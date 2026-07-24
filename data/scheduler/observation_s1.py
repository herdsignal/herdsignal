"""고정 S1 공식을 운영 가격 프레임에 적용해 최신 관찰 번들을 생성한다."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from herd.herd_state_s1 import (
    FAMILY_COLUMNS,
    ROOT,
    _stage,
    build_state_panel,
)
from herd.herd_transition_s1 import classify_transitions
from herd.validation_universe import SECTOR_UNIVERSE, TICKER_SECTOR_ETF


CONTRACT_PATH = ROOT / "data/config/observation_s1_service.json"
DEFAULT_OUTPUT = ROOT / "data/runtime/herd_observation_s1_latest.json"
FORMAT_VERSION = "HERD_OBSERVATION_S1_SERVICE_V1"
MARKET_TICKER = "SPY"
BENCHMARK_TICKERS = set(SECTOR_UNIVERSE["benchmark"])

SECTOR_NAME_TO_ETF = {
    "technology": "XLK",
    "information technology": "XLK",
    "communication services": "XLC",
    "consumer cyclical": "XLY",
    "consumer discretionary": "XLY",
    "consumer defensive": "XLP",
    "consumer staples": "XLP",
    "financial services": "XLF",
    "financials": "XLF",
    "healthcare": "XLV",
    "health care": "XLV",
    "industrials": "XLI",
    "aerospace & defense": "XLI",
    "energy": "XLE",
    "utilities": "XLU",
    "real estate": "XLRE",
    "basic materials": "XLB",
    "materials": "XLB",
}


class ObservationS1Error(RuntimeError):
    """운영 관찰 계약·입력 coverage·출력 경계가 깨졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ObservationS1Error(f"missing service input: {relative}")
    return path


def load_service_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != FORMAT_VERSION
        or contract.get("status") != "LOCKED_STATE_ONLY_SERVICE_CONTRACT"
    ):
        raise ObservationS1Error("S1 service contract is not locked")
    for key, version_key in (
        ("state_contract", "contract_version"),
        ("transition_contract", "contract_version"),
    ):
        specification = contract[key]
        source = _rooted(specification["path"])
        if _sha256(source) != specification["sha256"]:
            raise ObservationS1Error(f"S1 contract hash changed: {key}")
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get(version_key) != specification["required_version"]:
            raise ObservationS1Error(f"unexpected S1 contract version: {key}")
    universe = contract["reference_universe"]
    source = _rooted(universe["independent_universe_path"])
    if _sha256(source) != universe["independent_universe_sha256"]:
        raise ObservationS1Error("reference universe hash changed")
    boundary = contract["claim_boundary"]
    if (
        boundary["direction_prediction"]
        or boundary["buy_or_profit_take_authority"]
        or boundary["operational_action"] != "HOLD"
        or boundary["operational_action_ratio"] != 0.0
        or boundary["blind_holdout_access"]
    ):
        raise ObservationS1Error("observation contract cannot authorize actions")
    return contract


def load_model_contracts(
    service_contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = json.loads(
        _rooted(service_contract["state_contract"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    transition = json.loads(
        _rooted(service_contract["transition_contract"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if (
        state["observation_contract"]["future_outcomes_allowed"]
        or state["claim_boundary"]["operational_action_ratio"] != 0.0
        or transition["observation_contract"]["future_outcomes_allowed"]
        or transition["claim_boundary"]["operational_action_ratio"] != 0.0
    ):
        raise ObservationS1Error("research model boundary is not state-only")
    return state, transition


def load_reference_mapping(
    service_contract: dict[str, Any],
) -> dict[str, str]:
    universe = service_contract["reference_universe"]
    mapping = {
        ticker: sector
        for ticker, sector in TICKER_SECTOR_ETF.items()
        if ticker not in BENCHMARK_TICKERS
    }
    path = _rooted(universe["independent_universe_path"])
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if (
                universe["include_only_independent_eligible"]
                and row["eligible"] != "True"
            ):
                continue
            mapping[row["ticker"]] = row["sector_etf"]
    if len(mapping) != int(universe["expected_equities"]):
        raise ObservationS1Error(
            f"reference universe changed: expected={universe['expected_equities']} "
            f"actual={len(mapping)}"
        )
    return dict(sorted(mapping.items()))


def required_collection_tickers(
    service_contract: dict[str, Any] | None = None,
) -> set[str]:
    contract = service_contract or load_service_contract()
    mapping = load_reference_mapping(contract)
    return set(mapping) | set(mapping.values()) | {MARKET_TICKER}


def sector_etf_for_name(name: str | None) -> str | None:
    normalized = (name or "").strip().lower()
    return SECTOR_NAME_TO_ETF.get(normalized)


def _normalise_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    required = {"Date", "Close", "Volume"}
    if not required.issubset(frame.columns):
        raise ObservationS1Error(
            f"{ticker} price columns missing: {sorted(required - set(frame.columns))}"
        )
    normalized = frame.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce")
    normalized["Adj Close"] = pd.to_numeric(
        normalized["Close"], errors="coerce"
    )
    normalized["Volume"] = pd.to_numeric(
        normalized["Volume"], errors="coerce"
    )
    normalized = (
        normalized.dropna(subset=["Date", "Adj Close", "Volume"])
        .drop_duplicates("Date", keep="last")
        .sort_values("Date")
    )
    if normalized.empty:
        raise ObservationS1Error(f"{ticker} has no usable price rows")
    return normalized


def _market_panel(
    reference_panel: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    market = contract["market_observation"]
    expected = int(contract["reference_universe"]["expected_equities"])
    minimum = float(market["minimum_weekly_coverage_fraction"])
    grouped = reference_panel.groupby("signal_date", sort=True)
    coverage = grouped["ticker"].nunique() / expected
    family_medians = grouped[FAMILY_COLUMNS].median()
    result = family_medians.loc[coverage[coverage >= minimum].index].copy()
    if result.empty:
        raise ObservationS1Error("market aggregate has no covered weeks")
    result["DOWNSIDE_RISK_CONTEXT"] = grouped[
        "DOWNSIDE_RISK_CONTEXT"
    ].median().reindex(result.index)
    result["HERD_STATE"] = result[FAMILY_COLUMNS].mean(axis=1)
    result["HERD_STAGE"] = _stage(result["HERD_STATE"])
    result["ticker"] = market["public_ticker"]
    result["sector_etf"] = "SPY"
    result["universe_role"] = "MARKET_AGGREGATE"
    result["last_observed_session"] = result.index
    result["reference_coverage_fraction"] = coverage.reindex(result.index)
    return result.reset_index()


def _serialize_record(row: pd.Series, scope: str) -> dict[str, Any]:
    return {
        "ticker": str(row["ticker"]),
        "scope": scope,
        "asOfDate": pd.Timestamp(row["signal_date"]).date().isoformat(),
        "lastObservedSession": pd.Timestamp(
            row["last_observed_session"]
        ).date().isoformat(),
        "stateScore": round(float(row["HERD_STATE"]), 4),
        "stage": str(row["HERD_STAGE"]),
        "transition": str(row["HERD_TRANSITION"]),
        "rawTransition": str(row["RAW_HERD_TRANSITION"]),
        "transitionEvent": bool(row["TRANSITION_EVENT"]),
        "delta4w": round(float(row["HERD_DELTA_4W"]), 4),
        "delta13w": round(float(row["HERD_DELTA_13W"]), 4),
        "families": {
            column: round(float(row[column]), 4)
            for column in FAMILY_COLUMNS
        },
        "downsideRiskContext": round(
            float(row["DOWNSIDE_RISK_CONTEXT"]), 4
        ),
        "sectorEtf": str(row["sector_etf"]),
        "directionPrediction": False,
        "action": "HOLD",
        "actionRatio": 0.0,
    }


def build_observation_bundle(
    frames: dict[str, pd.DataFrame],
    *,
    target_tickers: set[str] | None = None,
    sector_overrides: dict[str, str] | None = None,
    service_contract: dict[str, Any] | None = None,
    reference_mapping: dict[str, str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    service = service_contract or load_service_contract()
    state_contract, transition_contract = load_model_contracts(service)
    reference = reference_mapping or load_reference_mapping(service)
    normalized: dict[str, pd.DataFrame] = {}
    rejected_frames: dict[str, str] = {}
    for ticker, frame in frames.items():
        try:
            normalized[ticker] = _normalise_frame(frame, ticker)
        except ObservationS1Error as exc:
            rejected_frames[ticker] = str(exc)
    available_reference = {
        ticker: sector
        for ticker, sector in reference.items()
        if ticker in normalized and sector in normalized
    }
    coverage = len(available_reference) / max(1, len(reference))
    minimum_coverage = float(
        service["reference_universe"]["minimum_total_coverage_fraction"]
    )
    if coverage < minimum_coverage:
        raise ObservationS1Error(
            f"reference coverage too low: {coverage:.4f} < {minimum_coverage:.4f}"
        )
    sector_counts = pd.Series(available_reference).value_counts().to_dict()
    minimum_peers = int(
        service["reference_universe"]["minimum_sector_peer_count"]
    )
    requested = set(target_tickers or available_reference)
    overrides = sector_overrides or {}
    sector_benchmarks = set(reference.values())
    target_mapping: dict[str, str] = {}
    unavailable: dict[str, str] = {}
    for ticker in sorted(requested):
        if ticker == MARKET_TICKER or ticker in sector_benchmarks:
            continue
        sector = reference.get(ticker) or overrides.get(ticker)
        if ticker not in normalized:
            unavailable[ticker] = rejected_frames.get(
                ticker, "PRICE_FRAME_UNAVAILABLE"
            )
        elif sector is None:
            unavailable[ticker] = "SECTOR_ETF_UNAVAILABLE"
        elif sector not in normalized:
            unavailable[ticker] = f"SECTOR_BENCHMARK_UNAVAILABLE:{sector}"
        elif int(sector_counts.get(sector, 0)) < minimum_peers:
            unavailable[ticker] = f"INSUFFICIENT_FIXED_SECTOR_PEERS:{sector}"
        else:
            target_mapping[ticker] = sector
    calculation_mapping = dict(available_reference)
    calculation_mapping.update(target_mapping)
    state_panel = build_state_panel(
        normalized,
        calculation_mapping,
        state_contract,
        "SERVICE_EQUITY",
        peer_mapping=available_reference,
    )
    transition_panel = classify_transitions(
        state_panel, transition_contract
    )
    latest = (
        transition_panel.sort_values("signal_date")
        .groupby("ticker", sort=True)
        .tail(1)
    )
    records = {
        str(row["ticker"]): _serialize_record(row, "EQUITY")
        for _, row in latest.iterrows()
        if row["ticker"] in target_mapping
    }
    reference_panel = state_panel[
        state_panel["ticker"].isin(available_reference)
    ]
    market_state = _market_panel(reference_panel, service)
    market_transition = classify_transitions(
        market_state, transition_contract
    )
    market_latest = market_transition.sort_values("signal_date").iloc[-1]
    market_record = _serialize_record(market_latest, "MARKET_AGGREGATE")
    market_record["label"] = service["market_observation"]["label"]
    market_record["claim"] = service["market_observation"]["claim"]
    market_record["referenceCoverageFraction"] = round(coverage, 4)
    records[MARKET_TICKER] = market_record
    now = generated_at or datetime.now(UTC)
    return {
        "schemaVersion": FORMAT_VERSION,
        "stateModelVersion": "HERD_STATE_S1",
        "transitionModelVersion": "HERD_TRANSITION_S1",
        "generatedAt": now.astimezone(UTC).isoformat(),
        "referenceUniverse": {
            "expected": len(reference),
            "available": len(available_reference),
            "coverageFraction": round(coverage, 6),
            "survivorshipSafe": False,
        },
        "records": dict(sorted(records.items())),
        "unavailable": unavailable,
        "claimBoundary": {
            "directionPrediction": False,
            "operationalAction": "HOLD",
            "operationalActionRatio": 0.0,
            "blindHoldoutAccess": False,
        },
    }


def write_observation_bundle(
    bundle: dict[str, Any],
    output_path: Path = DEFAULT_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output_path)

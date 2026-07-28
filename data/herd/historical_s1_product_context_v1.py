"""모든 S1 단계 진입의 과거 경로를 제품용 설명 통계로 고정한다."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from herd.historical_s1_replay_v1 import (
    CONTRACT_PATH as REPLAY_CONTRACT_PATH,
    _load_inputs,
    attach_outcomes,
    load_contract as load_replay_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_REPORT_PATH = (
    ROOT / "data/reports/historical_s1_product_context_v1.json"
)
DEFAULT_RESOURCE_PATH = (
    ROOT
    / "backend/src/main/resources/research/historical_s1_product_context_v1.json"
)
VERSION = "HERD_HISTORICAL_S1_PRODUCT_CONTEXT_V1"
STAGES = ["FLEE", "SCATTER", "CALM", "DRIFT", "RUSH"]
HORIZONS = [21, 63, 126]


class HistoricalS1ProductContextError(RuntimeError):
    """제품 설명 계약이나 고정 입력이 깨진 경우."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    boundary = contract.get("claim_boundary", {})
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status")
        != "LOCKED_DESCRIPTIVE_PRODUCT_CONTEXT_ONLY"
        or contract.get("stage_entries") != STAGES
        or contract.get("collapse_calendar_days") != 42
        or contract.get("horizons_sessions") != HORIZONS
        or int(contract.get("minimum_ticker_episodes", 0)) != 5
        or int(contract.get("minimum_reference_episodes", 0)) != 30
        or boundary.get("descriptive_context_only") is not True
        or boundary.get("current_constituent_history") is not True
        or boundary.get("candidate_selection") is not False
        or boundary.get("direction_prediction") is not False
        or boundary.get("buy_or_profit_take_authority") is not False
        or boundary.get("operational_action") != "HOLD"
        or float(boundary.get("operational_action_ratio", -1)) != 0.0
        or boundary.get("blind_holdout_access") is not False
        or boundary.get("survivorship_safe") is not False
    ):
        raise HistoricalS1ProductContextError(
            "historical product context contract is not locked"
        )
    return contract


def _replay_contract(product_contract: dict[str, Any]) -> dict[str, Any]:
    replay = copy.deepcopy(load_replay_contract(REPLAY_CONTRACT_PATH))
    replay["event_contract"]["stage_entries"] = product_contract["stage_entries"]
    replay["event_contract"]["highlighted_transitions"] = []
    replay["event_contract"]["collapse_calendar_days"] = product_contract[
        "collapse_calendar_days"
    ]
    replay["outcome_contract"]["horizons_sessions"] = product_contract[
        "horizons_sessions"
    ]
    return replay


def _summary(rows: pd.DataFrame) -> list[dict[str, Any]]:
    if rows.empty:
        return []
    grouped = (
        rows.assign(positive=rows["total_return"].gt(0).astype(float))
        .groupby("horizon_sessions", sort=True, observed=True)
        .agg(
            completedEpisodes=("episode_id", "nunique"),
            medianReturn=("total_return", "median"),
            positiveFraction=("positive", "mean"),
            medianMfe=("maximum_favorable_excursion", "median"),
            medianMae=("maximum_adverse_excursion", "median"),
        )
        .reset_index()
    )
    return [
        {
            "horizonSessions": int(row.horizon_sessions),
            "completedEpisodes": int(row.completedEpisodes),
            "medianReturnPct": round(float(row.medianReturn) * 100, 4),
            "positiveRatePct": round(float(row.positiveFraction) * 100, 2),
            "medianMfePct": round(float(row.medianMfe) * 100, 4),
            "medianMaePct": round(float(row.medianMae) * 100, 4),
        }
        for row in grouped.itertuples(index=False)
    ]


def build_context(
    ledger: pd.DataFrame,
    contract: dict[str, Any],
) -> dict[str, Any]:
    if (
        ledger.empty
        or ledger["direction_prediction"].fillna(True).astype(bool).any()
        or not ledger["operational_action"].eq("HOLD").all()
        or not pd.to_numeric(
            ledger["operational_action_ratio"], errors="coerce"
        ).eq(0.0).all()
    ):
        raise HistoricalS1ProductContextError(
            "product context ledger contains action authority"
        )
    ledger = ledger.copy()
    ledger["stage"] = ledger["event_kind"].str.removeprefix("STAGE_ENTRY_")
    references = {}
    for stage in STAGES:
        rows = ledger[ledger["stage"].eq(stage)]
        summaries = _summary(rows)
        references[stage] = {
            "evidenceStatus": (
                "DESCRIPTIVE_ONLY"
                if summaries
                and min(item["completedEpisodes"] for item in summaries)
                >= int(contract["minimum_reference_episodes"])
                else "INSUFFICIENT_SAMPLE"
            ),
            "episodeCount": int(rows["episode_id"].nunique()),
            "summaries": summaries,
        }
    tickers: dict[str, Any] = {}
    for (ticker, stage), rows in ledger.groupby(
        ["ticker", "stage"], sort=True, observed=True
    ):
        summaries = _summary(rows)
        tickers.setdefault(str(ticker), {})[str(stage)] = {
            "evidenceStatus": (
                "DESCRIPTIVE_ONLY"
                if summaries
                and min(item["completedEpisodes"] for item in summaries)
                >= int(contract["minimum_ticker_episodes"])
                else "INSUFFICIENT_SAMPLE"
            ),
            "episodeCount": int(rows["episode_id"].nunique()),
            "summaries": summaries,
        }
    return {
        "schemaVersion": VERSION,
        "stateModelVersion": contract["source_model"],
        "historyStartDate": str(ledger["signal_date"].min().date()),
        "historyEndDate": str(ledger["signal_date"].max().date()),
        "minimumTickerEpisodes": int(contract["minimum_ticker_episodes"]),
        "minimumReferenceEpisodes": int(contract["minimum_reference_episodes"]),
        "survivorshipSafe": False,
        "directionPrediction": False,
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
        "reference": references,
        "tickers": tickers,
    }


def run(
    contract_path: Path = CONTRACT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    resource_path: Path = DEFAULT_RESOURCE_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    replay_contract = _replay_contract(contract)
    events, keyed_prices, input_hashes = _load_inputs(
        replay_contract, REPLAY_CONTRACT_PATH
    )
    parts = []
    for role, role_events in events.groupby("universe_role", sort=True):
        prices = {
            key.split("|", 1)[1]: value
            for key, value in keyed_prices.items()
            if key.startswith(f"{role}|")
        }
        parts.append(attach_outcomes(role_events, prices, replay_contract))
    ledger = pd.concat(parts, ignore_index=True)
    context = build_context(ledger, contract)
    resource_path.parent.mkdir(parents=True, exist_ok=True)
    resource_path.write_text(
        json.dumps(context, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    report = {
        "reportVersion": VERSION,
        "status": "DESCRIPTIVE_PRODUCT_CONTEXT_READY",
        "episodes": int(ledger["episode_id"].nunique()),
        "rows": int(len(ledger)),
        "tickers": int(ledger["ticker"].nunique()),
        "historyStartDate": context["historyStartDate"],
        "historyEndDate": context["historyEndDate"],
        "inputHashes": {
            **input_hashes,
            "productContract": _sha256(contract_path),
        },
        "resource": {
            "path": str(resource_path.relative_to(ROOT)),
            "sha256": _sha256(resource_path),
        },
        "directionPrediction": False,
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
        "blindHoldoutAccess": False,
        "survivorshipSafe": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--resource", type=Path, default=DEFAULT_RESOURCE_PATH)
    args = parser.parse_args()
    print(json.dumps(
        run(args.contract, args.report, args.resource),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()

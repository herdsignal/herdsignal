"""사전등록된 FINRA–Rush 괴리 가설을 최근 pre-holdout에서 평가한다."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact


ROOT = Path(__file__).resolve().parents[2]
PREREG_PATH = ROOT / "data/herd/finra_rush_divergence_preregistration_v1.json"
MANIFEST_PATH = ROOT / "data/herd/finra_short_interest_incremental_v2_manifest.json"
IDENTITY_PATH = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v5.csv"
STATE_REPORT_PATH = ROOT / "data/reports/herd_state_s1.json"
PRICE_MANIFESTS = [
    ROOT / "data/snapshots/yf-long14-actions-sector-20260721/manifest.json",
    ROOT / "data/snapshots/yf-independent-current-sp500-20260721/manifest.json",
]
OUTPUT_PATH = ROOT / "data/reports/finra_rush_divergence_oos_v1.csv"
REPORT_PATH = ROOT / "data/reports/finra_rush_divergence_oos_v1.json"
VERSION = "HERD_FINRA_RUSH_DIVERGENCE_OOS_V1"
PINNED = {
    PREREG_PATH: "0a923ccdcbc98b6ff9accd7611f699cb39480ea48f3857fc65190b532c4a5405",
    MANIFEST_PATH: "f6c0e3685392ce38d8a30e2dcbcb9abbd7bd9664f8d1391b7c284ff5d3369588",
    IDENTITY_PATH: "4b10a272f1e5145cc1d73bdf6f91aace99502766d0a2d2c57cb30a206d6b9eed",
    STATE_REPORT_PATH: "dc154b7f6052bcae1dfd3accbe7f40bbd686f85908062f3800e911fde39b5121",
    PRICE_MANIFESTS[0]: "21cfb16db1e117778bdd6a56e54d3a207bbad29ab0edd676dbdd122e225aa44b",
    PRICE_MANIFESTS[1]: "dfc70664176b0fe4d04233164c877a5020ccacd653887eadbf5c4c0c38af9781",
}


class FinraRushDivergenceOosError(RuntimeError):
    """입력 무결성 또는 시점 정합 위반."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_inputs() -> None:
    for path, expected in PINNED.items():
        if not path.is_file() or _hash(path) != expected:
            raise FinraRushDivergenceOosError(f"pinned input changed: {path.relative_to(ROOT)}")


def _load_states() -> pd.DataFrame:
    report = json.loads(STATE_REPORT_PATH.read_text())
    parts = []
    for item in report["panels"].values():
        path = ROOT / item["path"]
        if _hash(path) != item["sha256"]:
            raise FinraRushDivergenceOosError("state panel hash changed")
        parts.append(pd.read_csv(path, compression="gzip", parse_dates=["signal_date"]))
    state = pd.concat(parts, ignore_index=True).sort_values(["ticker", "signal_date"])
    previous = state.groupby("ticker")["HERD_STAGE"].shift()
    starts = state["signal_date"].where(
        state["HERD_STAGE"].eq("RUSH") & previous.ne("RUSH")
    )
    state["rush_episode_start"] = starts.groupby(state["ticker"]).ffill()
    state.loc[state["HERD_STAGE"].ne("RUSH"), "rush_episode_start"] = pd.NaT
    if state.duplicated(["ticker", "signal_date"]).any():
        raise FinraRushDivergenceOosError("duplicate state observation")
    return state


def _valid_intervals(tickers: set[str]) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    intervals = pd.read_csv(IDENTITY_PATH)
    intervals = intervals[
        intervals["canonical_symbol"].isin(tickers)
        & intervals["status"].eq("TIME_VALID_CIK_VERIFIED")
    ].copy()
    intervals["valid_from"] = pd.to_datetime(intervals["valid_from"])
    intervals["valid_to"] = pd.to_datetime(intervals["valid_to"])
    return {
        ticker: list(zip(group["valid_from"], group["valid_to"], strict=True))
        for ticker, group in intervals.groupby("canonical_symbol")
    }


def _identity_valid(
    intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
    ticker: str,
    current: pd.Timestamp,
    previous: pd.Timestamp,
) -> bool:
    return any(start <= previous <= current <= end for start, end in intervals.get(ticker, []))


def _load_finra(tickers: set[str]) -> pd.DataFrame:
    manifest = json.loads(MANIFEST_PATH.read_text())
    parts = []
    for ordinal, entry in enumerate(manifest["entries"]):
        path = ROOT / entry["raw_path"]
        if _hash(path) != entry["sha256"]:
            raise FinraRushDivergenceOosError(f"FINRA raw hash changed: {entry['settlement_date']}")
        frame = pd.read_csv(
            path,
            sep="|",
            usecols=["symbolCode", "daysToCoverQuantity", "settlementDate"],
            dtype={"symbolCode": "string"},
        )
        frame = frame[frame["symbolCode"].isin(tickers)].copy()
        frame["publication_date"] = pd.Timestamp(entry["derived_publication_date"])
        frame["settlement_ordinal"] = ordinal
        parts.append(frame)
    result = pd.concat(parts, ignore_index=True)
    result = result.rename(
        columns={
            "symbolCode": "ticker",
            "daysToCoverQuantity": "days_to_cover",
            "settlementDate": "settlement_date",
        }
    )
    result["settlement_date"] = pd.to_datetime(result["settlement_date"])
    result["days_to_cover"] = pd.to_numeric(result["days_to_cover"], errors="coerce")
    return result.dropna(subset=["days_to_cover"]).sort_values(["ticker", "settlement_ordinal"])


def _attach_state(finra: pd.DataFrame, state: pd.DataFrame) -> pd.DataFrame:
    attached = []
    for ticker, rows in finra.groupby("ticker", sort=False):
        ticker_state = state[state["ticker"].eq(ticker)].sort_values("signal_date")
        if ticker_state.empty:
            continue
        merged = pd.merge_asof(
            rows.sort_values("publication_date"),
            ticker_state[
                ["signal_date", "HERD_STAGE", "sector_etf", "rush_episode_start"]
            ],
            left_on="publication_date",
            right_on="signal_date",
            direction="backward",
            allow_exact_matches=False,
        )
        merged["ticker"] = ticker
        attached.append(merged)
    if not attached:
        raise FinraRushDivergenceOosError("no FINRA rows joined to S1 state")
    return pd.concat(attached, ignore_index=True)


def _price_sources() -> dict[str, tuple[Path, str]]:
    sources: dict[str, tuple[Path, str]] = {}
    for manifest_path in PRICE_MANIFESTS:
        manifest = json.loads(manifest_path.read_text())
        for ticker, item in manifest["files"].items():
            sources.setdefault(ticker, (manifest_path.parent / item["path"], item["sha256"]))
    return sources


def _outcome(ticker: str, publication: pd.Timestamp, sources: dict[str, tuple[Path, str]]) -> dict[str, Any] | None:
    specification = sources.get(ticker)
    if specification is None:
        return None
    path, expected = specification
    if _hash(path) != expected:
        raise FinraRushDivergenceOosError(f"price hash changed: {ticker}")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        price = pd.read_csv(stream, parse_dates=["Date"], usecols=["Date", "Adj Close"])
    price = price.sort_values("Date")
    start_index = int(price["Date"].searchsorted(publication, side="right"))
    end_index = start_index + 63
    if start_index >= len(price) or end_index >= len(price):
        return None
    path_slice = price.iloc[start_index : end_index + 1]
    base = float(path_slice.iloc[0]["Adj Close"])
    returns = path_slice["Adj Close"].astype(float) / base - 1
    minimum = float(returns.min())
    terminal = float(returns.iloc[-1])
    adverse = minimum <= -0.12 or terminal <= -0.15
    return {
        "execution_date": path_slice.iloc[0]["Date"],
        "outcome_end": path_slice.iloc[-1]["Date"],
        "minimum_return_63d": minimum,
        "terminal_return_63d": terminal,
        "adverse_path": adverse,
    }


def _fold(anchor: pd.Timestamp, outcome_end: pd.Timestamp, folds: list[dict[str, str]]) -> str | None:
    for item in folds:
        if pd.Timestamp(item["start"]) <= anchor <= pd.Timestamp(item["end"]):
            return item["id"] if outcome_end <= pd.Timestamp(item["end"]) else None
    return None


def build_oos(
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    _verify_inputs()
    prereg = json.loads(PREREG_PATH.read_text())
    state = _load_states()
    tickers = set(state["ticker"])
    intervals = _valid_intervals(tickers)
    finra = _load_finra(tickers)
    group = finra.groupby("ticker", sort=False)
    finra["previous_settlement"] = group["settlement_date"].shift(1)
    finra["previous_ordinal"] = group["settlement_ordinal"].shift(1)
    finra["dtc_1"] = group["days_to_cover"].shift(1)
    finra["dtc_2"] = group["days_to_cover"].shift(2)
    finra["ordinal_2"] = group["settlement_ordinal"].shift(2)
    finra["identity_valid"] = [
        False
        if pd.isna(previous)
        else _identity_valid(intervals, ticker, current, previous)
        for ticker, current, previous in zip(
            finra["ticker"], finra["settlement_date"], finra["previous_settlement"], strict=True
        )
    ]
    joined = _attach_state(finra, state)
    staleness = (joined["publication_date"] - joined["signal_date"]).dt.days
    joined = joined[
        joined["identity_valid"]
        & joined["HERD_STAGE"].eq("RUSH")
        & staleness.le(prereg["exposure"]["maximum_state_staleness_calendar_days"])
        & joined["rush_episode_start"].notna()
        & joined["previous_ordinal"].eq(joined["settlement_ordinal"] - 1)
        & joined["ordinal_2"].eq(joined["settlement_ordinal"] - 2)
    ].copy()
    joined["sector_percentile"] = joined.groupby(
        ["settlement_date", "sector_etf"]
    )["days_to_cover"].rank(pct=True)
    joined["exposed"] = (
        joined["days_to_cover"].gt(joined["dtc_1"])
        & joined["dtc_1"].gt(joined["dtc_2"])
        & joined["sector_percentile"].ge(0.80)
    )
    anchors = (
        joined.sort_values("publication_date")
        .drop_duplicates(["ticker", "rush_episode_start"], keep="first")
        .copy()
    )
    sources = _price_sources()
    records = []
    for row in anchors.itertuples(index=False):
        outcome = _outcome(row.ticker, row.publication_date, sources)
        if outcome is None:
            continue
        fold_id = _fold(row.publication_date, outcome["outcome_end"], prereg["evaluation"]["time_folds"])
        if fold_id is None:
            continue
        records.append(
            {
                "ticker": row.ticker,
                "sector_etf": row.sector_etf,
                "rush_episode_start": row.rush_episode_start.date().isoformat(),
                "settlement_date": row.settlement_date.date().isoformat(),
                "publication_date": row.publication_date.date().isoformat(),
                "fold_id": fold_id,
                "days_to_cover": float(row.days_to_cover),
                "previous_days_to_cover": float(row.dtc_1),
                "two_period_days_to_cover": float(row.dtc_2),
                "sector_percentile": float(row.sector_percentile),
                "exposed": bool(row.exposed),
                "execution_date": outcome["execution_date"].date().isoformat(),
                "outcome_end": outcome["outcome_end"].date().isoformat(),
                "minimum_return_63d": outcome["minimum_return_63d"],
                "terminal_return_63d": outcome["terminal_return_63d"],
                "adverse_path": outcome["adverse_path"],
            }
        )
    result = pd.DataFrame(records)
    if result.empty:
        raise FinraRushDivergenceOosError("no complete fold observations")
    exposed = result[result["exposed"]]
    control = result[~result["exposed"]]
    exposed_adverse = int(exposed["adverse_path"].sum())
    control_adverse = int(control["adverse_path"].sum())
    exposed_rate = exposed_adverse / len(exposed) if len(exposed) else 0.0
    control_rate = control_adverse / len(control) if len(control) else 0.0
    risk_difference = exposed_rate - control_rate
    risk_ratio = exposed_rate / control_rate if control_rate else None
    table = [
        [exposed_adverse, len(exposed) - exposed_adverse],
        [control_adverse, len(control) - control_adverse],
    ]
    p_value = float(fisher_exact(table, alternative="greater").pvalue) if len(exposed) else 1.0
    fold_rows = []
    for fold_id, fold in result.groupby("fold_id"):
        left, right = fold[fold["exposed"]], fold[~fold["exposed"]]
        effect = None
        if len(left) >= 5 and len(right) >= 5:
            effect = float(left["adverse_path"].mean() - right["adverse_path"].mean())
        fold_rows.append(
            {
                "fold_id": fold_id,
                "exposed": len(left),
                "control": len(right),
                "risk_difference": effect,
            }
        )
    gate = prereg["evaluation"]
    checks = {
        "minimum_exposed_events": len(exposed) >= gate["minimum_historical_exposed_events"],
        "minimum_exposed_adverse_events": exposed_adverse >= gate["minimum_historical_adverse_events"],
        "minimum_distinct_tickers": exposed["ticker"].nunique() >= gate["minimum_distinct_tickers"],
        "minimum_distinct_sectors": exposed["sector_etf"].nunique() >= gate["minimum_distinct_sectors"],
        "minimum_directional_folds": sum(
            row["risk_difference"] is not None and row["risk_difference"] > 0 for row in fold_rows
        )
        >= gate["minimum_directionally_consistent_time_folds"],
        "minimum_risk_difference": risk_difference >= gate["minimum_effect_risk_difference"],
        "minimum_risk_ratio": risk_ratio is not None and risk_ratio >= gate["minimum_effect_risk_ratio"],
        "maximum_p_value": p_value <= gate["maximum_holm_p_value"],
    }
    passed = all(checks.values())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    report = {
        "report_version": VERSION,
        "status": "RECENT_PREHOLDOUT_SENSITIVITY_COMPLETE",
        "rows": len(result),
        "tickers": int(result["ticker"].nunique()),
        "exposed_events": len(exposed),
        "exposed_adverse_events": exposed_adverse,
        "control_events": len(control),
        "control_adverse_events": control_adverse,
        "exposed_adverse_rate": exposed_rate,
        "control_adverse_rate": control_rate,
        "risk_difference": risk_difference,
        "risk_ratio": risk_ratio,
        "one_sided_fisher_p_value": p_value,
        "folds": fold_rows,
        "checks": checks,
        "historical_gate_passed": passed,
        "adoption_allowed": False,
        "prospective_confirmation_required": True,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "panel_path": str(output_path.relative_to(ROOT)),
        "panel_sha256": _hash(output_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_oos(), indent=2))

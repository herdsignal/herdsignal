"""사전등록된 Form 4 비정례 다중 매도–S1 Rush 가설을 1회 평가한다."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

from herd.sec_form4_nonroutine_sale_rush_preregistration_v1 import (
    validate_preregistration,
)


ROOT = Path(__file__).resolve().parents[2]
PREREG_PATH = Path(__file__).with_name(
    "sec_form4_nonroutine_sale_rush_preregistration_v1.json"
)
SALE_PATH = ROOT / "data/reports/sec_form4_nonroutine_sale_events_v1.csv"
STATE_REPORT_PATH = ROOT / "data/reports/herd_state_s1.json"
PRICE_MANIFESTS = [
    ROOT / "data/snapshots/yf-long14-actions-sector-20260721/manifest.json",
    ROOT / "data/snapshots/yf-independent-current-sp500-20260721/manifest.json",
]
OUTPUT_PATH = ROOT / "data/reports/sec_form4_nonroutine_sale_rush_oos_v1.csv"
REPORT_PATH = ROOT / "data/reports/sec_form4_nonroutine_sale_rush_oos_v1.json"
VERSION = "HERD_SEC_FORM4_NONROUTINE_SALE_RUSH_OOS_V1"
PINNED = {
    SALE_PATH: "95f4e4710b6e8b74cc9b5b37f0d4031d8f5068a45fd31f2cd2b5de89d3962a14",
    STATE_REPORT_PATH: "dc154b7f6052bcae1dfd3accbe7f40bbd686f85908062f3800e911fde39b5121",
    PRICE_MANIFESTS[0]: "21cfb16db1e117778bdd6a56e54d3a207bbad29ab0edd676dbdd122e225aa44b",
    PRICE_MANIFESTS[1]: "dfc70664176b0fe4d04233164c877a5020ccacd653887eadbf5c4c0c38af9781",
}


class Form4SaleRushOosError(RuntimeError):
    """고정 입력 또는 시점 정합성이 훼손된 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_inputs() -> dict[str, Any]:
    protocol = json.loads(PREREG_PATH.read_text())
    validate_preregistration(protocol)
    for path, expected in PINNED.items():
        if not path.is_file() or _hash(path) != expected:
            raise Form4SaleRushOosError(
                f"pinned input changed: {path.relative_to(ROOT)}"
            )
    return protocol


def _rush_entries() -> pd.DataFrame:
    report = json.loads(STATE_REPORT_PATH.read_text())
    parts = []
    for item in report["panels"].values():
        path = ROOT / item["path"]
        if _hash(path) != item["sha256"]:
            raise Form4SaleRushOosError("state panel hash changed")
        parts.append(
            pd.read_csv(path, compression="gzip", parse_dates=["signal_date"])
        )
    state = pd.concat(parts, ignore_index=True).sort_values(
        ["ticker", "signal_date"]
    )
    previous = state.groupby("ticker", sort=False)["HERD_STAGE"].shift()
    entries = state[
        state["HERD_STAGE"].eq("RUSH")
        & previous.notna()
        & previous.ne("RUSH")
    ].copy()
    if entries.duplicated(["ticker", "signal_date"]).any():
        raise Form4SaleRushOosError("duplicate S1 Rush entry")
    return entries


def _sales() -> dict[str, pd.DataFrame]:
    sales = pd.read_csv(
        SALE_PATH,
        dtype={"issuerTradingSymbol": "string", "reportingOwnerCik": "string"},
        parse_dates=["filingDate"],
    )
    sales = sales[
        sales["candidateEligible"].eq(True)
        & sales["timingStatus"].eq("TIMING_NON_ROUTINE_CANDIDATE")
        & sales["explicit10b5One"].eq(False)
    ].copy()
    sales["ticker"] = (
        sales["issuerTradingSymbol"].str.upper().str.replace(".", "-", regex=False)
    )
    return {
        ticker: frame.sort_values("filingDate")
        for ticker, frame in sales.groupby("ticker", sort=False)
    }


def _attach_exposure(
    entries: pd.DataFrame,
    sales_by_ticker: dict[str, pd.DataFrame],
    lookback_days: int,
    minimum_owners: int,
) -> pd.DataFrame:
    records = []
    for row in entries.itertuples(index=False):
        sales = sales_by_ticker.get(row.ticker)
        window = (
            sales[
                sales["filingDate"].ge(
                    row.signal_date - pd.Timedelta(days=lookback_days)
                )
                & sales["filingDate"].lt(row.signal_date)
            ]
            if sales is not None
            else pd.DataFrame()
        )
        owners = (
            int(window["reportingOwnerCik"].nunique()) if len(window) else 0
        )
        records.append(
            {
                "ticker": row.ticker,
                "sector_etf": row.sector_etf,
                "universe_role": row.universe_role,
                "signal_date": row.signal_date,
                "HERD_STATE": float(row.HERD_STATE),
                "distinct_sale_owners_30d": owners,
                "sale_events_30d": len(window),
                "exposed": owners >= minimum_owners,
            }
        )
    return pd.DataFrame(records)


def _price_sources() -> dict[str, tuple[Path, str]]:
    sources: dict[str, tuple[Path, str]] = {}
    for manifest_path in PRICE_MANIFESTS:
        manifest = json.loads(manifest_path.read_text())
        for ticker, item in manifest["files"].items():
            sources.setdefault(
                ticker, (manifest_path.parent / item["path"], item["sha256"])
            )
    return sources


def _outcome(
    ticker: str,
    signal_date: pd.Timestamp,
    sources: dict[str, tuple[Path, str]],
    horizon: int,
) -> dict[str, Any] | None:
    specification = sources.get(ticker)
    if specification is None:
        return None
    path, expected = specification
    if _hash(path) != expected:
        raise Form4SaleRushOosError(f"price hash changed: {ticker}")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        price = pd.read_csv(
            stream, parse_dates=["Date"], usecols=["Date", "Adj Close"]
        ).sort_values("Date")
    start = int(price["Date"].searchsorted(signal_date, side="right"))
    end = start + horizon
    if start >= len(price) or end >= len(price):
        return None
    path_slice = price.iloc[start : end + 1]
    base = float(path_slice.iloc[0]["Adj Close"])
    returns = path_slice["Adj Close"].astype(float) / base - 1
    minimum = float(returns.min())
    terminal = float(returns.iloc[-1])
    return {
        "execution_date": path_slice.iloc[0]["Date"],
        "outcome_end": path_slice.iloc[-1]["Date"],
        "minimum_return_63d": minimum,
        "terminal_return_63d": terminal,
        "adverse_path": minimum <= -0.12 or terminal <= -0.15,
    }


def _fold(
    signal_date: pd.Timestamp,
    outcome_end: pd.Timestamp,
    folds: list[dict[str, str]],
) -> str | None:
    for item in folds:
        if pd.Timestamp(item["start"]) <= signal_date <= pd.Timestamp(item["end"]):
            return item["id"] if outcome_end <= pd.Timestamp(item["end"]) else None
    return None


def _risk_difference(frame: pd.DataFrame) -> tuple[float, float]:
    exposed = frame.loc[frame["exposed"], "adverse_path"]
    control = frame.loc[~frame["exposed"], "adverse_path"]
    if exposed.empty or control.empty:
        return math.nan, math.nan
    exposed_rate, control_rate = float(exposed.mean()), float(control.mean())
    ratio = exposed_rate / control_rate if control_rate else math.inf
    return exposed_rate - control_rate, ratio


def _cluster_bootstrap(
    panel: pd.DataFrame, iterations: int = 2000, seed: int = 20260726
) -> dict[str, Any]:
    tickers = sorted(panel["ticker"].unique())
    groups = {ticker: panel[panel["ticker"].eq(ticker)] for ticker in tickers}
    generator = np.random.default_rng(seed)
    differences = []
    for _ in range(iterations):
        sampled = generator.choice(tickers, len(tickers), replace=True)
        frame = pd.concat([groups[ticker] for ticker in sampled])
        difference, _ = _risk_difference(frame)
        if not math.isnan(difference):
            differences.append(difference)
    interval = (
        [float(np.quantile(differences, 0.025)), float(np.quantile(differences, 0.975))]
        if differences
        else [None, None]
    )
    return {
        "iterations": iterations,
        "valid_iterations": len(differences),
        "risk_difference_ci_95": interval,
    }


def build_oos(
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    protocol = _verify_inputs()
    exposure = protocol["exposure"]
    panel = _attach_exposure(
        _rush_entries(),
        _sales(),
        int(exposure["lookback_calendar_days"]),
        int(exposure["minimum_distinct_reporting_owners"]),
    )
    sources = _price_sources()
    records = []
    for row in panel.itertuples(index=False):
        outcome = _outcome(
            row.ticker,
            row.signal_date,
            sources,
            int(protocol["outcome"]["horizon_sessions"]),
        )
        if outcome is None:
            continue
        fold_id = _fold(
            row.signal_date, outcome["outcome_end"], protocol["oos_folds"]
        )
        if fold_id is None:
            continue
        record = row._asdict()
        record.update(outcome)
        record["fold_id"] = fold_id
        records.append(record)
    result = pd.DataFrame(records)
    if result.empty:
        raise Form4SaleRushOosError("no complete fold observations")

    exposed = result[result["exposed"]]
    control = result[~result["exposed"]]
    exposed_adverse = int(exposed["adverse_path"].sum())
    control_adverse = int(control["adverse_path"].sum())
    exposed_rate = float(exposed["adverse_path"].mean()) if len(exposed) else 0.0
    control_rate = float(control["adverse_path"].mean()) if len(control) else 0.0
    risk_difference, risk_ratio = _risk_difference(result)
    fisher_p = float(
        fisher_exact(
            [
                [exposed_adverse, len(exposed) - exposed_adverse],
                [control_adverse, len(control) - control_adverse],
            ],
            alternative="greater",
        ).pvalue
    )
    fold_rows = []
    for fold_id, frame in result.groupby("fold_id", sort=False):
        difference, ratio = _risk_difference(frame)
        positive = frame[frame["exposed"]]
        fold_rows.append(
            {
                "fold_id": fold_id,
                "episodes": len(frame),
                "feature_positive_episodes": len(positive),
                "feature_positive_adverse_rate": (
                    float(positive["adverse_path"].mean()) if len(positive) else None
                ),
                "feature_negative_adverse_rate": float(
                    frame.loc[~frame["exposed"], "adverse_path"].mean()
                ),
                "adverse_risk_difference": (
                    None if math.isnan(difference) else difference
                ),
                "relative_risk": None if math.isnan(ratio) else ratio,
                "direction_matches_hypothesis": (
                    not math.isnan(difference) and difference > 0
                ),
            }
        )
    bootstrap = _cluster_bootstrap(result)
    lower = bootstrap["risk_difference_ci_95"][0]
    gate = protocol["adoption_gate"]
    folds_with_ten = sum(
        row["feature_positive_episodes"] >= 10 for row in fold_rows
    )
    direction_folds = sum(
        row["direction_matches_hypothesis"] for row in fold_rows
    )
    checks = {
        "minimum_resolved_episodes": len(result)
        >= gate["minimum_resolved_episodes"],
        "minimum_feature_positive_episodes": len(exposed)
        >= gate["minimum_feature_positive_episodes"],
        "minimum_feature_positive_tickers": exposed["ticker"].nunique()
        >= gate["minimum_feature_positive_tickers"],
        "minimum_folds_with_at_least_10_positive_episodes": folds_with_ten
        >= gate["minimum_folds_with_at_least_10_positive_episodes"],
        "minimum_direction_consistent_folds": direction_folds
        >= gate["minimum_direction_consistent_folds"],
        "minimum_pooled_adverse_risk_difference": risk_difference
        >= gate["minimum_pooled_adverse_risk_difference"],
        "minimum_pooled_relative_risk": risk_ratio
        >= gate["minimum_pooled_relative_risk"],
        "bootstrap_lower_risk_difference_above_zero": lower is not None
        and lower
        > gate["minimum_ticker_cluster_bootstrap_95_lower_risk_difference"],
        "maximum_one_sided_fisher_p_value": fisher_p
        <= gate["maximum_one_sided_fisher_p_value"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    report = {
        "report_version": VERSION,
        "status": "PREHOLDOUT_OOS_COMPLETE",
        "episodes": len(result),
        "tickers": int(result["ticker"].nunique()),
        "feature_positive_episodes": len(exposed),
        "feature_positive_tickers": int(exposed["ticker"].nunique()),
        "feature_positive_adverse_episodes": exposed_adverse,
        "feature_negative_episodes": len(control),
        "feature_negative_adverse_episodes": control_adverse,
        "feature_positive_adverse_rate": exposed_rate,
        "feature_negative_adverse_rate": control_rate,
        "pooled_adverse_risk_difference": risk_difference,
        "pooled_relative_risk": risk_ratio,
        "one_sided_fisher_p_value": fisher_p,
        "folds": fold_rows,
        "ticker_cluster_bootstrap": bootstrap,
        "checks": checks,
        "passed": all(checks.values()),
        "adoption_allowed": False,
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

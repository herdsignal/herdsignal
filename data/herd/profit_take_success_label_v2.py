"""State S1 희소 Rush 사건의 경제적 성공 라벨 V2를 생성한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from herd.vnext_competing_path_economic_label_v1 import (
    classify_competing_path,
    load_contract as load_path_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
CEILING_PATH = ROOT / "data/reports/profit_take_opportunity_ceiling_v1.csv"
FOLD_PATH = ROOT / "data/walk_forward/long-oos-v2-20260721/price_timing_6m.csv"
OUTPUT_PATH = ROOT / "data/reports/profit_take_success_label_v2.csv"
REPORT_PATH = ROOT / "data/reports/profit_take_success_label_v2.json"
VERSION = "HERD_PROFIT_TAKE_SUCCESS_LABEL_V2"


class ProfitTakeSuccessLabelError(ValueError):
    """라벨 우선순위·해시·미래정보 경계가 깨진 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_LABEL_COUNTS"
    ):
        raise ProfitTakeSuccessLabelError("success label is not locked")
    for item in contract["inputs"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ProfitTakeSuccessLabelError(f"missing input: {item['path']}")
        if _hash(path) != item["sha256"]:
            raise ProfitTakeSuccessLabelError(f"input changed: {item['path']}")
    labels = [item["label"] for item in contract["labels_in_priority_order"]]
    firewall = contract["firewall"]
    if (
        labels
        != [
            "STRUCTURAL_DAMAGE",
            "ECONOMIC_REBUY_OPPORTUNITY",
            "HEALTHY_CONTINUATION",
            "NO_ECONOMIC_EDGE",
        ]
        or contract["population"]["maximum_events_per_ticker_year"] != 2
        or contract["population"]["outcome_must_end_inside_test_fold"] is not True
        or firewall["future_fields_may_enter_features"] is not False
        or firewall["oracle_reentry_may_execute"] is not False
        or firewall["labels_authorize_actions"] is not False
        or firewall["survivorship_safe"] is not False
        or firewall["blind_holdout_access"] is not False
        or firewall["operational_action_ratio"] != 0.0
    ):
        raise ProfitTakeSuccessLabelError("label or action boundary changed")
    return contract


def assign_label(stress_opportunity: bool, terminal_path: str) -> str:
    if terminal_path == "STRUCTURAL_BREAK":
        return "STRUCTURAL_DAMAGE"
    if stress_opportunity:
        return "ECONOMIC_REBUY_OPPORTUNITY"
    if terminal_path == "CONTINUATION":
        return "HEALTHY_CONTINUATION"
    return "NO_ECONOMIC_EDGE"


def _price_sources() -> dict[str, tuple[Path, str]]:
    sources: dict[str, tuple[Path, str]] = {}
    for relative in (
        "data/snapshots/yf-long14-actions-sector-20260721/manifest.json",
        "data/snapshots/yf-independent-current-sp500-20260721/manifest.json",
    ):
        manifest_path = ROOT / relative
        manifest = json.loads(manifest_path.read_text())
        for ticker, item in manifest["files"].items():
            sources.setdefault(
                ticker, (manifest_path.parent / item["path"], item["sha256"])
            )
    return sources


def _load_price(path: Path, expected: str) -> pd.DataFrame:
    if _hash(path) != expected:
        raise ProfitTakeSuccessLabelError(f"price changed: {path.name}")
    frame = pd.read_csv(path, compression="gzip", parse_dates=["Date"])
    return frame.set_index("Date").sort_index()


def _fold(
    signal_date: pd.Timestamp,
    outcome_end: pd.Timestamp,
    folds: pd.DataFrame,
) -> str | None:
    matched = folds[
        folds["test_start"].le(signal_date)
        & folds["test_end"].ge(signal_date)
        & folds["test_end"].ge(outcome_end)
    ]
    return str(matched.iloc[0]["fold_id"]) if len(matched) else None


def _coverage_gate(panel: pd.DataFrame, contract: dict[str, Any]) -> dict[str, bool]:
    gate = contract["next_gate"]
    primary = ("ECONOMIC_REBUY_OPPORTUNITY", "HEALTHY_CONTINUATION")
    checks = {
        "minimum_total_labeled_events": len(panel)
        >= gate["minimum_total_labeled_events"]
    }
    for label in primary:
        frame = panel[panel["success_label"].eq(label)]
        key = label.lower()
        checks[f"{key}_minimum_events"] = (
            len(frame) >= gate["minimum_events_each_primary_class"]
        )
        checks[f"{key}_minimum_tickers"] = (
            frame["ticker"].nunique()
            >= gate["minimum_tickers_each_primary_class"]
        )
        checks[f"{key}_minimum_folds"] = (
            frame["fold_id"].nunique()
            >= gate["minimum_folds_each_primary_class"]
        )
    return checks


def build_labels(
    output_path: Path = OUTPUT_PATH, report_path: Path = REPORT_PATH
) -> dict[str, Any]:
    contract = validate_contract(json.loads(CONTRACT_PATH.read_text()))
    ceiling = pd.read_csv(
        CEILING_PATH, parse_dates=["signal_date", "outcome_end"]
    )
    ceiling = ceiling[ceiling["sparse_eligible"].eq(True)].copy()
    folds = pd.read_csv(FOLD_PATH, parse_dates=["test_start", "test_end"])
    sources = _price_sources()
    prices: dict[str, pd.DataFrame] = {}
    path_contract = load_path_contract()
    records = []
    exclusions = {"OUTSIDE_FIXED_FOLD": 0, "RIGHT_CENSORED": 0}
    for row in ceiling.itertuples(index=False):
        fold_id = _fold(row.signal_date, row.outcome_end, folds)
        if fold_id is None:
            exclusions["OUTSIDE_FIXED_FOLD"] += 1
            continue
        if row.ticker not in prices:
            path, expected = sources[row.ticker]
            prices[row.ticker] = _load_price(path, expected)
        outcome = classify_competing_path(
            prices[row.ticker], row.signal_date, path_contract
        )
        if outcome.status == "RIGHT_CENSORED":
            exclusions["RIGHT_CENSORED"] += 1
            continue
        label = assign_label(
            bool(row.stress_constrained_available), outcome.terminal_path
        )
        records.append(
            {
                "ticker": row.ticker,
                "universe_role": row.universe_role,
                "signal_date": row.signal_date.date().isoformat(),
                "outcome_end": outcome.outcome_end,
                "fold_id": fold_id,
                "success_label": label,
                "first_boundary": outcome.first_boundary,
                "terminal_path": outcome.terminal_path,
                "maximum_favorable_excursion": outcome.maximum_favorable_excursion,
                "maximum_adverse_excursion": outcome.maximum_adverse_excursion,
                "terminal_return": outcome.terminal_return,
                "stress_constrained_sleeve_share_delta_rate": (
                    float(row.stress_constrained_share_delta_rate)
                ),
                "stress_constrained_time_to_reentry_sessions": (
                    None
                    if pd.isna(row.stress_constrained_time_to_reentry_sessions)
                    else int(row.stress_constrained_time_to_reentry_sessions)
                ),
                "future_fields_are_labels_only": True,
            }
        )
    panel = pd.DataFrame(records)
    if panel.empty or panel.duplicated(["ticker", "signal_date"]).any():
        raise ProfitTakeSuccessLabelError("label panel is empty or duplicated")
    checks = _coverage_gate(panel, contract)
    label_counts = {
        label: int(count)
        for label, count in panel["success_label"].value_counts().items()
    }
    lane_counts = {
        lane: {
            label: int(count)
            for label, count in frame["success_label"].value_counts().items()
        }
        for lane, frame in panel.groupby("universe_role", sort=False)
    }
    fold_counts = {
        fold: {
            label: int(count)
            for label, count in frame["success_label"].value_counts().items()
        }
        for fold, frame in panel.groupby("fold_id", sort=False)
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output_path, index=False)
    report = {
        "report_version": VERSION,
        "status": (
            "SUCCESS_LABEL_V2_COVERAGE_PASSED"
            if all(checks.values())
            else "SUCCESS_LABEL_V2_COVERAGE_FAILED"
        ),
        "rows": len(panel),
        "tickers": int(panel["ticker"].nunique()),
        "folds": int(panel["fold_id"].nunique()),
        "label_counts": label_counts,
        "universe_label_counts": lane_counts,
        "fold_label_counts": fold_counts,
        "exclusions": exclusions,
        "checks": checks,
        "coverage_passed": all(checks.values()),
        "direction_evidence_admitted": False,
        "labels_authorize_actions": False,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "panel_path": str(output_path.relative_to(ROOT)),
        "panel_sha256": _hash(output_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_labels(), indent=2))

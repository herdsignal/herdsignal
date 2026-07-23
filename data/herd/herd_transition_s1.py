"""HERD State S1의 관측 가능한 주간 변화만으로 Transition S1을 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from herd.herd_state_s1 import FAMILY_COLUMNS, ROOT


CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_REPORT = ROOT / "data/reports/herd_transition_s1.json"
DEFAULT_LATEST = ROOT / "data/reports/herd_transition_s1_latest.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data/walk_forward/herd-transition-s1"
POSITIVE_TRANSITIONS = {"EXTENDING", "RECOVERING"}
NEGATIVE_TRANSITIONS = {"COOLING", "BREAKING", "FALLING"}
HIGHLIGHTED_TRANSITIONS = {"COOLING", "BREAKING", "RECOVERING"}


class HerdTransitionS1Error(RuntimeError):
    """상태 입력이나 전환 계약이 깨졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise HerdTransitionS1Error(f"missing transition input: {relative}")
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != "HERD_TRANSITION_S1"
        or contract.get("status") != "LOCKED_BEFORE_TRANSITION_STABILITY_RESULTS"
    ):
        raise HerdTransitionS1Error("Transition S1 contract is not locked")
    observation = contract["observation_contract"]
    if observation["future_outcomes_allowed"]:
        raise HerdTransitionS1Error("transition cannot read future outcomes")
    if contract["claim_boundary"]["operational_action_ratio"] != 0.0:
        raise HerdTransitionS1Error("transition cannot authorize an action")
    expected = [
        "BREAKING",
        "RECOVERING",
        "COOLING",
        "EXTENDING",
        "FALLING",
        "STABILIZING",
        "PLATEAU",
        "NEUTRAL",
        "UNKNOWN",
    ]
    if [item["id"] for item in contract["classification_priority"]] != expected:
        raise HerdTransitionS1Error("transition classification priority changed")
    return contract


def _load_state_report(contract: dict[str, Any]) -> tuple[dict, dict[str, Path]]:
    specification = contract["state_input"]
    report_path = _rooted(specification["report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        report.get("status") != specification["required_status"]
        or not report.get("state_display_ready")
        or report.get("future_outcomes_read")
        or report.get("operational_action_ratio") != 0.0
    ):
        raise HerdTransitionS1Error("HERD State S1 is not a safe transition input")
    panels = {}
    for role, receipt in report["panels"].items():
        path = _rooted(receipt["path"])
        if _sha256(path) != receipt["sha256"]:
            raise HerdTransitionS1Error(f"state panel hash changed: {role}")
        panels[role] = path
    return report, panels


def classify_transitions(
    panel: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    required = {
        "ticker",
        "signal_date",
        "HERD_STATE",
        "HERD_STAGE",
        *FAMILY_COLUMNS,
    }
    if not required.issubset(panel.columns):
        raise HerdTransitionS1Error(
            f"state panel columns missing: {sorted(required - set(panel.columns))}"
        )
    observation = contract["observation_contract"]
    lookback = int(observation["short_change_weeks"])
    memory = int(observation["extreme_memory_weeks"])
    moderate = float(observation["moderate_score_change"])
    severe = float(observation["severe_score_change"])
    family_change = float(observation["moderate_family_change"])
    moderate_votes = int(observation["moderate_family_votes"])
    severe_votes = int(observation["severe_family_votes"])

    output_parts = []
    for _, rows in panel.groupby("ticker", sort=False):
        rows = rows.copy().sort_values("signal_date")
        rows["HERD_DELTA_4W"] = rows["HERD_STATE"] - rows["HERD_STATE"].shift(lookback)
        rows["HERD_DELTA_13W"] = rows["HERD_STATE"] - rows["HERD_STATE"].shift(memory)
        family_delta_columns = []
        for family in FAMILY_COLUMNS:
            column = f"{family}_DELTA_4W"
            rows[column] = rows[family] - rows[family].shift(lookback)
            family_delta_columns.append(column)
        rows["FAMILY_UP_VOTES"] = (
            rows[family_delta_columns] >= family_change
        ).sum(axis=1)
        rows["FAMILY_DOWN_VOTES"] = (
            rows[family_delta_columns] <= -family_change
        ).sum(axis=1)
        rows["RECENT_13W_MAX_HERD"] = rows["HERD_STATE"].rolling(
            memory, min_periods=memory
        ).max()
        rows["RECENT_13W_MIN_HERD"] = rows["HERD_STATE"].rolling(
            memory, min_periods=memory
        ).min()
        fully_observed = rows[
            [
                "HERD_DELTA_4W",
                "RECENT_13W_MAX_HERD",
                "RECENT_13W_MIN_HERD",
                *family_delta_columns,
            ]
        ].notna().all(axis=1)
        conditions = [
            fully_observed
            & (rows["RECENT_13W_MAX_HERD"] >= 75)
            & (rows["HERD_DELTA_4W"] <= -severe)
            & (rows["FAMILY_DOWN_VOTES"] >= severe_votes),
            fully_observed
            & (rows["RECENT_13W_MIN_HERD"] <= 40)
            & (rows["HERD_DELTA_4W"] >= severe)
            & (rows["FAMILY_UP_VOTES"] >= severe_votes),
            fully_observed
            & (rows["HERD_STATE"] >= 60)
            & (rows["HERD_DELTA_4W"] <= -moderate)
            & (rows["FAMILY_DOWN_VOTES"] >= moderate_votes),
            fully_observed
            & (rows["HERD_STATE"] >= 60)
            & (rows["HERD_DELTA_4W"] >= moderate)
            & (rows["FAMILY_UP_VOTES"] >= moderate_votes),
            fully_observed
            & (rows["HERD_STATE"] <= 40)
            & (rows["HERD_DELTA_4W"] <= -moderate)
            & (rows["FAMILY_DOWN_VOTES"] >= moderate_votes),
            fully_observed
            & (rows["HERD_STATE"] <= 40)
            & (rows["HERD_DELTA_4W"].abs() < moderate),
            fully_observed
            & (rows["HERD_STATE"] >= 60)
            & (rows["HERD_DELTA_4W"].abs() < moderate),
            fully_observed,
        ]
        choices = [
            "BREAKING",
            "RECOVERING",
            "COOLING",
            "EXTENDING",
            "FALLING",
            "STABILIZING",
            "PLATEAU",
            "NEUTRAL",
        ]
        rows["RAW_HERD_TRANSITION"] = np.select(
            conditions, choices, default="UNKNOWN"
        )
        rows["HERD_TRANSITION"], rows["OPPOSITE_DIRECTION_SUPPRESSED"] = (
            _stabilize_directional_labels(
                rows["RAW_HERD_TRANSITION"],
                int(observation["direction_confirmation_weeks"]),
                int(observation["opposite_direction_cooldown_weeks"]),
            )
        )
        previous = rows["HERD_TRANSITION"].shift(1)
        rows["TRANSITION_EVENT"] = (
            rows["HERD_TRANSITION"].isin(HIGHLIGHTED_TRANSITIONS)
            & rows["HERD_TRANSITION"].ne(previous)
        )
        output_parts.append(rows)
    return pd.concat(output_parts, ignore_index=True)


def _stabilize_directional_labels(
    raw: pd.Series,
    confirmation_weeks: int,
    cooldown_weeks: int,
) -> tuple[pd.Series, pd.Series]:
    labels = raw.astype(str).tolist()
    stabilized: list[str] = []
    suppressed: list[bool] = []
    last_direction: str | None = None
    last_direction_index = -10_000
    directional = POSITIVE_TRANSITIONS | NEGATIVE_TRANSITIONS
    for index, label in enumerate(labels):
        is_directional = label in directional
        confirmed = (
            is_directional
            and index + 1 >= confirmation_weeks
            and all(
                item == label
                for item in labels[index - confirmation_weeks + 1:index + 1]
            )
        )
        if is_directional and not confirmed:
            stabilized.append("NEUTRAL")
            suppressed.append(False)
            continue
        if not is_directional:
            stabilized.append(label)
            suppressed.append(False)
            continue
        direction = "POSITIVE" if label in POSITIVE_TRANSITIONS else "NEGATIVE"
        opposite_inside_cooldown = (
            last_direction is not None
            and direction != last_direction
            and index - last_direction_index <= cooldown_weeks
        )
        if opposite_inside_cooldown:
            stabilized.append("NEUTRAL")
            suppressed.append(True)
            continue
        stabilized.append(label)
        suppressed.append(False)
        last_direction = direction
        last_direction_index = index
    return (
        pd.Series(stabilized, index=raw.index, dtype="string"),
        pd.Series(suppressed, index=raw.index, dtype=bool),
    )


def _opposite_flip_fraction(panel: pd.DataFrame, lookback: int) -> float:
    flips = 0
    eligible = 0
    for _, rows in panel.groupby("ticker", sort=False):
        labels = rows.sort_values("signal_date")["HERD_TRANSITION"].tolist()
        for index, label in enumerate(labels):
            if label not in POSITIVE_TRANSITIONS | NEGATIVE_TRANSITIONS:
                continue
            prior = labels[max(0, index - lookback):index]
            eligible += 1
            if label in POSITIVE_TRANSITIONS:
                flips += any(item in NEGATIVE_TRANSITIONS for item in prior)
            else:
                flips += any(item in POSITIVE_TRANSITIONS for item in prior)
    return flips / eligible if eligible else 0.0


def _summary(
    panel: pd.DataFrame,
    contract: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    gates = contract["stability_gates"]
    counts = panel["HERD_TRANSITION"].value_counts().to_dict()
    unknown_fraction = float((panel["HERD_TRANSITION"] == "UNKNOWN").mean())
    flip_fraction = _opposite_flip_fraction(
        panel, int(contract["observation_contract"]["short_change_weeks"])
    )
    events = panel[panel["TRANSITION_EVENT"]].copy()
    events["year"] = pd.to_datetime(events["signal_date"]).dt.year
    annual = events.groupby(["ticker", "year"]).size()
    median_annual = float(annual.median()) if len(annual) else 0.0
    minimum_rows = (
        gates["primary_minimum_rows"]
        if role == "PRIMARY"
        else gates["independent_minimum_rows"]
    )
    minimum_breaking = (
        gates["primary_minimum_breaking_rows"]
        if role == "PRIMARY"
        else gates["independent_minimum_breaking_rows"]
    )
    minimum_recovering = (
        gates["primary_minimum_recovering_rows"]
        if role == "PRIMARY"
        else gates["independent_minimum_recovering_rows"]
    )
    checks = {
        "minimum_rows": len(panel) >= minimum_rows,
        "maximum_unknown_fraction": unknown_fraction
        <= gates["maximum_unknown_fraction"],
        "minimum_breaking_rows": int(counts.get("BREAKING", 0)) >= minimum_breaking,
        "minimum_recovering_rows": int(counts.get("RECOVERING", 0))
        >= minimum_recovering,
        "maximum_opposite_flip_fraction": flip_fraction
        <= gates["maximum_opposite_flip_within_4_weeks_fraction"],
        "maximum_median_highlighted_events": median_annual
        <= gates["maximum_median_highlighted_events_per_ticker_year"],
    }
    return {
        "role": role,
        "rows": int(len(panel)),
        "tickers": int(panel["ticker"].nunique()),
        "transition_counts": {key: int(value) for key, value in counts.items()},
        "unknown_fraction": unknown_fraction,
        "opposite_flip_within_4_weeks_fraction": flip_fraction,
        "highlighted_transition_events": int(len(events)),
        "median_highlighted_events_per_ticker_year": median_annual,
        "opposite_direction_suppressed": int(
            panel["OPPOSITE_DIRECTION_SUPPRESSED"].sum()
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _write_panel(panel: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.gz")
    panel.to_csv(temporary, index=False, compression="gzip")
    os.replace(temporary, path)


def run(
    contract_path: Path = CONTRACT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT,
    latest_path: Path = DEFAULT_LATEST,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    state_report, panel_paths = _load_state_report(contract)
    summaries = []
    receipts = {}
    latest_parts = []
    for role, state_path in panel_paths.items():
        state_panel = pd.read_csv(
            state_path,
            compression="gzip",
            parse_dates=["signal_date", "last_observed_session"],
        )
        transition_panel = classify_transitions(state_panel, contract)
        path = output_dir / f"{role.lower()}.csv.gz"
        _write_panel(transition_panel, path)
        receipts[role] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": _sha256(path),
            "rows": int(len(transition_panel)),
        }
        summaries.append(_summary(transition_panel, contract, role))
        latest_parts.append(
            transition_panel.sort_values("signal_date").groupby("ticker").tail(1)
        )
    latest = pd.concat(latest_parts, ignore_index=True).sort_values(
        ["universe_role", "ticker"]
    )
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest.to_csv(latest_path, index=False)
    passed = all(summary["passed"] for summary in summaries)
    report = {
        "report_version": "HERD_TRANSITION_S1",
        "status": (
            "TRANSITION_DISPLAY_READY"
            if passed
            else "TRANSITION_STABILITY_GATE_FAILED"
        ),
        "contract_sha256": _sha256(contract_path),
        "state_report_sha256": _sha256(
            _rooted(contract["state_input"]["report"])
        ),
        "state_contract_sha256": state_report["contract_sha256"],
        "panels": receipts,
        "universes": summaries,
        "latest_rows": int(len(latest)),
        "latest_sha256": _sha256(latest_path),
        "future_outcomes_read": False,
        "direction_prediction": False,
        "buy_or_profit_take_authority": False,
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "transition_display_ready": passed,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--latest", type=Path, default=DEFAULT_LATEST)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.contract, args.output_dir, args.report, args.latest),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

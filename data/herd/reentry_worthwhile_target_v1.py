"""경제성 상한 결과에서 미래값이 제거된 재진입 가치 목표 원장을 만든다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
TARGET_PATH = Path(__file__).with_suffix(".json")


def load_target(path: Path = TARGET_PATH) -> dict:
    target = json.loads(path.read_text(encoding="utf-8"))
    if target.get("status") != "LOCKED_AFTER_FEASIBILITY_BEFORE_FEATURE_RESEARCH":
        raise ValueError("reentry worthwhile target must be locked")
    interpretation = target["interpretation"]
    if interpretation.get("label_uses_future_only_as_outcome") is not True \
            or interpretation.get("same_sample_cannot_confirm_discovered_feature") is not True:
        raise ValueError("target leakage boundary is missing")
    return target


def build_target(events: pd.DataFrame, target: dict) -> tuple[pd.DataFrame, dict]:
    required = {"ticker", "episode_id", "signal_date", "path_label", "stress_constrained_available"}
    if not required.issubset(events.columns):
        raise ValueError(f"cycle events missing columns: {sorted(required - set(events.columns))}")
    frame = events.copy()
    worthwhile = frame["stress_constrained_available"].astype(bool)
    hold_winner = ~worthwhile & frame["path_label"].eq("CONTINUATION")
    frame["target_label"] = "EXCLUDED"
    frame.loc[worthwhile, "target_label"] = "REENTRY_WORTHWHILE"
    frame.loc[hold_winner, "target_label"] = "HOLD_WINNER"
    safe = frame[frame["target_label"].ne("EXCLUDED")][target["safe_output_columns"]].copy()
    counts = safe["target_label"].value_counts().to_dict()
    minimum = target["minimum_sample"]
    ready = all(counts.get(label, 0) >= count for label, count in minimum.items())
    report = {
        "report_version": "HERD_REENTRY_WORTHWHILE_TARGET_V1",
        "status": "DISCOVERY_TARGET_READY" if ready else "BLOCKED_INSUFFICIENT_TARGET_SAMPLE",
        "source_events": int(len(frame)),
        "eligible_target_events": int(len(safe)),
        "excluded_events": int(frame["target_label"].eq("EXCLUDED").sum()),
        "label_counts": counts,
        "safe_output_columns": safe.columns.tolist(),
        "future_outcome_columns_exported": False,
        "confirmation_on_same_sample_allowed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }
    return safe, report


def run(target_path: Path = TARGET_PATH) -> tuple[pd.DataFrame, dict]:
    target = load_target(target_path)
    report_path = (ROOT / target["required_feasibility_report"]).resolve()
    source_path = (ROOT / target["source_events"]).resolve()
    for path in (report_path, source_path):
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError("required target source missing or outside repository")
    feasibility = json.loads(report_path.read_text(encoding="utf-8"))
    if feasibility.get("status") != target["required_feasibility_status"]:
        raise ValueError("cycle feasibility gate has not passed")
    safe, report = build_target(pd.read_csv(source_path), target)
    return safe, report | {
        "source_report_version": feasibility["report_version"],
        "research_scope": target["research_scope"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    target, report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    target.to_csv(args.output, index=False)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

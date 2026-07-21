"""통과한 Rush 방향 증거가 있을 때만 최초 5% 부분 익절 사이클을 연다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.rush_confirmation_oos_v1 import evaluate_gate


def evaluate_cycle_gate() -> dict:
    oos = evaluate_gate()
    allowed = oos["direction_evidence_ready"] and bool(oos["passing_hypotheses"])
    return {
        "report_version":"herd-rush-five-percent-cycle-gate-v1",
        "status":"READY_FOR_5_PERCENT_CYCLE" if allowed else "BLOCKED_NO_CONFIRMED_RUSH_DIRECTION_EVIDENCE",
        "passing_hypotheses":oos["passing_hypotheses"],
        "initial_profit_take_fraction":0.05 if allowed else 0.0,
        "maximum_profit_take_fraction":0.15,
        "full_exit_allowed":False,
        "cycle_executed":False,
        "buy_hold_comparison_executed":False,
        "blocked_cycle_is_performance_failure":False,
        "operational_action_ratio":0.0,
        "blind_holdout_access":False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = evaluate_cycle_gate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

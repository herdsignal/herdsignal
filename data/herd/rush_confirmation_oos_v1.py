"""사전등록된 Rush 가설이 없으면 확인구간 OOS 접근을 차단한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.rush_hypothesis_preregistration_v1 import validate_registry


def evaluate_gate() -> dict:
    preregistration = validate_registry()
    allowed = preregistration["confirmation_oos_allowed"]
    return {
        "report_version":"herd-rush-confirmation-oos-v1",
        "status":"READY_FOR_CONFIRMATION_OOS" if allowed else "BLOCKED_NO_PREREGISTERED_HYPOTHESIS",
        "admitted_hypotheses":preregistration["admitted_hypotheses"],
        "confirmation_rows_read":0,
        "oos_tests_executed":0,
        "passing_hypotheses":[],
        "direction_evidence_ready":False,
        "blocked_test_is_performance_failure":False,
        "operational_action_ratio":0.0,
        "blind_holdout_access":False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = evaluate_gate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

"""SEC 가이던스 변화의 독립 OOS를 선행 커버리지 게이트 뒤에서만 실행한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROTOCOL = Path(__file__).with_suffix(".json")


def evaluate(protocol: dict) -> dict:
    pair_report_path = Path(protocol["revision_pair_report"])
    pair_report = json.loads(pair_report_path.read_text(encoding="utf-8"))
    ready = bool(pair_report["pair_coverage_gate_passed"])
    if ready:
        return {
            "report_version": "herd-sec-guidance-direction-oos-v1",
            "pair_coverage_gate_passed": True,
            "price_manifest_opened": False,
            "evaluated_pairs": 0,
            "evaluated_folds": 0,
            "admitted_direction_evidence": 0,
            "decision": "LOCK_PRICE_MANIFEST_BEFORE_OOS",
            "ready_for_herd_combination": False,
            "operational_action_ratio": 0.0,
            "pair_report_sha256": hashlib.sha256(pair_report_path.read_bytes()).hexdigest(),
        }
    return {
        "report_version": "herd-sec-guidance-direction-oos-v1",
        "pair_coverage_gate_passed": False,
        "price_manifest_opened": False,
        "evaluated_pairs": 0,
        "evaluated_folds": 0,
        "admitted_direction_evidence": 0,
        "decision": "OOS_BLOCKED_BY_PAIR_COVERAGE",
        "ready_for_herd_combination": False,
        "operational_action_ratio": 0.0,
        "pair_report_sha256": hashlib.sha256(pair_report_path.read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    report = evaluate(protocol)
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

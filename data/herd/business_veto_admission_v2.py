"""SEC PIT 기업 상태 OOS 결과를 추가매수 veto 권한으로만 엄격히 판정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


PROTOCOL = Path(__file__).with_suffix(".json")


def audit(protocol: dict) -> dict:
    report_path = Path(protocol["business_guard_oos_report"])
    summary_path = Path(protocol["business_guard_oos_summary"])
    source = json.loads(report_path.read_text(encoding="utf-8"))
    summary = pd.read_csv(summary_path)
    passed = (
        source["decision"] == "PASS_TO_ADD_BUY_VETO_ABLATION"
        and source["primary_outcomes_passed"] >= protocol["required_primary_outcomes"]
    )
    return {
        "report_version": "herd-business-veto-admission-v2",
        "source_decision": source["decision"],
        "primary_outcomes_passed": int(source["primary_outcomes_passed"]),
        "primary_outcomes_required": int(protocol["required_primary_outcomes"]),
        "summary_rows_audited": len(summary),
        "business_veto_evidence_admitted": passed,
        "add_buy_veto_ablation_allowed": passed,
        "sell_authority": False,
        "herd_weight_authority": False,
        "new_parser_sample_used_for_oos": False,
        "decision": "ADMIT_ADD_BUY_VETO_ABLATION_ONLY" if passed else "REJECT_BUSINESS_VETO_EVIDENCE",
        "business_guard_oos_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "business_guard_oos_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    report = audit(protocol)
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

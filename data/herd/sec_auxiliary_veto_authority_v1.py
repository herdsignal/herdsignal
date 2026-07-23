"""SEC 계층이 행동 방향으로 새지 않도록 veto 전용 권한을 강제한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROTOCOL = Path(__file__).with_suffix(".json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(protocol: dict) -> dict:
    guidance_path = Path(protocol["guidance_pair_report"])
    business_path = Path(protocol["business_veto_report"])
    guidance = json.loads(guidance_path.read_text())
    business = json.loads(business_path.read_text())
    guidance_ready = bool(
        guidance["pair_coverage_gate_passed"]
        and guidance.get("guidance_veto_oos_passed", False)
    )
    business_ready = bool(business["business_veto_evidence_admitted"])
    enabled = guidance_ready or business_ready
    return {
        "report_version": "herd-sec-auxiliary-veto-authority-v1",
        "guidance_pair_coverage_passed": guidance["pair_coverage_gate_passed"],
        "guidance_independent_oos_passed": guidance.get("guidance_veto_oos_passed", False),
        "guidance_veto_enabled": guidance_ready,
        "business_veto_independent_oos_passed": business_ready,
        "business_veto_enabled": business_ready,
        "effective_sec_veto_enabled": enabled,
        "allowed_runtime_effects": protocol["allowed_authority_on_independent_oos_pass"] if enabled else [],
        "create_buy_authority": False,
        "create_sell_authority": False,
        "herd_weight_authority": False,
        "action_ratio_authority": False,
        "decision": "ENABLE_AUXILIARY_VETO_ONLY" if enabled else "DISABLED_NO_ADMITTED_SEC_VETO",
        "guidance_pair_report_sha256": _sha256(guidance_path),
        "business_veto_report_sha256": _sha256(business_path),
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    report = audit(protocol)
    report["protocol_sha256"] = _sha256(PROTOCOL)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

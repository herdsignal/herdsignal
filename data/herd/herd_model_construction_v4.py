"""가격·가이던스·기업 상태 권한을 합쳐 증거가 있는 HERD 후보만 개방한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROTOCOL = Path(__file__).with_suffix(".json")


def construct(protocol: dict) -> dict:
    reports = {name: json.loads(Path(path).read_text(encoding="utf-8")) for name, path in protocol["required_reports"].items()}
    price = list(reports["price_direction"].get("admitted_direction_features", []))
    guidance_count = int(reports["guidance_direction"].get("admitted_direction_evidence", 0))
    profit_take = bool(reports["profit_take_registry"]["decision"].get("profit_take_evidence_admitted", False))
    direction = [*price]
    if guidance_count:
        direction.append("SEC_GUIDANCE_DIRECTION")
    if profit_take:
        direction.append("PRE_DAMAGE_PROFIT_TAKE")
    veto = bool(reports["business_veto"].get("business_veto_evidence_admitted", False))
    ready = len(direction) >= protocol["minimum_direction_evidence"]
    return {
        "report_version": "HERD_MODEL_CONSTRUCTION_V4",
        "status": "READY_FOR_B0_B5_ABLATION" if ready else "BLOCKED_NO_ADMITTED_DIRECTION_EVIDENCE",
        "admitted_direction_evidence": direction,
        "admitted_business_veto": veto,
        "business_veto_used_as_direction": False,
        "instantiated_candidates": list(protocol["candidate_templates"]) if ready else [],
        "candidate_count": len(protocol["candidate_templates"]) if ready else 0,
        "weights": {},
        "weights_allowed": False,
        "existing_v4_preserved": True,
        "model_promotion_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "input_sha256": {
            name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for name, path in protocol["required_reports"].items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    report = construct(protocol)
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""독립 OOS를 통과한 증거만 차세대 조합 후보로 승격한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROTOCOL = Path(__file__).with_suffix(".json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_gate(protocol: dict, source: dict) -> dict:
    passed = {
        family: list(result.get("passed_measurements", []))
        for family, result in source["families"].items()
        if result.get("decision") == "PASS" and result.get("passed_measurements")
    }
    measurement_count = sum(map(len, passed.values()))
    eligible = (
        len(passed) >= int(protocol["required_passed_families"])
        and measurement_count >= int(protocol["required_passed_measurements"])
    )
    return {
        "registry_version": "herd-expectation-combination-gate-v1",
        "decision": "ELIGIBLE_FOR_PREREGISTERED_COMBINATION" if eligible else "BLOCKED_NO_INDEPENDENT_EVIDENCE",
        "eligible": eligible,
        "admitted_evidence": passed,
        "admitted_family_count": len(passed),
        "admitted_measurement_count": measurement_count,
        "combination_formula": None,
        "research_trim_ratio": protocol["allowed_trim_ratio_if_eligible"] if eligible else 0.0,
        "operational_sell_authority": False,
        "operational_action_ratio": 0.0,
        "reason": (
            "Only independently passed evidence may enter a separately preregistered formula."
            if eligible else
            "No evidence survived the locked independent OOS gate; weighting and score construction are prohibited."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    source_path = Path(protocol["source_report"])
    source = json.loads(source_path.read_text(encoding="utf-8"))
    result = build_gate(protocol, source)
    result.update({"protocol_sha256": _sha256(PROTOCOL), "source_report_sha256": _sha256(source_path)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

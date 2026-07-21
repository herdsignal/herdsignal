"""발견 선택 원장과 Rush 가설 사전등록 목록의 일치를 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).with_suffix(".json")


def validate_registry(path: Path = REGISTRY_PATH) -> dict:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("registry_version") != "HERD_RUSH_HYPOTHESIS_PREREGISTRATION_V1" \
            or registry.get("status") != "LOCKED_AFTER_DISCOVERY_SELECTION":
        raise ValueError("Rush hypothesis registry is not locked")
    selection = json.loads((ROOT / registry["source_report"]).read_text(encoding="utf-8"))
    admitted = [item["feature"] for item in registry["admitted_hypotheses"]]
    if admitted != selection["retained_features"]:
        raise ValueError("preregistered hypotheses differ from discovery admission")
    if any(item["feature"] in admitted for item in registry["research_leads_without_test_authority"]):
        raise ValueError("research lead was promoted without admission")
    return {
        "report_version":"herd-rush-hypothesis-preregistration-v1",
        "status":"NO_HYPOTHESIS_PREREGISTERED" if not admitted else "HYPOTHESES_PREREGISTERED",
        "admitted_hypotheses":admitted,
        "admitted_count":len(admitted),
        "confirmation_oos_allowed":bool(admitted),
        "operational_action_ratio":0.0,
        "blind_holdout_access":False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = validate_registry()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

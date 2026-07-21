"""차세대 HERD 후보 계산식 V2 사전등록 계약을 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.evidence_target_matrix import load_and_validate as load_target_matrix


PROTOCOL_PATH = Path(__file__).with_name("herd_candidate_protocol_v2.json")


def load_and_validate(path: Path = PROTOCOL_PATH) -> tuple[dict, dict]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != "HERD_CANDIDATE_FORMULAS_V2" \
            or protocol.get("status") != "LOCKED_BEFORE_CANDIDATE_FEATURE_RESULTS":
        raise ValueError("candidate formula protocol is not locked")
    matrix, _ = load_target_matrix()
    inventory_candidates = {row["indicator_id"] for row in matrix["rows"]}
    features = protocol["features"]
    feature_ids = {feature["id"] for feature in features}
    if len(feature_ids) != len(features):
        raise ValueError("duplicate candidate feature")
    if any(feature["source_indicator"] not in inventory_candidates and not feature["source_indicator"].startswith("V4_") for feature in features):
        raise ValueError("candidate feature has unknown source indicator")
    hypotheses = protocol["hypotheses"]
    if any(item["feature"] not in feature_ids for item in hypotheses):
        raise ValueError("hypothesis references missing feature")
    if len({item["id"] for item in hypotheses}) != len(hypotheses):
        raise ValueError("duplicate hypothesis")
    if protocol["common"]["one_hypothesis_one_target"] is not True:
        raise ValueError("target isolation was weakened")
    if "LEARN_WEIGHTS_BEFORE_REDUNDANCY_AUDIT" not in protocol["forbidden"]:
        raise ValueError("premature weighting is not forbidden")
    return protocol, {
        "report_version": "herd-candidate-formulas-v2-preregistration",
        "features": len(features), "hypotheses": len(hypotheses),
        "roles": sorted({item["role"] for item in hypotheses}),
        "locked_before_results": True, "weights_allowed": False,
        "operational_actions_allowed": False
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    _, report = load_and_validate()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

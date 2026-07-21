"""HERD 모델 계보 계약이 실제 소스와 역할 경계를 유지하는지 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")


def validate_contract(path: Path = CONTRACT_PATH) -> dict:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != "HERD_MODEL_LINEAGE_V1" \
            or contract.get("status") != "LOCKED_FROM_CURRENT_CODE":
        raise ValueError("model lineage contract is not locked")
    checked = []
    for layer in contract["layers"]:
        source = (ROOT / layer["source"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise ValueError(f"missing model source: {layer['source']}")
        text = source.read_text(encoding="utf-8")
        missing = [symbol for symbol in layer["source_symbols"] if symbol not in text]
        if missing:
            raise ValueError(f"missing symbols in {layer['id']}: {missing}")
        checked.append(layer["id"])
    boundaries = contract["boundaries"]
    if any(boundaries[key] for key in (
        "personal_profile_is_part_of_objective_herd",
        "portfolio_context_is_part_of_objective_herd",
        "cooldown_is_direction_evidence",
        "price_rush_episode_is_sell_signal",
        "v61_action_layer_recalculates_v4_score",
    )):
        raise ValueError("model role boundary was violated")
    if boundaries["unapproved_research_action_ratio"] != 0.0:
        raise ValueError("unapproved action ratio must fail closed")
    return {
        "report_version":"herd-model-lineage-v1",
        "status":"MODEL_ROLES_VERIFIED",
        "verified_layers":checked,
        "verified_layer_count":len(checked),
        "operational_state_model":"HERD_V4_STATE",
        "research_action_model":"HERD_V61_ACTION_LAYER",
        "research_sample_selector":"PRICE_RUSH_EPISODE_V2",
        "operational_action_ratio":0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = validate_contract()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

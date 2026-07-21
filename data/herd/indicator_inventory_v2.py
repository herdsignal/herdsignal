"""HERD 운영·파생·안전·연구 지표 인벤토리 V2를 검증하고 보고서로 만든다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from config.settings import HERD_WEIGHTS


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).with_name("indicator_inventory_v2.json")
REQUIRED_V4 = {
    "V4_MONTHLY_RSI", "V4_WEEKLY_RSI", "V4_52W_POSITION", "V4_MA200_DEVIATION",
    "V4_VOLUME_STRENGTH", "V4_MA200_WEEKLY", "V4_EPS_MULTIPLIER", "V4_SECTOR_MULTIPLIER"
}
WEIGHT_MAP = {
    "V4_MONTHLY_RSI": "monthly_rsi", "V4_WEEKLY_RSI": "weekly_rsi",
    "V4_52W_POSITION": "52w_position", "V4_MA200_DEVIATION": "ma200_deviation",
    "V4_VOLUME_STRENGTH": "volume_strength", "V4_MA200_WEEKLY": "ma200_weekly"
}
ALLOWED_AUTHORITIES = {
    "NONE", "LEGACY_SCORE_ONLY", "ACTION_CONTEXT_ONLY", "ACTION_SIZE_ONLY",
    "VETO_ONLY", "ACTION_INTENSITY_CAP_ONLY", "OBSERVATION_CANDIDATE_ONLY"
}


def load_and_audit(path: Path = REGISTRY_PATH) -> tuple[dict, dict]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("inventory_version") != "HERD_INDICATOR_INVENTORY_V2" \
            or registry.get("status") != "AUDITED_NOT_ADOPTED":
        raise ValueError("indicator inventory V2 is not auditable")
    items = registry.get("indicators", [])
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)) or not REQUIRED_V4.issubset(ids):
        raise ValueError("indicator inventory has duplicates or missing v4 inputs")
    missing_sources = []
    missing_symbols = []
    for item in items:
        source = ROOT / item["source_path"]
        if not source.is_file():
            missing_sources.append(item["id"])
            continue
        if item["source_symbol"] not in source.read_text(encoding="utf-8"):
            missing_symbols.append(item["id"])
        if item["authority"] not in ALLOWED_AUTHORITIES:
            raise ValueError(f"invalid authority: {item['id']}")
    if missing_sources or missing_symbols:
        raise ValueError(f"inventory source mismatch: files={missing_sources}, symbols={missing_symbols}")
    for item in items:
        key = WEIGHT_MAP.get(item["id"])
        if key is not None and item["current_weight"] != HERD_WEIGHTS[key]:
            raise ValueError(f"operational weight drift: {item['id']}")
    layers = Counter(item["layer"] for item in items)
    authorities = Counter(item["authority"] for item in items)
    duplicate_groups = Counter(item["duplicate_group"] for item in items if item["duplicate_group"] != "NONE")
    report = {
        "report_version": "herd-indicator-inventory-v2-audit",
        "inventory_items": len(items), "layers": dict(sorted(layers.items())),
        "authorities": dict(sorted(authorities.items())),
        "duplicate_groups_with_multiple_items": {
            key: value for key, value in sorted(duplicate_groups.items()) if value > 1
        },
        "operational_v4_weight_sum": sum(HERD_WEIGHTS.values()),
        "research_candidates_with_direction_authority": [
            item["id"] for item in items
            if item["layer"] == "RESEARCH_CANDIDATE" and item["authority"] not in {"NONE", "OBSERVATION_CANDIDATE_ONLY", "ACTION_INTENSITY_CAP_ONLY"}
        ],
        "inventory_complete": True,
        "model_components_selected": False,
        "weights_selected": False
    }
    return registry, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    registry, report = load_and_audit()
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(registry["indicators"]).to_csv(args.csv, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

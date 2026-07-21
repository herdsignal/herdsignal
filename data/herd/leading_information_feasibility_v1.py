"""신규 선행정보 후보의 PIT·역사·라이선스 가능성을 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROTOCOL = Path(__file__).with_suffix(".json")
PRIMARY = "PRIMARY_CANDIDATE"


def audit(protocol: dict) -> dict:
    sources = protocol["sources"]
    ids = [source["id"] for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source id")
    by_id = {source["id"]: source for source in sources}
    for source_id in protocol["next_collection_order"]:
        if source_id not in by_id:
            raise ValueError(f"unknown collection source: {source_id}")
    primary = [source["id"] for source in sources if source["research_role"] == PRIMARY]
    blocked = [source["id"] for source in sources if source["research_role"] == "DATA_BLOCKED"]
    rejected = [source["id"] for source in sources if source["research_role"].startswith("REJECTED")]
    return {
        "report_version": "herd-leading-information-feasibility-v1",
        "decision": "COLLECT_PUBLIC_SEC_FIRST",
        "primary_collectable_sources": primary,
        "context_or_exploratory_sources": [
            source["id"] for source in sources
            if source["research_role"] in {"CONTEXT_ONLY", "EXPLORATORY_RECENT_LANE"}
        ],
        "data_blocked_sources": blocked,
        "rejected_proxy_sources": rejected,
        "next_implementation": "SEC_8K_EARNINGS_GUIDANCE_PIT_CORPUS",
        "herd_formula_change_allowed": False,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
        "reason": (
            "Current price and periodic-fundamental panel observes confirmation mostly after expectations are priced; "
            "SEC event documents are the first public source with an auditable availability timestamp and genuinely new content."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    result = audit(protocol)
    result["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

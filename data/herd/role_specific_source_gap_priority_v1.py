"""미연결 판단 역할의 다음 데이터 작업을 중단·수집·보류·보강으로 나눈다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
REPORT = ROOT / "data/reports/role_specific_source_gap_priority_v1.json"


class SourceGapPriorityError(ValueError):
    """Raised when a rejected or missing source is accidentally promoted."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs(protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for item in protocol["inputs"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise SourceGapPriorityError(f"missing or unsafe input: {item['path']}")
        if _sha256(path) != item["sha256"]:
            raise SourceGapPriorityError(f"input hash changed: {item['path']}")
        loaded[item["id"]] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def audit(protocol_path: Path = PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_PRIORITY_AUDIT":
        raise SourceGapPriorityError("source priority protocol is not locked")
    if protocol["authority"]["operational_action_ratio"] != 0.0:
        raise SourceGapPriorityError("source priority cannot authorize an action")
    inputs = _load_inputs(protocol)

    sec8k = inputs["SEC_8K"]
    form4 = inputs["FORM4"]
    finra = inputs["FINRA"]
    sec13f = inputs["SEC_13F"]
    runtime = inputs["RUNTIME_INFORMATION"]
    if form4["result"]["passed"] or "REJECT" not in form4["status"]:
        raise SourceGapPriorityError("Form 4 rejection boundary changed")
    if sec13f["decision"] != "KEEP_13F_AS_NON_DIRECTIONAL_CONTEXT_ONLY":
        raise SourceGapPriorityError("13F rejection boundary changed")
    if runtime["sources"]["POINT_IN_TIME_NEWS"] != "NOT_CONNECTED":
        raise SourceGapPriorityError("PIT news was connected without a source contract")
    if sec8k["direction_hypothesis_allowed"]:
        raise SourceGapPriorityError("pending SEC identity review opened direction research")

    decisions = [
        {
            "source": "SEC_MATERIAL_EVENT",
            "decision": "BOUNDED_MANUAL_SOURCE_REVIEW_NEXT",
            "product_role": "FUTURE_CORPORATE_DAMAGE_VETO_INPUT",
            "coverage": {
                "candidate_rows": sec8k["candidate_rows"],
                "reviewed_rows": sec8k["reviewed_rows"],
                "pending_rows": sec8k["decision_counts"].get("PENDING", 0),
            },
            "direction_vote": False,
            "reason": "Official filing evidence and a finite review queue exist; completion improves identity safety but does not predict profit-taking."
        },
        {
            "source": "FINRA_SHORT_INTEREST",
            "decision": "CONTINUE_APPEND_ONLY_SHADOW",
            "product_role": "FUTURE_POSITIONING_CONTEXT_CANDIDATE",
            "coverage": {
                "settlement_dates": finra["settlement_date_count"],
                "last_settlement_date": finra["last_settlement_date"],
                "status": finra["status"],
            },
            "direction_vote": False,
            "reason": "Official PIT collection exists but historical depth and prospective outcomes are not mature."
        },
        {
            "source": "POINT_IN_TIME_NEWS",
            "decision": "DEFER_UNTIL_SOURCE_RIGHTS_AND_VERSION_CONTRACT",
            "product_role": "NONE",
            "coverage": {"connected": False},
            "direction_vote": False,
            "reason": "No immutable article ledger with publication time, corrections, identity, and usage rights is connected."
        },
        {
            "source": "SEC_FORM4",
            "decision": "STOP_DIRECTION_RESEARCH_PRESERVE_CONTEXT",
            "product_role": "REJECTED_RESEARCH_CONTEXT_ONLY",
            "coverage": {
                "episodes": form4["result"]["episodes"],
                "tickers": form4["result"]["tickers"],
                "feature_positive_episodes": form4["result"]["feature_positive_episodes"],
            },
            "direction_vote": False,
            "reason": "The locked hypothesis failed robustness; same-sample retuning is prohibited."
        },
        {
            "source": "SEC_13F",
            "decision": "STOP_DIRECTION_RESEARCH_PRESERVE_DELAYED_CONTEXT",
            "product_role": "DELAYED_CONTEXT_ONLY",
            "coverage": {
                "test_rows": sec13f["folds"]["test_rows"],
                "test_tickers": sec13f["folds"]["test_tickers"],
                "incremental_roc_auc": sec13f["aggregate_metrics"]["incremental_roc_auc"],
            },
            "direction_vote": False,
            "reason": "The delayed holdings hypothesis failed its fixed OOS gates and cannot represent current positions."
        }
    ]
    if any(row["direction_vote"] for row in decisions):
        raise SourceGapPriorityError("source prioritization admitted a direction vote")
    return {
        "report_version": "HERD_ROLE_SPECIFIC_SOURCE_GAP_PRIORITY_V1",
        "status": "SOURCE_GAPS_PRIORITIZED_NO_DIRECTION_SOURCE_READY",
        "protocol_sha256": _sha256(protocol_path),
        "decisions": decisions,
        "summary": {
            "direction_ready_sources": 0,
            "bounded_manual_review_sources": 1,
            "prospective_collection_only_sources": 1,
            "deferred_sources": 1,
            "stopped_direction_sources": 2,
        },
        "selected_next_part": {
            "id": "SEC_8K_MATERIAL_EVENT_REVIEW_BATCHING",
            "purpose": "Make the 110-row official-source review executable in small deterministic batches.",
            "may_create_profit_take_direction": False,
            "may_enable_operational_action": False,
        },
        "new_hypothesis_allowed": False,
        "operational_action": "OBSERVE",
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    report = audit(args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

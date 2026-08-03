"""장기 운용 검토 역할별 데이터·coverage·권한 경계를 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
REPORT = ROOT / "data/reports/independent_evidence_role_audit_v1.json"


class EvidenceRoleAuditError(ValueError):
    """Raised when a role receives unsupported evidence or authority."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs(protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for item in protocol.get("inputs", []):
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise EvidenceRoleAuditError(f"missing or unsafe input: {item['path']}")
        if _sha256(path) != item.get("sha256"):
            raise EvidenceRoleAuditError(f"input hash changed: {item['path']}")
        loaded[item["id"]] = json.loads(path.read_text(encoding="utf-8"))
    if len(loaded) != 14:
        raise EvidenceRoleAuditError("role audit input set is incomplete")
    return loaded


def _role_results(inputs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    guidance = inputs["GUIDANCE_BINDINGS"]
    form4 = inputs["FORM4_OOS"]
    finra = inputs["FINRA_INCREMENTAL"]
    sec8k = inputs["SEC_8K_REVIEW"]
    return {
        "MARKET_TAPE": {
            "status": "ACTIVE_CONTEXT_ONLY",
            "coverage": "RUNTIME_SYMBOL_AND_SECTOR_PRICE_AVAILABILITY",
            "claim": "REALIZED_MARKET_SECTOR_AND_STOCK_PATH_ATTRIBUTION",
            "directional_vote": False,
        },
        "CHART_CROWD": {
            "status": inputs["CHART_CROWD"]["status"],
            "coverage": "STATE_S1_SUPPORTED_UNIVERSE",
            "claim": "CURRENT_FLEE_TO_RUSH_STATE",
            "directional_vote": False,
        },
        "BUSINESS_FUNDAMENTALS": {
            "status": "PARTIAL_OBSERVATION",
            "coverage": "SUPPORTED_GENERAL_ISSUER_WHEN_PIT_FACTS_EXIST",
            "claim": "SIX_RAW_PIT_FINANCIAL_MEASUREMENTS",
            "directional_vote": False,
        },
        "MANAGEMENT_EXPECTATIONS": {
            "status": "PARTIAL_FACT_ONLY_DIRECTION_REJECTED",
            "coverage": {
                "valid_atomic_facts": guidance["valid_rows_promoted"],
                "tickers": guidance["distinct_tickers"],
                "accessions": guidance["distinct_accessions"],
            },
            "claim": "SOURCE_REVIEWED_GUIDANCE_FACT_WITHOUT_UP_DOWN_LABEL",
            "directional_vote": False,
        },
        "MATERIAL_EVENTS_AND_NEWS": {
            "status": "NO_VIEW_IDENTITY_REVIEW_AND_NEWS_LEDGER_MISSING",
            "coverage": {
                "sec_8k_candidates": sec8k["candidate_rows"],
                "sec_8k_reviewed": sec8k["reviewed_rows"],
                "pit_news_connected": False,
            },
            "claim": "SOURCE_STATUS_ONLY",
            "directional_vote": False,
        },
        "INSIDER_BEHAVIOR": {
            "status": form4["status"],
            "coverage": {
                "owner_purchase_events": form4["owner_purchase_events"],
                "issuers": form4["owner_purchase_event_issuers"],
            },
            "claim": "REJECTED_RESEARCH_CONTEXT_ONLY",
            "directional_vote": False,
        },
        "SHORT_INTEREST": {
            "status": "PROSPECTIVE_SHADOW_ONLY",
            "coverage": {
                "settlement_dates": finra["settlement_date_count"],
                "last_settlement_date": finra["last_settlement_date"],
                "publication_status": finra["status"],
            },
            "claim": "POINT_IN_TIME_COLLECTION_STATUS_ONLY",
            "directional_vote": False,
        },
        "INSTITUTIONAL_HOLDINGS": {
            "status": "DELAYED_CONTEXT_DIRECTION_REJECTED",
            "coverage": inputs["SEC_13F_OOS"]["panel"],
            "claim": "QUARTERLY_DELAYED_CONTEXT_ONLY",
            "directional_vote": False,
        },
        "PORTFOLIO_FIT": {
            "status": inputs["PORTFOLIO_CONTEXT"]["status"],
            "coverage": "CURRENT_USER_PORTFOLIO_WHEN_AVAILABLE",
            "claim": "RAW_WEIGHT_AND_EQUITY_TARGET_GAP_ONLY",
            "directional_vote": False,
        },
        "INDEPENDENT_RISK_REVIEW": {
            "status": inputs["AI_REVIEW"]["status"],
            "coverage": "SOURCE_GROUNDED_EVIDENCE_PACKET_WHEN_ENABLED",
            "claim": "COUNTER_REVIEW_SUMMARY_ONLY",
            "directional_vote": False,
        },
    }


def audit(protocol_path: Path = PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_ROLE_AUDIT":
        raise EvidenceRoleAuditError("role audit protocol is not locked")
    if protocol.get("authority", {}).get("operational_action_ratio") != 0.0:
        raise EvidenceRoleAuditError("role audit cannot have action authority")
    inputs = _load_inputs(protocol)
    if inputs["FAILURE_SYNTHESIS"]["next_stage"]["new_hypothesis_allowed"]:
        raise EvidenceRoleAuditError("role audit cannot bypass failure synthesis")
    if inputs["GUIDANCE_OOS"]["adoption_gate_passed"]:
        raise EvidenceRoleAuditError("rejected guidance direction was promoted")
    if inputs["SEC_13F_OOS"]["decision"] != "KEEP_13F_AS_NON_DIRECTIONAL_CONTEXT_ONLY":
        raise EvidenceRoleAuditError("13F role boundary changed")
    if inputs["INFORMATION_CONTEXT"]["sources"]["POINT_IN_TIME_NEWS"] != "NOT_CONNECTED":
        raise EvidenceRoleAuditError("unreviewed PIT news source became connected")

    role_definitions = {row["id"]: row for row in protocol["roles"]}
    results = _role_results(inputs)
    if set(role_definitions) != set(results):
        raise EvidenceRoleAuditError("role definitions and results differ")
    directional_votes = sum(bool(row["directional_vote"]) for row in results.values())
    price_roles = [
        role_id
        for role_id, definition in role_definitions.items()
        if definition["information_domain"] == "REALIZED_PRICE"
    ]
    if directional_votes:
        raise EvidenceRoleAuditError("no role has admitted direction evidence")

    return {
        "report_version": "HERD_INDEPENDENT_EVIDENCE_ROLE_AUDIT_V1",
        "status": "ROLE_AUDIT_COMPLETE_CONTEXT_ONLY",
        "protocol_sha256": _sha256(protocol_path),
        "roles": [
            {**role_definitions[role_id], **result}
            for role_id, result in results.items()
        ],
        "summary": {
            "role_count": len(results),
            "directional_vote_roles": directional_votes,
            "price_domain_roles": price_roles,
            "price_domain_vote_count": 0,
            "pit_news_connected": False,
            "final_action_synthesis_enabled": False,
        },
        "architecture_decision": {
            "keep_independent_roles": True,
            "call_roles_ai_agents": False,
            "majority_vote_allowed": False,
            "deterministic_fail_closed_synthesis_only": True,
            "current_name": "LONG_TERM_OPERATING_REVIEW",
            "next_stage": "ROLE_SPECIFIC_SOURCE_GAPS_AND_RUNTIME_PACKET_AUDIT",
        },
        "blind_holdout_access": False,
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

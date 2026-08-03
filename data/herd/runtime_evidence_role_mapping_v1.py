"""연구 역할과 실제 런타임 Evidence Packet의 연결 경계를 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
REPORT = ROOT / "data/reports/runtime_evidence_role_mapping_v1.json"


class RuntimeRoleMappingError(ValueError):
    """Raised when runtime wiring violates a locked role boundary."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_file(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise RuntimeRoleMappingError(f"missing or unsafe runtime source: {relative}")
    return path


def audit(protocol_path: Path = PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_RUNTIME_AUDIT":
        raise RuntimeRoleMappingError("runtime mapping protocol is not locked")
    invariants = protocol.get("invariants", {})
    if invariants.get("operational_action_ratio") != 0.0:
        raise RuntimeRoleMappingError("runtime role audit cannot have action authority")

    role_report_path = _safe_file(protocol["input"]["path"])
    if _sha256(role_report_path) != protocol["input"].get("sha256"):
        raise RuntimeRoleMappingError("independent role audit hash changed")
    role_report = json.loads(role_report_path.read_text(encoding="utf-8"))
    research_roles = {row["id"] for row in role_report["roles"]}
    runtime_roles = {row["id"] for row in protocol["roles"]}
    if research_roles != runtime_roles or len(runtime_roles) != 10:
        raise RuntimeRoleMappingError("research and runtime role sets differ")

    sources = {
        relative: _safe_file(relative).read_text(encoding="utf-8")
        for relative in protocol["runtime_sources"]
    }
    all_source = "\n".join(sources.values())
    for role in protocol["roles"]:
        for marker in role["required_markers"]:
            if marker not in all_source:
                raise RuntimeRoleMappingError(
                    f"runtime marker missing for {role['id']}: {marker}"
                )

    objective = sources[
        "backend/src/main/java/com/herdsignal/service/decision/ObjectiveEvidenceService.java"
    ]
    personal = sources[
        "backend/src/main/java/com/herdsignal/service/decision/LongTermOperatingReviewService.java"
    ]
    information = sources[
        "backend/src/main/java/com/herdsignal/service/decision/InformationChangeEvidenceAssembler.java"
    ]
    ai_service = sources[
        "backend/src/main/java/com/herdsignal/service/EvidenceReviewService.java"
    ]
    ai_gateway = sources[
        "backend/src/main/java/com/herdsignal/service/OpenAiEvidenceReviewGateway.java"
    ]
    synthesis = sources[
        "backend/src/main/java/com/herdsignal/service/decision/DecisionSynthesisPolicy.java"
    ]

    if "PortfolioFitCalculator" in objective or "PortfolioActionContext" in objective:
        raise RuntimeRoleMappingError("private portfolio leaked into objective packet")
    if "PortfolioFitCalculator" not in personal or "PortfolioActionContext" not in personal:
        raise RuntimeRoleMappingError("personal portfolio layer is not connected after objective review")
    if "PORTFOLIO_FIT" in ai_service or "PORTFOLIO_FIT" in ai_gateway:
        raise RuntimeRoleMappingError("private portfolio area leaked into AI review")
    if "EvidenceQuality.NO_VIEW" not in information:
        raise RuntimeRoleMappingError("unavailable information sources are not fail-closed")
    if '"HOLD"' not in ai_service or "BigDecimal.ZERO" not in ai_service:
        raise RuntimeRoleMappingError("AI review does not force HOLD 0%")
    compact_ai_schema = ai_gateway.replace(" ", "")
    if '"enum":[false]' not in compact_ai_schema:
        raise RuntimeRoleMappingError("AI schema does not lock directionPrediction false")
    if '"enum":[0]' not in compact_ai_schema:
        raise RuntimeRoleMappingError("AI schema does not lock action ratio zero")
    if '"OBSERVE", 0.0' not in synthesis:
        raise RuntimeRoleMappingError("deterministic synthesis is not fail-closed")

    status_only = [
        role["id"] for role in protocol["roles"]
        if role["connection"] == "CONNECTED_STATUS_ONLY"
    ]
    objective_fact_roles = [
        role["id"] for role in protocol["roles"]
        if role["connection"] == "CONNECTED_OBJECTIVE_FACT"
    ]
    ai_lenses = list(dict.fromkeys(
        role["ai_lens"] for role in protocol["roles"] if role["ai_lens"]
    ))
    return {
        "report_version": "HERD_RUNTIME_EVIDENCE_ROLE_MAPPING_V1",
        "status": "RUNTIME_MAPPING_COMPLETE_FAIL_CLOSED",
        "protocol_sha256": _sha256(protocol_path),
        "role_count": len(runtime_roles),
        "objective_fact_roles": objective_fact_roles,
        "status_only_roles": status_only,
        "private_after_objective_roles": ["PORTFOLIO_FIT"],
        "dual_layer_risk_roles": ["INDEPENDENT_RISK_REVIEW"],
        "ai_lenses": ai_lenses,
        "directional_vote_roles": 0,
        "runtime_gaps": [
            {
                "id": "PIT_INFORMATION_SOURCES_NOT_ADMITTED",
                "roles": status_only,
                "severity": "EXPECTED_BLOCK",
                "action": "Keep NO_VIEW until one source independently passes admission."
            },
            {
                "id": "INFORMATION_CHANGE_AREA_COLLAPSES_FOUR_SOURCE_ROLES",
                "roles": status_only,
                "severity": "FUTURE_SPLIT_REQUIRED",
                "action": "Split the admitted source into its own DecisionArea before it can provide facts or a lens."
            }
        ],
        "architecture_decision": {
            "current_runtime_name": "LONG_TERM_OPERATING_REVIEW",
            "committee_or_agent_label_allowed": False,
            "deterministic_synthesis_remains_authoritative": True,
            "portfolio_sent_to_ai": False,
            "next_stage": "ROLE_SPECIFIC_SOURCE_GAP_PRIORITIZATION"
        },
        "new_hypothesis_allowed": False,
        "operational_action": "OBSERVE",
        "operational_action_ratio": 0.0
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

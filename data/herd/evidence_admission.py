"""OOS 결과를 근거 역할별 다음 단계 권한으로 변환한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).with_name("evidence_admission_registry.json")
REGISTRY_VERSION = "HERD_EVIDENCE_ADMISSION_V1"
EXPECTED_FAMILIES = {
    "PRICE_EXTENSION",
    "TREND_MATURITY",
    "PARTICIPATION",
    "RELATIVE_OVERHEAT",
    "MARKET_RISK",
    "BUSINESS_GUARD",
}
ACTION_TYPES = {"NEW_ENTRY", "ADD_BUY", "PROFIT_TAKE", "REENTRY"}
EXPECTED_ACTION_HYPOTHESES = {
    "ENTRY_TREND_RESUMPTION",
    "ADD_BUY_MARKET_SECTOR_DISLOCATION",
    "PROFIT_TAKE_VOLATILITY_EXTENSION",
    "PROFIT_TAKE_TREND_DECELERATION",
    "PROFIT_TAKE_RELATIVE_STRENGTH_BREAK",
    "REENTRY_POST_PROFIT_STABILIZATION",
}


class EvidenceAdmissionError(RuntimeError):
    """탈락 또는 역할 제한 증거가 허용되지 않은 단계로 진입할 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_file(relative_path: str) -> Path:
    path = (REPOSITORY_ROOT / relative_path).resolve()
    if not path.is_relative_to(REPOSITORY_ROOT) or not path.is_file():
        raise EvidenceAdmissionError(f"invalid source report: {relative_path}")
    return path


def validate_registry(registry: dict) -> dict:
    if (
        registry.get("registry_version") != REGISTRY_VERSION
        or registry.get("status") != "POST_OOS_DECISIONS_LOCKED"
    ):
        raise EvidenceAdmissionError("evidence admission registry is not locked")

    for source in registry.get("source_reports", []):
        if _sha256(_source_file(source["path"])) != source["sha256"]:
            raise EvidenceAdmissionError(f"source report hash mismatch: {source['path']}")

    families = registry.get("families", [])
    family_ids = {family.get("id") for family in families}
    if family_ids != EXPECTED_FAMILIES or len(families) != len(family_ids):
        raise EvidenceAdmissionError("evidence families are missing or duplicated")

    directional = [
        family for family in families if family.get("direction_authorized") is True
    ]
    action_authorizations = {action: 0 for action in ACTION_TYPES}
    for family in families:
        actions = family.get("authorized_actions", [])
        if len(actions) != len(set(actions)) or not set(actions).issubset(ACTION_TYPES):
            raise EvidenceAdmissionError(f"invalid action permission: {family['id']}")
        if actions and family.get("direction_authorized") is not True:
            raise EvidenceAdmissionError(
                f"action permission requires direction evidence: {family['id']}"
            )
        for action in actions:
            action_authorizations[action] += 1
    market_risk = next(family for family in families if family["id"] == "MARKET_RISK")
    if (
        market_risk.get("decision") != "PASS_STOCK_DOWNSIDE_COMPONENT_ONLY"
        or market_risk.get("role") != "ACTION_INTENSITY_CAP"
        or market_risk.get("allowed_next_step") != "CAP_ABLATION_ONLY"
        or market_risk.get("direction_authorized") is not False
    ):
        raise EvidenceAdmissionError("market risk exceeded its validated role")

    state = registry.get("candidate_state", {})
    if state.get("direction_family_count") != len(directional):
        raise EvidenceAdmissionError("direction family count is inconsistent")
    if not directional and state.get("herd_next_composition_allowed") is not False:
        raise EvidenceAdmissionError("HERD composition requires directional evidence")
    if (
        state.get("profit_take_cycle_allowed") is not False
        or state.get("reentry_cycle_allowed") is not False
        or state.get("operational_action_ratio") != 0.0
    ):
        raise EvidenceAdmissionError("unvalidated action cycle was authorized")

    rush = next(
        hypothesis
        for hypothesis in registry.get("composite_hypotheses", [])
        if hypothesis.get("id") == "RUSH_TURNING_POINT"
    )
    if (
        rush.get("decision") != "REJECT_CURRENT_MEASUREMENT"
        or rush.get("profit_take_authorized") is not False
    ):
        raise EvidenceAdmissionError("rejected Rush evidence was re-enabled")

    action_hypotheses = registry.get("action_hypotheses", [])
    if (
        {row.get("id") for row in action_hypotheses}
        != EXPECTED_ACTION_HYPOTHESES
        or any(row.get("action") not in ACTION_TYPES for row in action_hypotheses)
    ):
        raise EvidenceAdmissionError("action direction decisions are incomplete")
    if any(row.get("authorized") is not False for row in action_hypotheses):
        raise EvidenceAdmissionError("failed or blocked action evidence was authorized")
    action_report = json.loads(
        _source_file("data/reports/action_direction_oos_v1.json").read_text(
            encoding="utf-8"
        )
    )
    locked_decisions = {
        row["id"]: row["decision"] for row in action_hypotheses
    }
    if locked_decisions != action_report.get("decisions"):
        raise EvidenceAdmissionError("action direction decision does not match OOS report")
    if (
        action_report.get("operational_authorization") is not False
        or action_report.get("blind_holdout_access") is not False
    ):
        raise EvidenceAdmissionError("action OOS report exceeded research authority")

    return {
        "registry_version": REGISTRY_VERSION,
        "family_count": len(families),
        "direction_family_count": len(directional),
        "action_authorizations": action_authorizations,
        "action_hypothesis_authorizations": {
            action: sum(
                row["authorized"] is True
                for row in action_hypotheses if row["action"] == action
            )
            for action in ACTION_TYPES
        },
        "cap_ablation_families": [
            family["id"]
            for family in families
            if family.get("allowed_next_step") == "CAP_ABLATION_ONLY"
        ],
        "herd_next_composition_allowed": state["herd_next_composition_allowed"],
        "operational_action_ratio": state["operational_action_ratio"],
    }


def load_registry(path: Path = REGISTRY_PATH) -> tuple[dict, dict]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    return registry, validate_registry(registry)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    args = parser.parse_args()
    _, audit = load_registry(args.registry)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

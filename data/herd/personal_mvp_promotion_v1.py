"""현재 증거로 개인 MVP에 허용할 기능과 차단할 행동을 판정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from herd.herd_state_s1 import ROOT


CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_REPORT = ROOT / "data/reports/personal_mvp_promotion_v1.json"


class PersonalMvpPromotionError(RuntimeError):
    """승격 입력·해시·안전 경계가 유효하지 않을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise PersonalMvpPromotionError(f"missing promotion input: {relative}")
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != "HERD_PERSONAL_MVP_PROMOTION_V1"
        or contract.get("status") != "LOCKED_STATE_AND_ACTION_BOUNDARY"
    ):
        raise PersonalMvpPromotionError("personal MVP contract is not locked")
    output = contract["fail_closed_output"]
    if (
        output["default_action"] != "HOLD"
        or output["operational_action_ratio"] != 0.0
        or output["full_exit_allowed"]
        or output["leverage_allowed"]
        or output["blind_holdout_access"]
    ):
        raise PersonalMvpPromotionError("fail-closed boundary was weakened")
    for specification in contract["inputs"].values():
        input_path = _rooted(specification["path"])
        if _sha256(input_path) != specification["sha256"]:
            raise PersonalMvpPromotionError(
                f"pinned promotion input changed: {specification['path']}"
            )
    return contract


def _load_report(specification: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        _rooted(specification["path"]).read_text(encoding="utf-8")
    )


def decide(contract: dict[str, Any]) -> dict[str, Any]:
    state = _load_report(contract["inputs"]["state_report"])
    transition = _load_report(contract["inputs"]["transition_report"])
    economic = _load_report(contract["inputs"]["economic_report"])
    economic_statuses = {
        contract["inputs"]["economic_report"]["passing_status"],
        contract["inputs"]["economic_report"]["current_status"],
    }
    if economic.get("status") not in economic_statuses:
        raise PersonalMvpPromotionError("unknown economic evaluation status")
    state_ready = (
        state.get("status")
        == contract["inputs"]["state_report"]["required_status"]
        and state.get("operational_action_ratio") == 0.0
        and state.get("future_outcomes_read") is False
    )
    transition_ready = (
        transition.get("status")
        == contract["inputs"]["transition_report"]["required_status"]
        and transition.get("operational_action_ratio") == 0.0
        and transition.get("future_outcomes_read") is False
    )
    economic_passed = (
        economic.get("status")
        == contract["inputs"]["economic_report"]["passing_status"]
        and economic.get("passed") is True
    )
    action_ready = (
        economic_passed
        and economic.get("blind_holdout_access") is True
        and economic.get("survivorship_safe") is True
    )
    state_mvp_ready = state_ready and transition_ready
    blockers = []
    if not state_ready:
        blockers.append("HERD_STATE_S1_NOT_READY")
    if not transition_ready:
        blockers.append("HERD_TRANSITION_S1_NOT_READY")
    if not economic_passed:
        blockers.append("PERSONAL_POLICY_PREHOLDOUT_FAILED")
    if not economic.get("blind_holdout_access"):
        blockers.append("BLIND_HOLDOUT_NOT_PASSED")
    if not economic.get("survivorship_safe"):
        blockers.append("SURVIVORSHIP_SAFE_FALSE")
    return {
        "report_version": "HERD_PERSONAL_MVP_PROMOTION_V1",
        "status": (
            "STATE_OBSERVATION_MVP_READY"
            if state_mvp_ready
            else "PERSONAL_MVP_BLOCKED"
        ),
        "decision": (
            "NO_ADOPTABLE_ACTION_CANDIDATE"
            if not action_ready
            else "ACTION_CANDIDATE_REQUIRES_EXPLICIT_APPROVAL"
        ),
        "model_family": "HERD_STATE_S1",
        "lifecycle": "PERSONAL_RESEARCH_MVP",
        "state_observation_ready": state_ready,
        "transition_observation_ready": transition_ready,
        "action_candidate_ready": action_ready,
        "action_model_status": economic.get("status"),
        "allowed_scope": contract["allowed_personal_mvp_scope"],
        "blocked_scope": contract["blocked_scope"],
        "default_action": "HOLD",
        "operational_action_ratio": 0.0,
        "user_action_suppressed": True,
        "herd_state_role": "HERD_STATE_S1_OBSERVATION",
        "historical_role": "PRE_HOLDOUT_RESEARCH_ONLY",
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "prospective_shadow_status": "ACTION_SHADOW_BLOCKED_POLICY_FAILED",
        "promotion_blockers": blockers,
    }


def run(
    contract_path: Path = CONTRACT_PATH,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    report = decide(contract)
    report["contract_sha256"] = _sha256(contract_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    print(json.dumps(run(args.contract, args.report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

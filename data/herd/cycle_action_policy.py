"""부분 익절·재진입 정책이 현재 OOS 권한을 넘지 않는지 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.evidence_admission import load_registry


POLICY_PATH = Path(__file__).with_name("cycle_action_policy.json")
POLICY_VERSION = "HERD_CYCLE_ACTION_V1"


class CycleActionPolicyError(RuntimeError):
    pass


def validate_policy(policy: dict) -> dict:
    if (
        policy.get("policy_version") != POLICY_VERSION
        or policy.get("status") != "RESEARCH_POLICY_LOCKED"
    ):
        raise CycleActionPolicyError("cycle action policy is not locked")

    _, evidence = load_registry()
    current = policy.get("current_authorization", {})
    expected_profit_take = (
        evidence["action_authorizations"]["PROFIT_TAKE"] > 0
    )
    expected_reentry = evidence["action_authorizations"]["REENTRY"] > 0
    if (
        current.get("profit_take") is not expected_profit_take
        or current.get("reentry") is not expected_reentry
    ):
        raise CycleActionPolicyError("cycle action exceeds OOS direction evidence")

    sizing = policy.get("sizing", {})
    if (
        not 0 < sizing.get("minimum_fraction", 0) <= sizing.get("maximum_fraction", 1) <= 0.15
        or sizing.get("full_liquidation_allowed") is not False
        or sizing.get("reentry_cannot_exceed_open_sale_cash") is not True
    ):
        raise CycleActionPolicyError("cycle sizing violates partial-action policy")

    forbidden = set(policy.get("forbidden", []))
    required = {
        "RUSH_ALONE_AUTHORIZES_PROFIT_TAKE",
        "FLEE_ALONE_AUTHORIZES_REENTRY",
        "REENTRY_WITHOUT_PRIOR_PROFIT_TAKE_CASH",
        "COUNT_OPEN_SALE_AS_COMPLETED_CYCLE",
    }
    if not required.issubset(forbidden):
        raise CycleActionPolicyError("critical cycle shortcuts are not forbidden")

    return {
        "policy_version": POLICY_VERSION,
        "profit_take_authorized": current["profit_take"],
        "reentry_authorized": current["reentry"],
        "maximum_fraction": sizing["maximum_fraction"],
    }


def load_policy(path: Path = POLICY_PATH) -> tuple[dict, dict]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    return policy, validate_policy(policy)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    args = parser.parse_args()
    _, audit = load_policy(args.policy)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

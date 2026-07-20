"""신규진입·추가매수 정책과 현재 OOS 권한의 일관성을 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.evidence_admission import load_registry


POLICY_PATH = Path(__file__).with_name("entry_add_buy_policy.json")
POLICY_VERSION = "HERD_ENTRY_ADD_BUY_V1"
EXPECTED_TYPES = {"GENERAL_CORPORATE", "BANK", "INSURANCE", "REIT", "UTILITY"}


class EntryAddBuyPolicyError(RuntimeError):
    pass


def validate_policy(policy: dict) -> dict:
    if (
        policy.get("policy_version") != POLICY_VERSION
        or policy.get("status") != "RESEARCH_POLICY_LOCKED"
    ):
        raise EntryAddBuyPolicyError("entry/add-buy policy is not locked")
    if set(policy.get("company_type_routes", {})) != EXPECTED_TYPES:
        raise EntryAddBuyPolicyError("company type routes are incomplete")

    _, evidence = load_registry()
    current = policy.get("current_authorization", {})
    expected_direction = evidence["direction_family_count"] > 0
    if current.get("new_entry") is not expected_direction:
        raise EntryAddBuyPolicyError("new-entry authorization exceeds evidence")
    if (
        current.get("generic_business_guard") is not False
        or current.get("specialized_company_models") != []
        or current.get("add_buy") is not False
    ):
        raise EntryAddBuyPolicyError("add-buy was authorized without business evidence")

    forbidden = set(policy.get("forbidden", []))
    required = {
        "LOW_HERD_ALONE_AUTHORIZES_ENTRY",
        "PRICE_DROP_ALONE_AUTHORIZES_ADD_BUY",
        "GENERIC_DEBT_RATIO_APPLIED_TO_BANK_REIT_INSURANCE_OR_UTILITY",
        "UNKNOWN_BUSINESS_STATE_TREATED_AS_PASS",
    }
    if not required.issubset(forbidden):
        raise EntryAddBuyPolicyError("critical entry/add-buy shortcuts are not forbidden")

    return {
        "policy_version": POLICY_VERSION,
        "new_entry_authorized": current["new_entry"],
        "add_buy_authorized": current["add_buy"],
        "company_type_routes": len(policy["company_type_routes"]),
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

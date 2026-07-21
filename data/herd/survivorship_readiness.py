"""PIT 구성·식별자·가격·기업행동을 함께 검증해 생존자 편향 준비도를 판정한다."""

from __future__ import annotations

from typing import Any


def _check(name: str, passed: bool, actual: Any, required: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "actual": actual, "required": required}


def evaluate_survivorship_readiness(evidence: dict[str, Any]) -> dict[str, Any]:
    """네 증거 축 중 하나라도 없거나 미완성이면 fail-closed로 판정한다."""
    membership = evidence.get("membership", {})
    identity = evidence.get("identity", {})
    prices = evidence.get("prices", {})
    actions = evidence.get("corporate_actions", {})
    requested = prices.get("requested_tickers")
    available = prices.get("available_tickers")
    coverage = available / requested if isinstance(requested, int) and requested > 0 \
        and isinstance(available, int) else None
    delisted_requested = prices.get("delisted_requested")
    delisted_available = prices.get("delisted_available")

    checks = [
        _check("membership_replay", membership.get("replay_complete") is True,
               membership.get("replay_complete"), True),
        _check("membership_errors", membership.get("replay_errors") == 0,
               membership.get("replay_errors"), 0),
        _check("membership_blockers", membership.get("blocked_events") == 0,
               membership.get("blocked_events"), 0),
        _check("cik_mapping", identity.get("mapped_entities") is not None
               and identity.get("mapped_entities") == identity.get("total_entities"),
               {"mapped": identity.get("mapped_entities"), "total": identity.get("total_entities")},
               "mapped == total"),
        _check("identity_ambiguity", identity.get("ambiguous_entities") == 0,
               identity.get("ambiguous_entities"), 0),
        _check("price_coverage", coverage is not None and coverage >= 0.95, coverage, ">=0.95"),
        _check("delisted_price_coverage", isinstance(delisted_requested, int)
               and delisted_requested > 0 and delisted_available == delisted_requested,
               {"available": delisted_available, "requested": delisted_requested},
               "all delisted prices available"),
        _check("price_adjustment_audit", prices.get("adjustment_audited") is True,
               prices.get("adjustment_audited"), True),
        _check("corporate_action_ledger", actions.get("unresolved_events") == 0,
               actions.get("unresolved_events"), 0),
        _check("split_dividend_audit", actions.get("split_dividend_audited") is True,
               actions.get("split_dividend_audited"), True),
    ]
    failed = [item["name"] for item in checks if not item["passed"]]
    return {
        "status": "SURVIVORSHIP_SAFE" if not failed else "PIT_RESEARCH_ONLY",
        "survivorship_safe": not failed,
        "promotion_allowed": False,
        "failed_checks": failed,
        "checks": checks,
    }

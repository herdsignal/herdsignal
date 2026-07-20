"""검증 권한과 PIT 상태로 신규진입·추가매수 연구 자격을 판정한다."""

from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_ACTIONS = {"NEW_ENTRY", "ADD_BUY", "PROFIT_TAKE", "REENTRY"}
SPECIALIZED_COMPANY_TYPES = {"BANK", "INSURANCE", "REIT", "UTILITY"}


@dataclass(frozen=True)
class EligibilityContext:
    action: str
    evidence_as_of_signal: bool
    direction_authorized: bool
    data_fresh: bool
    existing_holder: bool = False
    market_or_sector_explained_weakness: bool = False
    decline_stabilized: bool = False
    business_guard_authorized: bool = False
    business_guard_state: str = "UNKNOWN"
    company_type: str = "UNKNOWN"
    company_type_model_authorized: bool = False
    crowded_state: bool = False
    exhaustion_model_authorized: bool = False
    exhausted_or_breaking: bool = False
    prior_profit_take_cash: bool = False


@dataclass(frozen=True)
class EligibilityDecision:
    action: str
    eligible: bool
    reasons: tuple[str, ...]


def evaluate_eligibility(context: EligibilityContext) -> EligibilityDecision:
    action = context.action.upper()
    if action not in SUPPORTED_ACTIONS:
        raise ValueError(f"unsupported action eligibility type: {context.action}")

    reasons = []
    if not context.evidence_as_of_signal:
        reasons.append("NON_PIT_EVIDENCE")
    if not context.data_fresh:
        reasons.append("STALE_OR_MISSING_DATA")
    if not context.direction_authorized:
        reasons.append("NO_OOS_DIRECTION_EVIDENCE")

    if action in {"ADD_BUY", "REENTRY"}:
        if not context.existing_holder:
            reasons.append("NOT_EXISTING_HOLDER")
        if not context.market_or_sector_explained_weakness:
            reasons.append("WEAKNESS_NOT_MARKET_OR_SECTOR_EXPLAINED")
        if not context.decline_stabilized:
            reasons.append("DECLINE_NOT_STABILIZED")
        if not context.business_guard_authorized:
            reasons.append("BUSINESS_GUARD_NOT_OOS_AUTHORIZED")
        elif context.business_guard_state != "PASS":
            reasons.append("BUSINESS_GUARD_NOT_PASS")
        if context.company_type in SPECIALIZED_COMPANY_TYPES:
            if not context.company_type_model_authorized:
                reasons.append(f"{context.company_type}_MODEL_NOT_AUTHORIZED")
        elif context.company_type != "GENERAL_CORPORATE":
            reasons.append("UNKNOWN_COMPANY_TYPE")
        if action == "REENTRY" and not context.prior_profit_take_cash:
            reasons.append("NO_PRIOR_PROFIT_TAKE_CASH")

    if action == "PROFIT_TAKE":
        if not context.existing_holder:
            reasons.append("NOT_EXISTING_HOLDER")
        if not context.crowded_state:
            reasons.append("NOT_CROWDED")
        if not context.exhaustion_model_authorized:
            reasons.append("EXHAUSTION_MODEL_NOT_OOS_AUTHORIZED")
        elif not context.exhausted_or_breaking:
            reasons.append("RUSH_NOT_EXHAUSTED_OR_BREAKING")

    return EligibilityDecision(
        action=action,
        eligible=not reasons,
        reasons=tuple(reasons),
    )

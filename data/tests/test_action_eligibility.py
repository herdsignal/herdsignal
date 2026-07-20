from herd.action_eligibility import EligibilityContext, evaluate_eligibility


def test_current_new_entry_is_blocked_without_direction_evidence():
    decision = evaluate_eligibility(EligibilityContext(
        action="NEW_ENTRY",
        evidence_as_of_signal=True,
        direction_authorized=False,
        data_fresh=True,
    ))

    assert decision.eligible is False
    assert decision.reasons == ("NO_OOS_DIRECTION_EVIDENCE",)


def test_add_buy_requires_complete_evidence_not_just_price_drop():
    decision = evaluate_eligibility(EligibilityContext(
        action="ADD_BUY",
        evidence_as_of_signal=True,
        direction_authorized=True,
        data_fresh=True,
        existing_holder=True,
        company_type="GENERAL_CORPORATE",
    ))

    assert decision.eligible is False
    assert "WEAKNESS_NOT_MARKET_OR_SECTOR_EXPLAINED" in decision.reasons
    assert "DECLINE_NOT_STABILIZED" in decision.reasons
    assert "BUSINESS_GUARD_NOT_OOS_AUTHORIZED" in decision.reasons


def test_generic_business_rule_cannot_authorize_bank_add_buy():
    decision = evaluate_eligibility(EligibilityContext(
        action="ADD_BUY",
        evidence_as_of_signal=True,
        direction_authorized=True,
        data_fresh=True,
        existing_holder=True,
        market_or_sector_explained_weakness=True,
        decline_stabilized=True,
        business_guard_authorized=True,
        business_guard_state="PASS",
        company_type="BANK",
        company_type_model_authorized=False,
    ))

    assert decision.eligible is False
    assert decision.reasons == ("BANK_MODEL_NOT_AUTHORIZED",)


def test_fully_authorized_general_company_context_can_be_researched():
    decision = evaluate_eligibility(EligibilityContext(
        action="ADD_BUY",
        evidence_as_of_signal=True,
        direction_authorized=True,
        data_fresh=True,
        existing_holder=True,
        market_or_sector_explained_weakness=True,
        decline_stabilized=True,
        business_guard_authorized=True,
        business_guard_state="PASS",
        company_type="GENERAL_CORPORATE",
    ))

    assert decision.eligible is True
    assert decision.reasons == ()

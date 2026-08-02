from scheduler.model_readiness_audit import build_readiness


def _claim_scope():
    return {
        "lanes": {
            "PERSONAL_PROSPECTIVE_SHADOW": {
                "minimum_observation_months_before_policy_review": 12,
                "minimum_complete_candidate_events_before_policy_review": 30,
                "minimum_distinct_tickers_before_policy_review": 10,
            }
        }
    }


def test_blocks_action_while_only_observation_data_exists():
    result = build_readiness(
        {
            "product_scope": "STATE_AND_TRANSITION_OBSERVATION",
            "adoptable_action_candidates": 0,
        },
        {"decision": {"survivorship_safe": False}},
        _claim_scope(),
        {
            "observationArchives": 1,
            "observationRecords": 440,
            "distinctTickers": 440,
            "firstObservationDate": "2026-07-24",
            "latestObservationDate": "2026-07-24",
            "maturityByHorizon": {"126": {"matured": 0}},
        },
    )

    assert result["product"]["stateObservationReady"] is True
    assert result["gates"]["operationalActionAllowed"] is False
    assert result["gates"]["personalProspectivePolicyReviewReady"] is False
    assert result["nextWork"]["primary"] == (
        "ACCUMULATE_PROSPECTIVE_OBSERVATIONS_AND_OUTCOMES"
    )


def test_requires_preholdout_pass_even_after_prospective_minimums():
    result = build_readiness(
        {
            "product_scope": "STATE_AND_TRANSITION_OBSERVATION",
            "adoptable_action_candidates": 0,
        },
        {"decision": {"survivorship_safe": True}},
        _claim_scope(),
        {
            "observationArchives": 60,
            "observationRecords": 1000,
            "distinctTickers": 20,
            "firstObservationDate": "2025-01-01",
            "latestObservationDate": "2026-07-01",
            "maturityByHorizon": {"126": {"matured": 100}},
        },
    )

    assert result["evidence"]["prospectiveObservationMonths"] == 18
    assert result["gates"]["personalProspectivePolicyReviewReady"] is False
    assert result["gates"]["marketGeneralActionResearchReady"] is True


def test_surfaces_locked_source_review_as_current_primary_work():
    result = build_readiness(
        {
            "product_scope": "STATE_AND_TRANSITION_OBSERVATION",
            "adoptable_action_candidates": 0,
            "pending_source_decisions": 110,
            "next_stage": "COMPLETE_110_SEC_IDENTITY_SOURCE_DECISIONS",
        },
        {"decision": {"survivorship_safe": False}},
        _claim_scope(),
        {
            "observationArchives": 1,
            "observationRecords": 440,
            "distinctTickers": 440,
            "firstObservationDate": "2026-07-24",
            "latestObservationDate": "2026-07-24",
            "maturityByHorizon": {"126": {"matured": 0}},
        },
    )

    assert result["evidence"]["pendingSourceDecisions"] == 110
    assert result["nextWork"]["primary"] == (
        "COMPLETE_110_SEC_IDENTITY_SOURCE_DECISIONS"
    )
    assert result["nextWork"]["prospective"] == (
        "ACCUMULATE_PROSPECTIVE_OBSERVATIONS_AND_OUTCOMES"
    )

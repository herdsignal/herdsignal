from herd.overnight_pit_shadow_completion_v1 import _evaluate_reports


def _payloads():
    return {
        "EXECUTION_CONTRACT": {
            "status": "LOCKED_BEFORE_OVERNIGHT_EXPANSION",
            "authority": {"operational_action_ratio": 0.0},
        },
        "IDENTIFIER_GAP_REPORT": {
            "status": "HASH_LOCKED_TARGET_QUEUE_READY",
        },
        "TARGETED_COVER_REPORT": {
            "status": "HASH_LOCKED_ELIGIBLE_SOURCE_EXHAUSTED",
            "unresolved_failures": 0,
        },
        "LIFECYCLE_LEDGER_REPORT": {
            "status": "TIME_VALID_LIFECYCLE_LEDGER_BUILT",
            "conflict_excluded_interval_count": 0,
        },
        "LIFECYCLE_COVERAGE_REPORT": {
            "finra_shadow_identifier_gate_passed": True,
            "target_gap_audit": {"blocked_target_count": 5},
        },
        "FINRA_INCREMENTAL_REPORT": {
            "status": "PENDING_OFFICIAL_PUBLICATION_WINDOW",
            "as_of_utc": "2026-07-23T16:00:00+00:00",
            "all_baseline_hashes_verified": True,
            "pending_candidates": [
                {
                    "status": "PENDING_OFFICIAL_PUBLICATION_WINDOW",
                    "download_not_before": "2026-07-24T00:00:00-04:00",
                }
            ],
        },
        "UNIFIED_PANEL_REPORT": {
            "status": "HASH_LOCKED_PROSPECTIVE_SEED_SNAPSHOT_READY",
            "finra_current_snapshot_coverage_gate": {"passed": True},
            "price_or_return_outcomes_opened": False,
            "direction_labels_created": False,
        },
        "FULL_REGRESSION_REPORT": {
            "status": "FULL_REGRESSION_PASS",
            "all_commands_passed": True,
        },
    }


def test_all_seven_stage_checks_pass_with_honest_not_due_candidate():
    result = _evaluate_reports(_payloads())
    assert result["all_stage_checks_passed"] is True
    assert result["pending_finra_candidates_are_not_due"] is True


def test_due_but_missing_finra_candidate_fails_closed():
    payloads = _payloads()
    payloads["FINRA_INCREMENTAL_REPORT"]["as_of_utc"] = (
        "2026-07-24T05:00:00+00:00"
    )
    result = _evaluate_reports(payloads)
    assert result["stage_checks"]["PART_5"] is False
    assert result["all_stage_checks_passed"] is False


def test_same_calendar_date_respects_timezone_offset():
    payloads = _payloads()
    payloads["FINRA_INCREMENTAL_REPORT"]["as_of_utc"] = (
        "2026-07-24T03:00:00+00:00"
    )
    result = _evaluate_reports(payloads)
    assert result["stage_checks"]["PART_5"] is True


def test_regression_failure_keeps_part_seven_incomplete():
    payloads = _payloads()
    payloads["FULL_REGRESSION_REPORT"]["status"] = "FULL_REGRESSION_FAIL"
    payloads["FULL_REGRESSION_REPORT"]["all_commands_passed"] = False
    result = _evaluate_reports(payloads)
    assert result["stage_checks"]["PART_7"] is False

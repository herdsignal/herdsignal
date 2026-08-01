import hashlib
import json
from pathlib import Path

from scheduler.action_research_intake_gate import build_report


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/herd/unified_pit_shadow_panel_v1.json"


def _prospective(months_ready: bool = False) -> dict:
    return {
        "firstObservationDate": "2025-01-01" if months_ready else "2026-07-24",
        "latestObservationDate": "2026-07-24",
        "distinctTickers": 20 if months_ready else 440,
        "maturityByHorizon": {"126": {"matured": 40 if months_ready else 0}},
    }


def _candidate() -> dict:
    return {
        "status": "LOCKED_BEFORE_OUTCOME_REVIEW",
        "serviceObjective": "RARE_PARTIAL_PROFIT_TAKE_AND_EVIDENCE_BACKED_REENTRY_FOR_ALREADY_SELECTED_LONG_TERM_US_EQUITY_HOLDINGS",
        "candidateId": "NEW_PIT_INPUT_V1",
        "economicFamily": "NEW_PUBLIC_EXPECTATION_INPUT",
        "sampleId": "INDEPENDENT_SAMPLE_V1",
        "target": "PROFIT_TAKE_DIRECTION",
        "newInput": {
            "path": "data/herd/unified_pit_shadow_panel_v1.json",
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "pointInTime": True,
            "availabilityTimestampField": "acceptedAt",
        },
        "formula": "locked_feature_t_minus_1",
        "observationTiming": "after public acceptance and before next session open",
        "expectedFrequencyPerYear": 4,
        "oosProtocol": {
            "independentTickerOrTimeSplit": True,
            "costStressIncluded": True,
            "buyAndHoldComparator": True,
            "blindHoldoutAccess": False,
        },
        "overlapAudit": {
            "reusedRejectedExperimentIds": [],
            "sameSampleRetuning": False,
            "rejectedFeatureRecombination": False,
            "legacyFormulaReuse": False,
        },
    }


def test_blocks_cleanly_when_no_economically_new_input_exists() -> None:
    report = build_report(_prospective())

    assert report["status"] == "BLOCKED_NO_NEW_INPUT"
    assert report["gates"]["independentOosAllowed"] is False
    assert report["operationalActionRatio"] == 0.0


def test_locked_nonduplicate_candidate_only_opens_independent_oos() -> None:
    report = build_report(_prospective(months_ready=True), _candidate())

    assert report["status"] == "READY_FOR_INDEPENDENT_OOS"
    assert report["gates"]["independentOosAllowed"] is True
    assert report["prospective"]["policyReviewReady"] is True
    assert report["gates"]["completedCycleAllowed"] is False
    assert report["gates"]["operationalActionAllowed"] is False


def test_rejected_sample_and_retuning_are_blocked() -> None:
    candidate = _candidate()
    candidate["sampleId"] = "MATCHED_WEEKLY_RSI_PAIRS_449"
    candidate["overlapAudit"]["sameSampleRetuning"] = True

    report = build_report(_prospective(months_ready=True), candidate)

    assert report["status"] == "BLOCKED_INVALID_CANDIDATE"
    assert "SAME_SAMPLE_THRESHOLD_RETUNING" in report["candidateValidationFailures"]
    assert report["gates"]["blindHoldoutAllowed"] is False

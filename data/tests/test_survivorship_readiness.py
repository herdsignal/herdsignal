import copy
import json
from pathlib import Path

from herd.survivorship_readiness import evaluate_survivorship_readiness


DATA_ROOT = Path(__file__).resolve().parents[1]


def complete_evidence():
    return {
        "membership": {"replay_complete": True, "replay_errors": 0, "blocked_events": 0},
        "identity": {"mapped_entities": 900, "total_entities": 900, "ambiguous_entities": 0},
        "prices": {"requested_tickers": 900, "available_tickers": 890,
                   "delisted_requested": 120, "delisted_available": 120,
                   "adjustment_audited": True},
        "corporate_actions": {"unresolved_events": 0, "split_dividend_audited": True},
    }


def test_all_four_evidence_axes_are_required_for_safe_status():
    result = evaluate_survivorship_readiness(complete_evidence())
    assert result["survivorship_safe"] is True
    assert result["status"] == "SURVIVORSHIP_SAFE"
    assert result["promotion_allowed"] is False


def test_complete_membership_does_not_hide_missing_delisted_prices():
    evidence = complete_evidence()
    evidence["prices"]["delisted_available"] = 119
    result = evaluate_survivorship_readiness(evidence)
    assert result["survivorship_safe"] is False
    assert "delisted_price_coverage" in result["failed_checks"]


def test_missing_axis_fails_closed_instead_of_raising_readiness():
    evidence = copy.deepcopy(complete_evidence())
    del evidence["corporate_actions"]
    result = evaluate_survivorship_readiness(evidence)
    assert result["status"] == "PIT_RESEARCH_ONLY"
    assert "corporate_action_ledger" in result["failed_checks"]
    assert "split_dividend_audit" in result["failed_checks"]


def test_current_public_evidence_cannot_claim_survivorship_safety():
    evidence = json.loads(
        (DATA_ROOT / "herd/survivorship_evidence_v1.json").read_text(encoding="utf-8")
    )
    result = evaluate_survivorship_readiness(evidence)

    assert result["survivorship_safe"] is False
    assert "membership_replay" in result["failed_checks"]
    assert "delisted_price_coverage" in result["failed_checks"]
    assert "split_dividend_audit" in result["failed_checks"]

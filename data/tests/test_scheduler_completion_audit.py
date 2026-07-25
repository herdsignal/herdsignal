from copy import deepcopy
from datetime import UTC, datetime

from scheduler.completion_audit import evaluate_completion
from scheduler.observation_s1 import FORMAT_VERSION


def _contract() -> dict:
    return {
        "reference_universe": {
            "expected_equities": 439,
            "minimum_total_coverage_fraction": 0.9,
        }
    }


def _record(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "scope": "EQUITY",
        "asOfDate": "2026-07-24",
        "lastObservedSession": "2026-07-24",
        "stateScore": 50.0,
        "stage": "CALM",
        "transition": "NEUTRAL",
        "rawTransition": "NEUTRAL",
        "transitionEvent": False,
        "delta4w": 0.0,
        "delta13w": 0.0,
        "families": {
            "PRICE_EXTENSION": 50.0,
            "TREND_POSITION": 50.0,
            "RELATIVE_POSITION": 50.0,
            "PARTICIPATION": 50.0,
        },
        "downsideRiskContext": 50.0,
        "sectorEtf": "XLK",
        "directionPrediction": False,
        "action": "HOLD",
        "actionRatio": 0.0,
    }


def _bundle() -> dict:
    return {
        "schemaVersion": FORMAT_VERSION,
        "stateModelVersion": "HERD_STATE_S1",
        "transitionModelVersion": "HERD_TRANSITION_S1",
        "generatedAt": "2026-07-25T01:30:00+00:00",
        "referenceUniverse": {
            "expected": 439,
            "available": 439,
            "coverageFraction": 1.0,
            "survivorshipSafe": False,
        },
        "records": {"AAPL": _record("AAPL")},
        "unavailable": {},
        "claimBoundary": {
            "directionPrediction": False,
            "operationalAction": "HOLD",
            "operationalActionRatio": 0.0,
            "blindHoldoutAccess": False,
        },
    }


def _run(status: str = "SUCCESS") -> dict:
    return {
        "id": 7,
        "status": status,
        "started_at": datetime(2026, 7, 25, 1, 0, tzinfo=UTC),
        "finished_at": (
            datetime(2026, 7, 25, 2, 0, tzinfo=UTC)
            if status != "RUNNING"
            else None
        ),
        "total_count": 458,
        "success_count": 458 if status == "SUCCESS" else 0,
        "failed_count": 0,
        "failed_tickers": [],
        "skipped_count": 0,
        "skipped_tickers": [],
        "publish_status": "SUCCESS",
        "universe_sha256": "a" * 64,
    }


def test_accepts_explicit_minimum_history_exclusion() -> None:
    run = _run()
    run["success_count"] = 457
    run["skipped_count"] = 1
    run["skipped_tickers"] = ["SNDK"]
    result = evaluate_completion(
        run=run,
        bundle=_bundle(),
        contract=_contract(),
        stored_pairs={("AAPL", "2026-07-24")},
    )
    assert result["status"] == "PASS"
    assert result["skippedTickers"] == ["SNDK"]


def test_passes_only_when_run_bundle_and_db_are_complete() -> None:
    result = evaluate_completion(
        run=_run(),
        bundle=_bundle(),
        contract=_contract(),
        stored_pairs={("AAPL", "2026-07-24")},
    )
    assert result["status"] == "PASS"
    assert result["passed"] is True


def test_reports_missing_db_observation() -> None:
    result = evaluate_completion(
        run=_run(),
        bundle=_bundle(),
        contract=_contract(),
        stored_pairs=set(),
    )
    assert result["status"] == "FAIL"
    assert result["missingObservationPairs"] == [
        {"ticker": "AAPL", "observationDate": "2026-07-24"}
    ]


def test_running_run_never_passes_even_with_previous_bundle() -> None:
    result = evaluate_completion(
        run=_run("RUNNING"),
        bundle=_bundle(),
        contract=_contract(),
        stored_pairs={("AAPL", "2026-07-24")},
    )
    assert result["status"] == "RUNNING"
    assert result["passed"] is False


def test_rejects_reference_universe_drift() -> None:
    bundle = deepcopy(_bundle())
    bundle["referenceUniverse"]["expected"] = 438
    result = evaluate_completion(
        run=_run(),
        bundle=bundle,
        contract=_contract(),
        stored_pairs={("AAPL", "2026-07-24")},
    )
    assert result["status"] == "FAIL"
    assert next(
        check for check in result["checks"]
        if check["name"] == "reference_universe_locked"
    )["passed"] is False


def test_rejects_run_when_state_publish_was_blocked() -> None:
    run = _run()
    run["status"] = "PARTIAL_FAILURE"
    run["success_count"] = 457
    run["failed_count"] = 1
    run["failed_tickers"] = ["NVDA"]
    run["publish_status"] = "SKIPPED_INCOMPLETE_INPUT"
    result = evaluate_completion(
        run=run,
        bundle=_bundle(),
        contract=_contract(),
        stored_pairs={("AAPL", "2026-07-24")},
    )
    assert result["status"] == "FAIL"
    assert next(
        check for check in result["checks"]
        if check["name"] == "state_publish_succeeded"
    )["passed"] is False


def test_rejects_malformed_ticker_universe_hash() -> None:
    run = _run()
    run["universe_sha256"] = "not-a-sha256"
    result = evaluate_completion(
        run=run,
        bundle=_bundle(),
        contract=_contract(),
        stored_pairs={("AAPL", "2026-07-24")},
    )
    assert result["status"] == "FAIL"
    assert next(
        check for check in result["checks"]
        if check["name"] == "ticker_universe_contract_recorded"
    )["passed"] is False


def test_accepts_explicit_legacy_run_without_v8_publish_contract() -> None:
    run = _run()
    run["publish_status"] = None
    run["universe_sha256"] = None
    result = evaluate_completion(
        run=run,
        bundle=_bundle(),
        contract=_contract(),
        stored_pairs={("AAPL", "2026-07-24")},
    )
    assert result["status"] == "PASS"
    assert next(
        check for check in result["checks"]
        if check["name"] == "ticker_universe_contract_recorded"
    )["detail"] == "legacy_pre_v8=true"

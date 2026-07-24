from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from init_db import HerdObservation
from scheduler.observation_s1 import FORMAT_VERSION
from scheduler.observation_store import (
    ObservationStoreError,
    save_observation_bundle,
)


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    HerdObservation.__table__.create(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _record(ticker: str, *, score: float = 62.5) -> dict:
    return {
        "ticker": ticker,
        "scope": "EQUITY",
        "asOfDate": "2026-07-24",
        "lastObservedSession": "2026-07-24",
        "stateScore": score,
        "stage": "DRIFT",
        "transition": "NEUTRAL",
        "rawTransition": "NEUTRAL",
        "transitionEvent": False,
        "delta4w": 1.25,
        "delta13w": 3.5,
        "families": {
            "PRICE_EXTENSION": 70.0,
            "TREND_POSITION": 65.0,
            "RELATIVE_POSITION": 60.0,
            "PARTICIPATION": 55.0,
        },
        "downsideRiskContext": 35.0,
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
        "generatedAt": datetime(2026, 7, 25, tzinfo=UTC).isoformat(),
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


def test_bundle_save_is_idempotent_upsert() -> None:
    factory = _session_factory()
    first = save_observation_bundle(_bundle(), factory)
    changed = _bundle()
    changed["records"]["AAPL"]["stateScore"] = 64.25
    second = save_observation_bundle(changed, factory)

    with factory() as session:
        rows = session.query(HerdObservation).all()
        assert len(rows) == 1
        assert float(rows[0].state_score) == 64.25
        assert rows[0].operational_action == "HOLD"
    assert first == {"inserted": 1, "updated": 0}
    assert second == {"inserted": 0, "updated": 1}


def test_action_authority_is_rejected_before_db_write() -> None:
    factory = _session_factory()
    bundle = _bundle()
    bundle["records"]["AAPL"]["actionRatio"] = 0.05

    with pytest.raises(ObservationStoreError, match="state-only"):
        save_observation_bundle(bundle, factory)
    with factory() as session:
        assert session.query(HerdObservation).count() == 0


def test_invalid_record_prevents_entire_bundle_from_being_saved() -> None:
    factory = _session_factory()
    bundle = _bundle()
    bundle["records"]["NVDA"] = _record("NVDA", score=110)

    with pytest.raises(ObservationStoreError, match="stateScore"):
        save_observation_bundle(bundle, factory)
    with factory() as session:
        assert session.query(HerdObservation).count() == 0


def test_market_aggregate_requires_explicit_meaning() -> None:
    factory = _session_factory()
    bundle = deepcopy(_bundle())
    bundle["records"]["SPY"] = _record("SPY")
    bundle["records"]["SPY"]["scope"] = "MARKET_AGGREGATE"

    with pytest.raises(ObservationStoreError, match="label and claim"):
        save_observation_bundle(bundle, factory)

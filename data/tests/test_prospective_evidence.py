from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from scheduler.prospective_evidence import (
    audit_archive,
    archive_observation,
    mature_outcomes,
    verify_observation,
)
from scheduler.observation_s1 import FORMAT_VERSION


def _frame(periods: int = 180) -> pd.DataFrame:
    close = np.linspace(100, 130, periods)
    return pd.DataFrame({
        "Date": pd.bdate_range("2026-01-01", periods=periods),
        "Open": close - 0.25,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": np.arange(periods) + 1_000,
    })


def _contract(path: Path) -> Path:
    source = Path(__file__).resolve().parents[2] / "data/config/prospective_evidence_v1.json"
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def _bundle() -> dict:
    record = {
        "ticker": "AAPL",
        "scope": "EQUITY",
        "asOfDate": "2026-07-24",
        "lastObservedSession": "2026-07-24",
        "stateScore": 62.5,
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
        "records": {"AAPL": record},
        "unavailable": {},
        "claimBoundary": {
            "directionPrediction": False,
            "operationalAction": "HOLD",
            "operationalActionRatio": 0.0,
            "blindHoldoutAccess": False,
        },
    }


def test_observation_is_immutable_idempotent_and_actionless(tmp_path: Path) -> None:
    bundle = _bundle()
    frame = _frame()
    frame.loc[frame.index[-1], "Date"] = pd.Timestamp("2026-07-24")
    frames = {"AAPL": frame}
    contract = _contract(tmp_path / "contract.json")

    first = archive_observation(
        bundle,
        frames,
        {"AAPL": {"PORTFOLIO", "WATCHLIST"}},
        archive_dir=tmp_path,
        recorded_at=datetime(2026, 7, 25, tzinfo=UTC),
        contract_path=contract,
    )
    second = archive_observation(
        bundle,
        frames,
        {"AAPL": {"PORTFOLIO", "WATCHLIST"}},
        archive_dir=tmp_path,
        contract_path=contract,
    )
    envelope = verify_observation(Path(first["path"]))

    assert first["status"] == "CREATED"
    assert second["status"] == "EXISTS"
    assert envelope["evidence"]["records"][0]["trackingScopes"] == [
        "PORTFOLIO", "WATCHLIST"
    ]
    assert envelope["evidence"]["records"][0]["observation"]["action"] == "HOLD"


def test_same_observation_date_keeps_first_immutable_record(tmp_path: Path) -> None:
    bundle = _bundle()
    frame = _frame()
    frame.loc[frame.index[-1], "Date"] = pd.Timestamp("2026-07-24")
    contract = _contract(tmp_path / "contract.json")
    archive_observation(
        bundle, {"AAPL": frame}, {}, archive_dir=tmp_path, contract_path=contract
    )
    changed = deepcopy(bundle)
    changed["records"]["AAPL"]["stateScore"] = 70
    result = archive_observation(
        changed, {"AAPL": frame}, {}, archive_dir=tmp_path, contract_path=contract
    )
    stored = verify_observation(tmp_path / "observations/2026-07-24.json")
    assert result["status"] == "EXISTS"
    assert stored["evidence"]["records"][0]["observation"]["stateScore"] == 62.5


def test_personal_unavailable_ticker_is_preserved_with_scope(tmp_path: Path) -> None:
    bundle = _bundle()
    bundle["unavailable"] = {"BITX": "SECTOR_ETF_UNAVAILABLE"}
    frame = _frame()
    frame.loc[frame.index[-1], "Date"] = pd.Timestamp("2026-07-24")
    contract = _contract(tmp_path / "contract.json")
    result = archive_observation(
        bundle,
        {"AAPL": frame, "BITX": frame},
        {"BITX": {"PORTFOLIO"}},
        archive_dir=tmp_path,
        contract_path=contract,
    )
    evidence = verify_observation(Path(result["path"]))["evidence"]
    assert evidence["unavailable"] == [{
        "ticker": "BITX",
        "reason": "SECTOR_ETF_UNAVAILABLE",
        "trackingScopes": ["LEVERAGED_ETF", "PORTFOLIO"],
    }]


def test_only_mature_horizons_receive_descriptive_outcomes(tmp_path: Path) -> None:
    bundle = _bundle()
    observation_frame = _frame(150)
    observation_frame.loc[observation_frame.index[-1], "Date"] = pd.Timestamp("2026-07-24")
    contract = _contract(tmp_path / "contract.json")
    archive_observation(
        bundle,
        {"AAPL": observation_frame},
        {},
        archive_dir=tmp_path,
        contract_path=contract,
    )
    future_dates = pd.bdate_range("2026-07-27", periods=63)
    future_close = np.linspace(131, 145, 63)
    future = pd.DataFrame({
        "Date": future_dates,
        "Open": future_close - 0.25,
        "High": future_close + 1,
        "Low": future_close - 1,
        "Close": future_close,
        "Volume": 2_000,
    })
    full = pd.concat([observation_frame, future], ignore_index=True)

    result = mature_outcomes(
        {"AAPL": full}, archive_dir=tmp_path, contract_path=contract
    )

    assert result["created"] == 2
    assert result["pending"] == 1
    outcome = pd.read_json(
        tmp_path / "outcomes/2026-07-24/AAPL-21.json", typ="series"
    ).to_dict()
    assert outcome["economicLabel"] == "NOT_ASSIGNED_OBSERVATION_ONLY"
    assert outcome["operationalAction"] == "HOLD"
    audit = audit_archive(tmp_path, contract_path=contract)
    assert audit["status"] == "PASS"
    assert audit["observationArchives"] == 1
    assert audit["maturedOutcomes"] == 2
    assert audit["pendingOutcomes"] == 1
    assert audit["firstObservationDate"] == "2026-07-24"
    assert audit["latestObservationDate"] == "2026-07-24"
    assert audit["maturityByHorizon"] == {
        "21": {"expected": 1, "matured": 1, "pending": 0},
        "63": {"expected": 1, "matured": 1, "pending": 0},
        "126": {"expected": 1, "matured": 0, "pending": 1},
    }

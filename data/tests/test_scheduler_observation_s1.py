from datetime import UTC, datetime

import numpy as np
import pandas as pd

from scheduler.observation_s1 import (
    apply_operational_identity_window,
    build_daily_observation_bundle,
    build_observation_bundle,
    load_operational_identity_starts,
    sector_etf_for_name,
)


def _frame(offset: float, periods: int = 1100) -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-03", periods=periods)
    trend = np.linspace(100 + offset, 220 + offset, periods)
    cycle = np.sin(np.arange(periods) / 25) * 8
    close = trend + cycle
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close - 0.5,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1_000_000 + np.arange(periods) * 10,
        }
    )


def _contracts() -> tuple[dict, dict]:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    service = json.loads(
        (root / "data/config/observation_s1_service.json").read_text()
    )
    service["reference_universe"]["expected_equities"] = 4
    service["reference_universe"]["minimum_total_coverage_fraction"] = 0.75
    service["reference_universe"]["minimum_sector_peer_count"] = 3
    return service, {"AAA": "XLK", "BBB": "XLK", "CCC": "XLK", "DDD": "XLK"}


def test_service_bundle_separates_market_aggregate_and_equity_state() -> None:
    service, reference = _contracts()
    frames = {
        ticker: _frame(index * 3)
        for index, ticker in enumerate((*reference, "EXTRA", "XLK", "SPY"))
    }
    bundle = build_observation_bundle(
        frames,
        target_tickers={"AAA", "EXTRA"},
        sector_overrides={"EXTRA": "XLK"},
        service_contract=service,
        reference_mapping=reference,
        generated_at=datetime(2026, 7, 25, tzinfo=UTC),
    )
    assert set(bundle["records"]) == {"AAA", "EXTRA", "SPY"}
    assert bundle["records"]["SPY"]["scope"] == "MARKET_AGGREGATE"
    assert bundle["records"]["SPY"]["claim"] == "CROWD_STATE_NOT_SPY_PRICE_SCORE"
    assert bundle["records"]["AAA"]["scope"] == "EQUITY"
    assert bundle["records"]["AAA"]["action"] == "HOLD"
    assert bundle["records"]["AAA"]["actionRatio"] == 0.0
    assert bundle["claimBoundary"]["directionPrediction"] is False


def test_daily_bundle_is_provisional_and_uses_latest_completed_session() -> None:
    service, reference = _contracts()
    frames = {
        ticker: _frame(index * 3)
        for index, ticker in enumerate((*reference, "EXTRA", "XLK", "SPY"))
    }
    bundle = build_daily_observation_bundle(
        frames,
        target_tickers={"AAA", "EXTRA"},
        sector_overrides={"EXTRA": "XLK"},
        service_contract=service,
        reference_mapping=reference,
        generated_at=datetime(2026, 7, 29, tzinfo=UTC),
    )

    assert bundle["stateModelVersion"] == "HERD_DAILY_D1"
    assert bundle["claimBoundary"]["confirmedState"] is False
    assert set(bundle["records"]) == {"AAA", "EXTRA", "SPY"}
    assert bundle["records"]["AAA"]["provisional"] is True
    assert bundle["records"]["AAA"]["transition"] == "PROVISIONAL"
    assert bundle["records"]["AAA"]["action"] == "HOLD"
    assert bundle["records"]["AAA"]["asOfDate"] == str(
        frames["AAA"]["Date"].iloc[-1].date()
    )


def test_unmapped_target_is_reported_instead_of_falling_back_to_spy() -> None:
    service, reference = _contracts()
    frames = {
        ticker: _frame(index * 3)
        for index, ticker in enumerate((*reference, "UNKNOWN", "XLK", "SPY"))
    }
    bundle = build_observation_bundle(
        frames,
        target_tickers={"UNKNOWN"},
        service_contract=service,
        reference_mapping=reference,
    )
    assert "UNKNOWN" not in bundle["records"]
    assert bundle["unavailable"]["UNKNOWN"] == "SECTOR_ETF_UNAVAILABLE"


def test_sector_name_mapping_is_explicit_and_conservative() -> None:
    assert sector_etf_for_name("Technology") == "XLK"
    assert sector_etf_for_name("Aerospace & Defense") == "XLI"
    assert sector_etf_for_name("Unknown Industry") is None


def test_operational_identity_window_removes_reused_ticker_history() -> None:
    starts = load_operational_identity_starts()

    assert starts["SW"] == pd.Timestamp("2024-07-09")
    assert starts["BLK"] == pd.Timestamp("2021-07-14")
    assert starts["FISV"] == pd.Timestamp("2021-06-03")

    frame = pd.DataFrame({
        "Date": ["2024-07-08", "2024-07-09", "2024-07-10"],
        "Close": [10.0, 20.0, 21.0],
        "Volume": [100, 200, 300],
    })
    trimmed = apply_operational_identity_window("SW", frame, starts=starts)

    assert trimmed["Date"].tolist() == ["2024-07-09", "2024-07-10"]

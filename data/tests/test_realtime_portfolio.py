from datetime import date

from scheduler import realtime_portfolio
from scheduler.realtime_portfolio import (
    calculate_current_portfolio,
    empty_portfolio,
    value_holdings,
)


def test_value_holdings_calculates_position_and_portfolio_totals():
    holdings = [
        {"ticker": "NVDA", "avg_price": 90.0, "quantity": 2.0},
        {"ticker": "MISSING", "avg_price": 10.0, "quantity": 1.0},
    ]
    prices = {
        "NVDA": {
            "price": 110.0,
            "prev_close": 100.0,
            "change_pct": 10.0,
            "price_date": "2026-07-24",
        }
    }

    stocks, totals = value_holdings(holdings, prices)

    assert stocks == [{
        "ticker": "NVDA",
        "avg_price": 90.0,
        "quantity": 2.0,
        "current_price": 110.0,
        "price_date": "2026-07-24",
        "market_value": 220.0,
        "return_pct": 22.2222,
        "daily_change_pct": 10.0,
    }]
    assert totals == {
        "total_value": 220.0,
        "total_cost": 180.0,
        "previous_value": 200.0,
        "daily_current_value": 220.0,
    }


def test_empty_portfolio_returns_a_new_collection():
    first = empty_portfolio()
    second = empty_portfolio()

    first["stocks"].append({"ticker": "NVDA"})

    assert second["stocks"] == []


def test_calculate_current_portfolio_uses_injected_price_and_snapshot_date(monkeypatch):
    holdings = [{"ticker": "NVDA", "avg_price": 90.0, "quantity": 2.0}]
    snapshot_calls = []
    monkeypatch.setattr(
        realtime_portfolio,
        "load_holdings",
        lambda user_id, session_factory: holdings,
    )
    monkeypatch.setattr(
        realtime_portfolio,
        "upsert_snapshot",
        lambda *args: snapshot_calls.append(args),
    )

    result = calculate_current_portfolio(
        "user-1",
        session_factory=object(),
        price_loader=lambda tickers: {
            "NVDA": {
                "price": 110.0,
                "prev_close": 100.0,
                "change_pct": 10.0,
                "price_date": "2026-07-23",
            },
        },
        snapshot_date=date(2026, 7, 24),
    )

    assert result["total_value"] == 220.0
    assert result["market_data_date"] == "2026-07-23"
    assert result["valuation_status"] == "COMPLETE"
    assert result["expected_stock_count"] == 1
    assert result["priced_stock_count"] == 1
    assert result["missing_price_tickers"] == []
    assert snapshot_calls[0][0:2] == ("user-1", date(2026, 7, 24))


def test_calculate_current_portfolio_marks_partial_and_skips_snapshot(monkeypatch):
    holdings = [
        {"ticker": "NVDA", "avg_price": 90.0, "quantity": 2.0},
        {"ticker": "TSLA", "avg_price": 200.0, "quantity": 1.0},
    ]
    snapshot_calls = []
    monkeypatch.setattr(
        realtime_portfolio,
        "load_holdings",
        lambda user_id, session_factory: holdings,
    )
    monkeypatch.setattr(
        realtime_portfolio,
        "upsert_snapshot",
        lambda *args: snapshot_calls.append(args),
    )

    result = calculate_current_portfolio(
        "user-1",
        session_factory=object(),
        price_loader=lambda tickers: {
            "NVDA": {
                "price": 110.0,
                "prev_close": 100.0,
                "change_pct": 10.0,
                "price_date": "2026-07-23",
            },
        },
        snapshot_date=date(2026, 7, 24),
    )

    assert result["valuation_status"] == "PARTIAL"
    assert result["expected_stock_count"] == 2
    assert result["priced_stock_count"] == 1
    assert result["missing_price_tickers"] == ["TSLA"]
    assert snapshot_calls == []

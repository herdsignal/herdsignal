from scheduler.realtime_portfolio import empty_portfolio, value_holdings


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

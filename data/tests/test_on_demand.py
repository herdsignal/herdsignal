from scheduler.on_demand import calculate_many


def test_calculate_many_normalizes_deduplicates_and_isolates_failures():
    calls = []

    def calculate_one(ticker: str, force: bool) -> dict:
        calls.append((ticker, force))
        if ticker == "BAD":
            raise RuntimeError("failed")
        return {"ticker": ticker}

    result = calculate_many(
        [" nvda ", "NVDA", "", "bad", "spy"],
        calculate_one=calculate_one,
        force=True,
    )

    assert calls == [("NVDA", True), ("BAD", True), ("SPY", True)]
    assert result["results"] == [{"ticker": "NVDA"}, {"ticker": "SPY"}]
    assert result["errors"] == [{"ticker": "BAD", "error": "failed"}]

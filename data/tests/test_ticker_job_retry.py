from unittest.mock import MagicMock

from scheduler.ticker_job import collect_ticker_frames_with_retry


def test_retries_only_failed_tickers_and_keeps_successful_frames() -> None:
    calls: dict[str, int] = {}

    def collect(ticker: str) -> str:
        calls[ticker] = calls.get(ticker, 0) + 1
        if ticker == "SNDK" and calls[ticker] == 1:
            raise RuntimeError("temporary")
        return f"frame-{ticker}"

    frames, failed, recovered = collect_ticker_frames_with_retry(
        ["AAPL", "SNDK"], collect
    )

    assert frames == {"AAPL": "frame-AAPL", "SNDK": "frame-SNDK"}
    assert failed == []
    assert recovered == ["SNDK"]
    assert calls == {"AAPL": 1, "SNDK": 2}


def test_returns_final_failures_after_one_retry() -> None:
    collect = MagicMock(side_effect=RuntimeError("down"))

    frames, failed, recovered = collect_ticker_frames_with_retry(["AAPL"], collect)

    assert frames == {}
    assert failed == ["AAPL"]
    assert recovered == []
    assert collect.call_count == 2

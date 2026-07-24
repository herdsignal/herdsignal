"""요청 기반 HERD 계산과 캐시 조회."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable

from init_db import HerdIndicator, HerdScore

logger = logging.getLogger(__name__)


def calculate_on_demand(
    ticker: str,
    *,
    force: bool,
    cache_days: int,
    session_factory,
    collect: Callable,
    calculate: Callable,
    save: Callable,
    today: date | None = None,
) -> dict:
    """캐시가 유효하면 반환하고, 아니면 새 HERD 값을 계산해 저장한다."""
    normalized_ticker = ticker.upper().strip()
    if not normalized_ticker:
        raise ValueError("ticker must not be blank")

    calculation_date = today or date.today()
    cache_cutoff = calculation_date - timedelta(days=cache_days)
    latest_score = None

    with session_factory() as session:
        latest_score = (
            session.query(HerdScore)
            .filter(HerdScore.ticker == normalized_ticker)
            .order_by(HerdScore.score_date.desc())
            .first()
        )
        if not force and latest_score and latest_score.score_date >= cache_cutoff:
            indicator_row = (
                session.query(HerdIndicator)
                .filter(
                    HerdIndicator.ticker == normalized_ticker,
                    HerdIndicator.score_date == latest_score.score_date,
                )
                .first()
            )
            indicators = _serialize_indicators(indicator_row)
            logger.info(
                "[Tier2][%s] 캐시 히트 score_date=%s score=%.2f",
                normalized_ticker,
                latest_score.score_date,
                float(latest_score.herd_score),
            )
            return {
                "ticker": normalized_ticker,
                "score": float(latest_score.herd_score),
                "stage": latest_score.herd_stage,
                "signal": latest_score.signal or "HOLD",
                "indicators": indicators,
                "score_date": str(latest_score.score_date),
                "from_cache": True,
            }

    logger.info(
        "[Tier2][%s] %s — 최신=%s",
        normalized_ticker,
        "강제 갱신" if force else "캐시 미스",
        latest_score.score_date if latest_score else "없음",
    )
    frame = collect(normalized_ticker)
    result = calculate(normalized_ticker, frame)
    if not save(normalized_ticker, result, frame):
        raise RuntimeError(f"[{normalized_ticker}] HERD 계산 결과 DB 저장 실패")

    return {
        "ticker": normalized_ticker,
        "score": result["score"],
        "stage": result["stage"],
        "signal": result.get("signal", "HOLD"),
        "indicators": result["indicators"],
        "score_date": str(calculation_date),
        "from_cache": False,
    }


def calculate_many(
    tickers: list[str],
    *,
    calculate_one: Callable[[str, bool], dict],
    force: bool,
) -> dict:
    """중복과 빈 값을 제거한 뒤 여러 종목을 독립적으로 계산한다."""
    results: list[dict] = []
    errors: list[dict] = []
    normalized = dict.fromkeys(
        ticker.upper().strip()
        for ticker in tickers
        if ticker and ticker.strip()
    )
    for ticker in normalized:
        try:
            results.append(calculate_one(ticker, force))
        except Exception as exc:
            logger.error("[Tier2][%s] 배치 갱신 실패: %s", ticker, exc, exc_info=True)
            errors.append({"ticker": ticker, "error": str(exc)})
    return {"results": results, "errors": errors}


def _serialize_indicators(indicator_row) -> dict:
    if indicator_row is None:
        return {}
    return {
        "weekly_rsi": float(indicator_row.weekly_rsi or 0),
        "monthly_rsi": float(indicator_row.monthly_rsi or 0),
        "position_52w": float(indicator_row.position_52w or 0),
        "ma200_deviation": float(indicator_row.ma200_deviation or 0),
        "volume_strength": float(indicator_row.volume_strength or 0),
    }

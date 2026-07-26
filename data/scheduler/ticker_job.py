"""Tier 1 종목별 HERD 계산을 실행하고 성공·실패만 반환한다."""

from __future__ import annotations

import logging
from collections.abc import Callable

from herd.errors import InsufficientModelHistoryError

logger = logging.getLogger(__name__)


def execute_tickers(
    tickers: list[str],
    collect: Callable,
    calculate: Callable,
    save: Callable,
    on_success: Callable | None = None,
    validate: Callable | None = None,
) -> tuple[list[str], list[str], list[str]]:
    success: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []
    total = len(tickers)
    for index, ticker in enumerate(tickers, start=1):
        logger.info("[Tier1][%s] 처리 시작 (%s/%s)", ticker, index, total)
        try:
            frame = collect(ticker)
            if validate is not None:
                validate(ticker, frame)
            result = calculate(ticker, frame)
            if save(ticker, result, frame):
                success.append(ticker)
                if on_success is not None:
                    on_success(ticker, frame)
                logger.info(
                    "[Tier1][%s] 완료 score=%.2f stage=%s",
                    ticker, result["score"], result["stage"],
                )
            else:
                failed.append(ticker)
                logger.error("[Tier1][%s] DB 저장 실패", ticker)
        except InsufficientModelHistoryError as exc:
            skipped.append(ticker)
            logger.warning(
                "[Tier1][%s] 모델 입력 적격성 제외: %s",
                ticker,
                exc,
            )
        except Exception as exc:
            failed.append(ticker)
            logger.error("[Tier1][%s] 처리 중 예외: %s", ticker, exc, exc_info=True)
    return success, failed, skipped

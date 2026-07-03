"""
collectors/sector_collector.py — HERD v4 섹터 상대 강도 보정

yfinance에서 종목 섹터와 90일 수익률을 조회하고,
섹터 ETF 대비 상대 수익률을 HERD 보정 승수로 변환한다.
"""

import logging
from pathlib import Path
import sys

import yfinance as yf

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from config.settings import (  # noqa: E402
    DEFAULT_SECTOR_ETF,
    SECTOR_ETF_MAP,
    SECTOR_RELATIVE_DAYS,
    SECTOR_RELATIVE_MULTIPLIERS,
)

logger = logging.getLogger(__name__)


def _get_sector(ticker: str) -> str | None:
    """yfinance quoteSummary에서 섹터명을 조회한다."""
    try:
        info = yf.Ticker(ticker).info or {}
        sector = info.get("sector")
        return str(sector) if sector else None
    except Exception as e:
        logger.debug(f"[{ticker}] 섹터 조회 실패: {e}")
        return None


def _get_lookback_return(ticker: str, days: int) -> float | None:
    """최근 N거래일 기준 수익률을 반환한다."""
    try:
        hist = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
    except Exception as e:
        logger.debug(f"[{ticker}] 섹터 강도 가격 조회 실패: {e}")
        return None

    if hist is None or hist.empty or "Close" not in hist:
        return None

    close = hist["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    close = close.dropna()
    if len(close) < 2:
        return None

    lookback = min(days, len(close) - 1)
    start = float(close.iloc[-lookback - 1])
    end = float(close.iloc[-1])
    if start == 0:
        return None

    return (end / start - 1) * 100


def _multiplier_from_relative_strength(relative_strength: float) -> float:
    """섹터 ETF 대비 상대 수익률을 HERD v4 승수로 변환한다."""
    if relative_strength > 15:
        return SECTOR_RELATIVE_MULTIPLIERS["strong_outperform"]
    if relative_strength > 5:
        return SECTOR_RELATIVE_MULTIPLIERS["outperform"]
    if relative_strength >= -5:
        return SECTOR_RELATIVE_MULTIPLIERS["neutral"]
    if relative_strength >= -15:
        return SECTOR_RELATIVE_MULTIPLIERS["underperform"]
    return SECTOR_RELATIVE_MULTIPLIERS["strong_underperform"]


def get_sector_multiplier(ticker: str) -> float:
    """
    종목 90일 수익률과 섹터 ETF 90일 수익률의 차이를 보정 승수로 반환한다.

    섹터 조회 실패, ETF/가격 데이터 부족, 네트워크 오류는 모두 1.0으로 폴백한다.
    """
    try:
        normalized = ticker.upper()
        sector = _get_sector(normalized)
        sector_etf = SECTOR_ETF_MAP.get(sector or "", DEFAULT_SECTOR_ETF)

        stock_return = _get_lookback_return(normalized, SECTOR_RELATIVE_DAYS)
        sector_return = _get_lookback_return(sector_etf, SECTOR_RELATIVE_DAYS)
        if stock_return is None or sector_return is None:
            logger.debug(f"[{ticker}] 섹터 강도 데이터 부족 — 기본값 1.0 사용")
            return SECTOR_RELATIVE_MULTIPLIERS["neutral"]

        relative_strength = stock_return - sector_return
        multiplier = _multiplier_from_relative_strength(relative_strength)
        logger.info(
            f"[{ticker}] 섹터 강도 보정: sector={sector or 'N/A'} etf={sector_etf} "
            f"stock={stock_return:+.1f}% sector={sector_return:+.1f}% "
            f"relative={relative_strength:+.1f}% multiplier={multiplier:.2f}"
        )
        return multiplier
    except Exception as e:
        logger.warning(f"[{ticker}] 섹터 보정 승수 계산 실패 — 기본값 1.0 사용: {e}")
        return SECTOR_RELATIVE_MULTIPLIERS["neutral"]

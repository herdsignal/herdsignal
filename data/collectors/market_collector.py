"""
collectors/market_collector.py — 시장 레퍼런스 데이터 수집

SPY 현재가와 1개월 수익률을 yfinance로 조회한다.
Spring Boot MarketService의 ProcessBuilder가 이 모듈을 호출한다.
"""

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

logger = logging.getLogger(__name__)

_TICKER = "SPY"


def get_spy_market_data() -> dict:
    """
    SPY 현재가와 1개월 수익률을 yfinance로 조회한다.

    period="35d"(약 5주)로 데이터를 가져와
    첫 종가(≈1개월 전)와 마지막 종가(현재)로 수익률을 계산한다.

    Returns:
        {
            "ticker":        str,    # "SPY"
            "current_price": float,  # 최신 종가 (약 15분 지연)
            "return_1m_pct": float,  # 1개월 수익률 (%)
            "price_date":    str,    # 최신 종가 기준 날짜 (YYYY-MM-DD)
        }

    Raises:
        RuntimeError: yfinance 조회 실패 또는 데이터 부족 시
    """
    df = yf.download(
        tickers=_TICKER,
        period="35d",        # 약 5주 — 1개월 수익률 계산에 충분
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if df.empty:
        raise RuntimeError(f"[{_TICKER}] yfinance 반환 데이터 없음")

    # 단일 종목 yf.download는 Close가 Series 또는 1열 DataFrame으로 반환됨
    raw = df["Close"]
    closes = (raw if isinstance(raw, pd.Series) else raw[_TICKER]).dropna()

    if len(closes) < 2:
        raise RuntimeError(f"[{_TICKER}] 가격 데이터 부족: {len(closes)}행")

    current_price = float(closes.iloc[-1])
    price_1m_ago  = float(closes.iloc[0])   # 기간 첫날 종가 (≈ 1개월 전)
    return_1m_pct = (current_price - price_1m_ago) / price_1m_ago * 100
    price_date    = str(closes.index[-1].date())

    result = {
        "ticker":        _TICKER,
        "current_price": round(current_price, 2),
        "return_1m_pct": round(return_1m_pct, 2),
        "price_date":    price_date,
    }

    logger.info(
        f"[market_collector][{_TICKER}] "
        f"현재가=${current_price:.2f}  1개월 수익률={return_1m_pct:+.2f}%  날짜={price_date}"
    )
    return result


if __name__ == "__main__":
    # 직접 실행 시 stdout에 JSON 출력 (ProcessBuilder 호환)
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(get_spy_market_data()))

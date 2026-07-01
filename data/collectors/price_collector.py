"""
collectors/price_collector.py — yfinance 실시간 현재가 조회

yfinance의 무료 티어는 약 15분 지연 데이터를 제공한다.
여러 종목을 한번에 다운로드해 API 호출 횟수를 최소화한다.
"""

import logging
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

logger = logging.getLogger(__name__)


def get_current_prices(tickers: list) -> dict:
    """
    여러 종목의 현재가(15분 지연)를 yfinance로 일괄 조회한다.

    단일·다중 종목 모두 yf.download 한 번으로 처리.
    실패한 종목은 None으로 반환해 호출자가 제외 여부를 결정.

    Args:
        tickers: 종목 티커 목록 (예: ["NVDA", "AAPL"])

    Returns:
        {
            "NVDA": {
                "price":      float,  # 최신 종가 (15분 지연)
                "prev_close": float,  # 전일 종가
                "change_pct": float,  # 전일 대비 등락률 (%)
            },
            "AAPL": None,  # 조회 실패 시 None
            ...
        }
    """
    if not tickers:
        return {}

    # 결과 초기화 — 조회 실패 종목은 None 유지
    result: dict = {ticker: None for ticker in tickers}

    try:
        # yf.download로 전체 티커 한번에 조회 (최근 5영업일)
        # auto_adjust=True: 배당·분할 조정 종가 사용 (Adj Close → Close)
        df = yf.download(
            tickers=tickers,
            period="5d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        if df.empty:
            logger.warning(f"[price_collector] yfinance 반환 데이터 없음: {tickers}")
            return result

        # Close 컬럼 추출 — 단일·다중 종목 구조 통일
        raw_close = df["Close"]
        if isinstance(raw_close, pd.Series):
            # 단일 종목: Series → 1열 DataFrame으로 변환
            close_df = pd.DataFrame({tickers[0]: raw_close})
        else:
            # 다중 종목: DataFrame (컬럼 = 티커)
            close_df = raw_close

        for ticker in tickers:
            try:
                if ticker not in close_df.columns:
                    logger.warning(f"[price_collector][{ticker}] 컬럼 없음")
                    continue

                # NaN 행 제거 후 최신 2개 값 사용
                closes = close_df[ticker].dropna()
                if closes.empty:
                    logger.warning(f"[price_collector][{ticker}] 유효한 종가 없음")
                    continue

                current_price = float(closes.iloc[-1])
                # 전일 종가가 없으면 현재가로 대체 (등락률 = 0)
                prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else current_price
                change_pct = (
                    (current_price - prev_close) / prev_close * 100
                    if prev_close > 0 else 0.0
                )

                result[ticker] = {
                    "price":      round(current_price, 4),
                    "prev_close": round(prev_close, 4),
                    "change_pct": round(change_pct, 4),
                }
                logger.info(
                    f"[price_collector][{ticker}] "
                    f"현재가=${current_price:.2f}  전일=${prev_close:.2f}  "
                    f"등락={change_pct:+.2f}%"
                )

            except Exception as e:
                logger.error(f"[price_collector][{ticker}] 가격 파싱 실패: {e}")
                result[ticker] = None

    except Exception as e:
        logger.error(f"[price_collector] yfinance 일괄 조회 실패: {e}", exc_info=True)

    return result

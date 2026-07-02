"""
collectors/stock_info_collector.py — 개별 종목 기본 재무정보 수집

yfinance .info를 통해 시가총액·PER·EPS·영업이익률·매출·배당수익률을 조회한다.
Spring Boot FinancialsService의 ProcessBuilder가 이 모듈을 호출한다.
"""

import json
import logging
import sys
from pathlib import Path

import yfinance as yf

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

logger = logging.getLogger(__name__)


def get_stock_financials(ticker: str) -> dict:
    """
    yfinance .info에서 재무 지표 6개를 추출해 반환한다.

    operatingMargins·dividendYield는 yfinance가 소수(0.30)로 반환하므로
    ×100 처리해 퍼센트값(30.0)으로 반환한다.
    데이터가 없는 필드는 None으로 반환한다.

    Args:
        ticker: 종목 티커 (예: "AAPL")

    Returns:
        {
            "ticker":           str,
            "market_cap":       float | None,  # 시가총액 (USD)
            "trailing_pe":      float | None,  # PER (TTM)
            "eps":              float | None,  # EPS (TTM, USD)
            "operating_margin": float | None,  # 영업이익률 (%)
            "total_revenue":    float | None,  # 매출 (TTM, USD)
            "dividend_yield":   float | None,  # 배당수익률 (%)
        }
    """
    ticker = ticker.upper().strip()
    logger.info(f"[stock_info_collector][{ticker}] yfinance .info 조회 시작")

    info = yf.Ticker(ticker).info

    def to_float(val):
        """None이거나 숫자가 아니면 None 반환."""
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    def to_pct(val):
        """소수 비율 → 퍼센트 변환. None이면 None."""
        f = to_float(val)
        return round(f * 100, 2) if f is not None else None

    result = {
        "ticker":           ticker,
        "market_cap":       to_float(info.get("marketCap")),
        "trailing_pe":      to_float(info.get("trailingPE")),
        "eps":              to_float(info.get("trailingEps")),
        "operating_margin": to_pct(info.get("operatingMargins")),
        "total_revenue":    to_float(info.get("totalRevenue")),
        "dividend_yield":   to_pct(info.get("dividendYield")),
    }

    logger.info(
        f"[stock_info_collector][{ticker}] 조회 완료 — "
        f"시가총액={result['market_cap']}  PER={result['trailing_pe']}  "
        f"영업이익률={result['operating_margin']}%"
    )
    return result


if __name__ == "__main__":
    # 직접 실행 시 stdout에 JSON 출력 (ProcessBuilder 호환)
    import sys as _sys
    logging.basicConfig(level=logging.INFO)
    _ticker = _sys.argv[1] if len(_sys.argv) > 1 else "AAPL"
    print(json.dumps(get_stock_financials(_ticker)))

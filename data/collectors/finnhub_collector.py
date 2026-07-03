"""
collectors/finnhub_collector.py — Finnhub API 데이터 수집

수집 대상:
  1. 실적 서프라이즈 (EPS 실제값 vs 예상값)
  2. 애널리스트 평균 목표가
  3. 백테스트용 과거 실적 전체 히스토리 (look-ahead bias 방지)

무료 플랜 rate limit: 분당 60회 → 각 호출 후 0.5초 딜레이 적용
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys

import requests

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from config.settings import EPS_SURPRISE_MULTIPLIERS, FINNHUB_API_KEY  # noqa: E402

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# API 설정 상수
# ──────────────────────────────────────────────
_BASE_URL      = "https://finnhub.io/api/v1"
_REQUEST_DELAY = 0.5   # 호출 간 최소 대기 (초) — 분당 60회 제한 준수
_TIMEOUT       = 10    # HTTP 요청 타임아웃 (초)

# 실적 발표는 분기 마감 후 평균 45일 내 공표 → look-ahead bias 방지 기준일
_EARNINGS_REPORT_LAG_DAYS = 45


# ──────────────────────────────────────────────
# 내부 헬퍼 — HTTP 요청
# ──────────────────────────────────────────────
def _get(endpoint: str, params: dict) -> dict | list | None:
    """
    Finnhub REST API에 GET 요청을 보내고 JSON 응답을 반환한다.
    네트워크 오류 또는 HTTP 에러 시 None 반환.
    rate limit 준수를 위해 호출 후 _REQUEST_DELAY 초 대기.
    """
    if not FINNHUB_API_KEY:
        logger.error("FINNHUB_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return None

    params = dict(params)  # 원본 딕셔너리 변경 방지
    params["token"] = FINNHUB_API_KEY
    url = f"{_BASE_URL}/{endpoint}"

    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        logger.error(f"Finnhub API HTTP 오류 [{endpoint}] {resp.status_code}: {e}")
        return None
    except requests.RequestException as e:
        logger.error(f"Finnhub API 요청 실패 [{endpoint}]: {e}")
        return None
    finally:
        # rate limit 준수 — 성공·실패 모두 딜레이 적용
        time.sleep(_REQUEST_DELAY)


# ──────────────────────────────────────────────
# 공개 함수 1 — 최근 분기 EPS 서프라이즈
# ──────────────────────────────────────────────
def get_earnings_surprise(ticker: str) -> float | None:
    """
    가장 최근 분기 EPS 서프라이즈 % 를 반환한다.
    예: 예상 $1.0, 실제 $1.2 → +20.0%

    Args:
        ticker: 종목 티커 (예: "AAPL")

    Returns:
        서프라이즈 % (양수=어닝 서프라이즈, 음수=어닝 쇼크)
        데이터 없거나 예상값이 0이면 None
    """
    data = _get("stock/earnings", {"symbol": ticker})

    if not data or not isinstance(data, list) or len(data) == 0:
        logger.debug(f"[{ticker}] 실적 데이터 없음")
        return None

    # Finnhub는 최신 분기가 첫 번째 항목
    latest   = data[0]
    actual   = latest.get("actual")
    estimate = latest.get("estimate")

    if actual is None or estimate is None or estimate == 0:
        logger.debug(f"[{ticker}] 서프라이즈 계산 불가 — actual={actual}, estimate={estimate}")
        return None

    # Finnhub가 surprisePercent를 제공하지만 직접 계산으로 일관성 유지
    surprise_pct = round((actual / estimate - 1) * 100, 2)
    logger.info(
        f"[{ticker}] 최근 분기 EPS 서프라이즈: {surprise_pct:+.1f}% "
        f"(실제={actual}, 예상={estimate}, 분기={latest.get('period')})"
    )
    return surprise_pct


def get_eps_surprise_multiplier(ticker: str) -> float:
    """
    최근 4분기 EPS 서프라이즈 연속 beat/miss 흐름을 HERD v4 보정 승수로 변환한다.

    ETF처럼 실적 데이터가 없거나 API가 실패하면 1.0을 반환해
    기존 HERD v3 점수에 영향을 주지 않는다.
    """
    try:
        history = get_earnings_history(ticker)
        surprises = [
            item["surprise_pct"]
            for item in history[:4]
            if item.get("surprise_pct") is not None
        ]
    except Exception as e:
        logger.warning(f"[{ticker}] EPS 보정 승수 계산 실패 — 기본값 1.0 사용: {e}")
        return EPS_SURPRISE_MULTIPLIERS["neutral"]

    if len(surprises) < 2:
        logger.debug(f"[{ticker}] EPS 보정 데이터 부족 — 기본값 1.0 사용")
        return EPS_SURPRISE_MULTIPLIERS["neutral"]

    latest_is_beat = surprises[0] > 0
    latest_is_miss = surprises[0] < 0

    if not latest_is_beat and not latest_is_miss:
        return EPS_SURPRISE_MULTIPLIERS["neutral"]

    streak = 0
    for surprise in surprises:
        if latest_is_beat and surprise > 0:
            streak += 1
        elif latest_is_miss and surprise < 0:
            streak += 1
        else:
            break

    if latest_is_beat:
        if streak >= 4:
            return EPS_SURPRISE_MULTIPLIERS["beat_4"]
        if streak == 3:
            return EPS_SURPRISE_MULTIPLIERS["beat_3"]
        if streak == 2:
            return EPS_SURPRISE_MULTIPLIERS["beat_2"]
        return EPS_SURPRISE_MULTIPLIERS["neutral"]

    if streak >= 4:
        return EPS_SURPRISE_MULTIPLIERS["miss_4"]
    if streak == 3:
        return EPS_SURPRISE_MULTIPLIERS["miss_3"]
    if streak == 2:
        return EPS_SURPRISE_MULTIPLIERS["miss_2"]
    return EPS_SURPRISE_MULTIPLIERS["neutral"]


# ──────────────────────────────────────────────
# 공개 함수 2 — 애널리스트 평균 목표가
# ──────────────────────────────────────────────
def get_analyst_target(ticker: str) -> dict | None:
    """
    현재 애널리스트 컨센서스 목표가를 조회한다.
    현재가는 Finnhub quote 엔드포인트로 별도 조회.

    Args:
        ticker: 종목 티커 (예: "AAPL")

    Returns:
        {"current": 현재가, "target": 목표가(평균), "upside": 상승여력%}
        데이터 없으면 None
    """
    # 목표가 조회 (API 호출 1회)
    target_data = _get("stock/price-target", {"symbol": ticker})

    # 현재가 조회 (API 호출 2회 — rate limit 고려)
    quote_data = _get("quote", {"symbol": ticker})

    if not target_data or not quote_data:
        logger.debug(f"[{ticker}] 목표가 또는 현재가 데이터 없음")
        return None

    target_mean   = target_data.get("targetMean")
    current_price = quote_data.get("c")   # c = current price

    if not target_mean or not current_price or current_price == 0:
        logger.debug(
            f"[{ticker}] 유효하지 않은 데이터 — "
            f"target={target_mean}, current={current_price}"
        )
        return None

    upside = round((target_mean / current_price - 1) * 100, 1)
    result = {
        "current": round(float(current_price), 2),
        "target":  round(float(target_mean),   2),
        "upside":  upside,
    }
    logger.info(
        f"[{ticker}] 목표가: ${result['target']:.2f} "
        f"(현재 ${result['current']:.2f}, 상승여력 {result['upside']:+.1f}%)"
    )
    return result


# ──────────────────────────────────────────────
# 공개 함수 3 — 백테스트용 과거 실적 히스토리
# ──────────────────────────────────────────────
def get_earnings_history(ticker: str) -> list[dict]:
    """
    전체 과거 실적 데이터를 반환한다.
    백테스트에서 look-ahead bias를 방지하기 위해
    각 분기의 "데이터 사용 가능 날짜"를 함께 제공한다.

    Look-ahead bias 방지 로직:
    - Finnhub API는 실적 발표일(report date)을 직접 제공하지 않음
    - 분기 마감일(period) + 45일을 보수적 발표 추정일로 사용
    - 백테스트에서 이 날짜 이후 데이터만 해당 분기 서프라이즈 참조 가능

    Args:
        ticker: 종목 티커

    Returns:
        최신 분기부터 과거 순으로 정렬된 실적 리스트
        [
            {
                "period":       "2024-09-28",    # 분기 마감일 (str)
                "actual":       1.64,             # EPS 실제값
                "estimate":     1.60,             # EPS 예상값
                "surprise_pct": 2.5,              # 서프라이즈 % (None 가능)
                "available_after": datetime(...), # 이 날짜 이후부터 사용 가능
            },
            ...
        ]
    """
    data = _get("stock/earnings", {"symbol": ticker})

    if not data or not isinstance(data, list):
        logger.debug(f"[{ticker}] 과거 실적 데이터 없음")
        return []

    records: list[dict] = []
    for item in data:
        actual   = item.get("actual")
        estimate = item.get("estimate")
        period   = item.get("period")  # 예: "2024-09-28"

        # 서프라이즈 % 계산 (예상값이 0이면 계산 불가)
        if actual is not None and estimate is not None and estimate != 0:
            surprise_pct = round((actual / estimate - 1) * 100, 2)
        else:
            surprise_pct = None

        # 데이터 사용 가능 날짜 = 분기 마감 + 45일
        if period:
            try:
                period_dt     = datetime.strptime(period, "%Y-%m-%d")
                available_after = period_dt + timedelta(days=_EARNINGS_REPORT_LAG_DAYS)
            except ValueError:
                available_after = None
        else:
            available_after = None

        records.append({
            "period":          period,
            "actual":          actual,
            "estimate":        estimate,
            "surprise_pct":    surprise_pct,
            "available_after": available_after,
        })

    logger.info(f"[{ticker}] 실적 히스토리 {len(records)}개 수집 완료")
    return records  # Finnhub는 최신 → 과거 순으로 반환


# ──────────────────────────────────────────────
# 공개 함수 4 — 최근 뉴스 (StockDetail 연동)
# ──────────────────────────────────────────────
def get_company_news(ticker: str, days: int = 30) -> list[dict]:
    """
    최근 N일 회사 뉴스를 최대 5건 반환한다.
    Finnhub company-news 엔드포인트 사용 (무료 플랜 지원).

    Args:
        ticker: 종목 티커 (예: "AAPL")
        days:   조회 기간 (기본 30일)

    Returns:
        [{"headline": str, "source": str, "url": str, "date": "YYYY-MM-DD"}, ...]
        최대 5건. API 실패 또는 결과 없으면 빈 리스트.
    """
    from_dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    to_dt   = datetime.now().strftime("%Y-%m-%d")
    data = _get("company-news", {"symbol": ticker, "from": from_dt, "to": to_dt})

    if not data or not isinstance(data, list):
        logger.debug(f"[{ticker}] 뉴스 데이터 없음")
        return []

    results: list[dict] = []
    for item in data[:5]:  # 최신 5건만 (Finnhub는 최신순 정렬)
        ts = item.get("datetime", 0)
        try:
            date_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d") if ts else ""
        except (ValueError, OSError):
            date_str = ""
        results.append({
            "headline": item.get("headline", ""),
            "source":   item.get("source", ""),
            "url":      item.get("url", ""),
            "date":     date_str,
        })

    logger.info(f"[{ticker}] 뉴스 {len(results)}건 수집 완료")
    return results


# ──────────────────────────────────────────────
# 공개 함수 5 — 애널리스트 추천 컨센서스 (StockDetail 연동)
# ──────────────────────────────────────────────
def get_recommendation_trends(ticker: str) -> dict | None:
    """
    최신 1개월 애널리스트 추천 컨센서스를 반환한다.
    Finnhub stock/recommendation 엔드포인트 사용 (무료 플랜 지원).
    price_target은 프리미엄 전용이므로 사용하지 않는다.

    Args:
        ticker: 종목 티커 (예: "AAPL")

    Returns:
        {
            "strong_buy": int, "buy": int, "hold": int,
            "sell": int, "strong_sell": int,
            "total": int, "consensus": str, "period": str
        }
        데이터 없거나 실패 시 None.
    """
    data = _get("stock/recommendation", {"symbol": ticker})

    if not data or not isinstance(data, list) or len(data) == 0:
        logger.debug(f"[{ticker}] 애널리스트 추천 데이터 없음")
        return None

    latest = data[0]  # 가장 최근 달
    strong_buy  = int(latest.get("strongBuy",  0) or 0)
    buy         = int(latest.get("buy",        0) or 0)
    hold        = int(latest.get("hold",       0) or 0)
    sell        = int(latest.get("sell",       0) or 0)
    strong_sell = int(latest.get("strongSell", 0) or 0)
    total       = strong_buy + buy + hold + sell + strong_sell

    # 컨센서스 결정 — 비율 기반 간단 규칙
    if total == 0:
        consensus = "N/A"
    elif strong_buy / total >= 0.5:
        consensus = "Strong Buy"
    elif (strong_buy + buy) / total >= 0.5:
        consensus = "Buy"
    elif (strong_sell + sell) / total >= 0.5:
        consensus = "Sell"
    elif hold / total >= 0.35:
        consensus = "Hold"
    else:
        consensus = "Buy"

    result = {
        "strong_buy":  strong_buy,
        "buy":         buy,
        "hold":        hold,
        "sell":        sell,
        "strong_sell": strong_sell,
        "total":       total,
        "consensus":   consensus,
        "period":      latest.get("period", ""),
    }
    logger.info(f"[{ticker}] 컨센서스: {consensus} (총 {total}명)")
    return result


# ──────────────────────────────────────────────
# 공개 함수 6 — 내부자 거래 (StockDetail 연동)
# ──────────────────────────────────────────────
def get_insider_transactions(ticker: str, limit: int = 10) -> list[dict]:
    """
    최근 내부자 거래를 최대 N건 반환한다.
    Finnhub stock/insider-transactions 엔드포인트 사용 (무료 플랜 지원).

    Args:
        ticker: 종목 티커 (예: "AAPL")
        limit:  최대 반환 건수 (기본 10)

    Returns:
        [{"name": str, "transaction_code": str, "share": int, "date": "YYYY-MM-DD"}, ...]
        "P"=매수, "S"=매도. 실패 시 빈 리스트.
    """
    data = _get("stock/insider-transactions", {"symbol": ticker})

    if not data or not isinstance(data, dict):
        logger.debug(f"[{ticker}] 내부자 거래 데이터 없음")
        return []

    transactions = data.get("data", [])
    if not transactions or not isinstance(transactions, list):
        return []

    results: list[dict] = []
    for tx in transactions[:limit]:
        share = tx.get("share", 0)
        results.append({
            "name":             tx.get("name", ""),
            "transaction_code": tx.get("transactionCode", ""),
            "share":            int(share) if share is not None else 0,
            "date":             tx.get("transactionDate", ""),
        })

    logger.info(f"[{ticker}] 내부자 거래 {len(results)}건 수집 완료")
    return results


# ──────────────────────────────────────────────
# 내부 헬퍼 — 백테스트에서 날짜 기준 서프라이즈 조회
# ──────────────────────────────────────────────
def get_surprise_at_date(
    earnings_history: list[dict],
    target_date: datetime,
) -> float | None:
    """
    특정 날짜 기준으로 사용 가능한 가장 최근 EPS 서프라이즈를 반환한다.
    look-ahead bias 방지: available_after <= target_date 인 첫 번째 항목만 사용.

    Args:
        earnings_history: get_earnings_history() 반환값 (최신 → 과거 순)
        target_date:      조회 기준 날짜 (백테스트 시뮬레이션 날짜)

    Returns:
        사용 가능한 가장 최근 서프라이즈 % (없으면 None)
    """
    for record in earnings_history:
        available = record.get("available_after")
        if available is None:
            continue
        # available_after가 target_date 이전이면 이 데이터를 사용할 수 있음
        if available <= target_date:
            return record["surprise_pct"]
    return None

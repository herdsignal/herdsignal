"""
collectors/finnhub_collector.py — Finnhub API 데이터 수집

수집 대상:
  1. 실적 서프라이즈 (EPS 실제값 vs 예상값)
  2. 심볼 검색
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
# 공개 함수 0 — 심볼 검색
# ──────────────────────────────────────────────
def search_symbols(query: str, limit: int = 8) -> list[dict]:
    """
    회사명 또는 티커 문자열로 Finnhub 심볼 후보를 조회한다.

    Args:
        query: 검색어 (예: "Sandisk", "SNDK")
        limit: 최대 반환 개수

    Returns:
        [
            {
                "ticker": "SNDK",
                "name": "SANDISK CORPORATION",
                "type": "Common Stock",
                "display_symbol": "SNDK",
            },
            ...
        ]
    """
    normalized = (query or "").strip()
    if len(normalized) < 1:
        return []

    data = _get("search", {"q": normalized})
    if not data or not isinstance(data, dict):
        return []

    results = data.get("result")
    if not isinstance(results, list):
        return []

    symbols: list[dict] = []
    seen: set[str] = set()
    for item in results:
        symbol = (item.get("symbol") or item.get("displaySymbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue

        # HerdService 티커 검증과 맞춰 영숫자·점·하이픈 티커만 허용한다.
        if not all(ch.isalnum() or ch in ".-" for ch in symbol):
            continue

        seen.add(symbol)
        symbols.append({
            "ticker": symbol,
            "name": item.get("description") or symbol,
            "type": item.get("type") or "Stock",
            "display_symbol": item.get("displaySymbol") or symbol,
        })
        if len(symbols) >= limit:
            break

    return symbols


# ──────────────────────────────────────────────
# 공개 함수 0-1 — 회사 프로필
# ──────────────────────────────────────────────
def get_company_profile(ticker: str) -> dict | None:
    """
    Finnhub company profile2에서 회사명, 섹터, 로고 URL을 조회한다.

    Returns:
        {
            "ticker": "AAPL",
            "name": "Apple Inc",
            "sector": "Technology",
            "logo_url": "https://...",
        }
        데이터가 없거나 API가 실패하면 None.
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return None

    data = _get("stock/profile2", {"symbol": symbol})
    if not data or not isinstance(data, dict):
        return None

    name = data.get("name")
    sector = data.get("finnhubIndustry")
    logo_url = data.get("logo")

    if not any([name, sector, logo_url]):
        return None

    return {
        "ticker": symbol,
        "name": name,
        "sector": sector,
        "logo_url": logo_url,
    }


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
# 공개 함수 2 — 백테스트용 과거 실적 히스토리
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

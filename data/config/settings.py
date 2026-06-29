"""
config/settings.py — 전역 설정값 관리
환경변수(.env)에서 값을 읽어 각 모듈에 제공한다.
"""

import os
import logging
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드 (data/ 기준 상위 폴더 탐색 없이 현재 위치 우선)
load_dotenv()


# ──────────────────────────────────────────────
# MariaDB 접속 정보
# ──────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "herdsignal")

# SQLAlchemy 커넥션 URL (pymysql 드라이버 사용)
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)


# ──────────────────────────────────────────────
# Finnhub API 키 (실적 서프라이즈, 애널리스트 목표가)
# 무료 플랜: 분당 60회 호출 제한
# ──────────────────────────────────────────────
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")


# ──────────────────────────────────────────────
# yfinance 데이터 수집 기간 설정
# ──────────────────────────────────────────────
# 기본 5년치 데이터를 수집해 RSI·MA200 등 장기 지표 계산에 사용
YFINANCE_PERIOD = os.getenv("YFINANCE_PERIOD", "5y")

# 월봉·주봉 RSI 계산에 필요한 최소 데이터 기간 (단위: 년)
MIN_HISTORY_YEARS = int(os.getenv("MIN_HISTORY_YEARS", "2"))


# ──────────────────────────────────────────────
# HERD Index 가중치 (6개 지표, 합계 = 1.0)
# ──────────────────────────────────────────────
# v3: 거래량 강도 제거 — 백테스트에서 선행성 1.5일로 거의 무의미함이 증명됨
#     잉여 10%를 선행 지표(월봉RSI·52주위치·200일이격도)에 재배분
#   월봉 RSI      24% — 장기 모멘텀 (가장 선행성 강함, +4%p)
#   주봉 RSI      19% — 중기 모멘텀 (+1%p)
#   52주 위치     19% — 연간 가격 위치 (+1%p)
#   200일 이격도  18% — 중기 추세 이탈 (+4%p)
#   거래량 강도    0% — 비활성화 (코드는 유지, v4 복원 가능)
#   200주 MA      20% — 장기 구조적 저점/고점
HERD_WEIGHTS = {
    "monthly_rsi":      float(os.getenv("WEIGHT_MONTHLY_RSI",   "0.24")),  # 월봉 RSI
    "weekly_rsi":       float(os.getenv("WEIGHT_WEEKLY_RSI",    "0.19")),  # 주봉 RSI
    "52w_position":     float(os.getenv("WEIGHT_52W_POSITION",  "0.19")),  # 52주 고저 위치
    "ma200_deviation":  float(os.getenv("WEIGHT_MA200_DEV",     "0.18")),  # 200일 이동평균 이격도
    "volume_strength":  float(os.getenv("WEIGHT_VOLUME",        "0.00")),  # 거래량 강도 (비활성화)
    "ma200_weekly":     float(os.getenv("WEIGHT_MA200_WEEKLY",  "0.20")),  # 200주 이동평균 위치
}

# 가중치 합계 검증 — 서버 기동 시 합이 1.0이 아니면 즉시 오류 발생
_weight_sum = round(sum(HERD_WEIGHTS.values()), 10)
assert _weight_sum == 1.0, (
    f"HERD_WEIGHTS 합계가 1.0이어야 합니다. 현재 합계: {_weight_sum}"
)


# ──────────────────────────────────────────────
# HERD Index 단계 판정 임계값
# ──────────────────────────────────────────────
# 백분위수 정규화 방식 기반으로 도출한 최적 임계값.
# 10y 데이터에서 Rush / Flee 각 5~10% 발생 빈도를 목표로 설정.
HERD_THRESHOLDS = {
    "rush": float(os.getenv("HERD_RUSH_THRESHOLD", "75")),  # Rush(익절 구간): 이 값 이상
    "flee": float(os.getenv("HERD_FLEE_THRESHOLD", "15")),  # Flee(매수 구간): 이 값 이하
}


# ──────────────────────────────────────────────
# on-demand 계산 캐싱 유효 기간
# ──────────────────────────────────────────────
# calculate_on_demand() 호출 시 이 기간 이내 데이터가 있으면 재계산 없이 반환
CACHE_DAYS = int(os.getenv("CACHE_DAYS", "7"))


# ──────────────────────────────────────────────
# 스케줄러 실행 시간 (미국 동부시간 ET 기준)
# 미국 주식시장 마감: ET 16:00 → 30분 후 16:30 실행
# 여름(EDT, UTC-4) → 한국시간 다음날 05:30 KST
# 겨울(EST, UTC-5) → 한국시간 다음날 06:30 KST
# ──────────────────────────────────────────────
SCHEDULER_HOUR_ET   = int(os.getenv("SCHEDULER_HOUR_ET",   "16"))  # 16시 (오후 4시)
SCHEDULER_MINUTE_ET = int(os.getenv("SCHEDULER_MINUTE_ET", "30"))  # 30분


# ──────────────────────────────────────────────
# 로깅 설정
# ──────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
)

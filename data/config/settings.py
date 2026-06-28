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
# yfinance 데이터 수집 기간 설정
# ──────────────────────────────────────────────
# 기본 5년치 데이터를 수집해 RSI·MA200 등 장기 지표 계산에 사용
YFINANCE_PERIOD = os.getenv("YFINANCE_PERIOD", "5y")

# 월봉·주봉 RSI 계산에 필요한 최소 데이터 기간 (단위: 년)
MIN_HISTORY_YEARS = int(os.getenv("MIN_HISTORY_YEARS", "2"))


# ──────────────────────────────────────────────
# HERD Index 가중치 (5개 지표, 합계 = 1.0)
# ──────────────────────────────────────────────
# 각 지표를 동일 비중(20%)으로 초기화. 추후 백테스트 결과에 따라 조정 가능.
HERD_WEIGHTS = {
    "monthly_rsi":      float(os.getenv("WEIGHT_MONTHLY_RSI",   "0.2")),  # 월봉 RSI
    "weekly_rsi":       float(os.getenv("WEIGHT_WEEKLY_RSI",    "0.2")),  # 주봉 RSI
    "52w_position":     float(os.getenv("WEIGHT_52W_POSITION",  "0.2")),  # 52주 고저 위치
    "ma200_deviation":  float(os.getenv("WEIGHT_MA200_DEV",     "0.2")),  # 200일 이동평균 이격도
    "volume_strength":  float(os.getenv("WEIGHT_VOLUME",        "0.2")),  # 거래량 강도
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

"""
config/database.py — SQLAlchemy 엔진 및 세션 관리
settings.py의 DATABASE_URL을 기반으로 엔진을 생성하고
다른 모듈에서 DB 세션을 주입받을 수 있도록 팩토리를 제공한다.
"""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# ORM Base — 모든 모델 클래스가 상속
# ──────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────
# 엔진 생성
# ──────────────────────────────────────────────
def create_db_engine(database_url: str | None = None, echo: bool = False):
    """
    SQLAlchemy 엔진을 생성한다.

    Args:
        database_url: 커넥션 URL. None이면 settings.DATABASE_URL 사용.
        echo: True이면 실행 SQL을 로그에 출력 (디버그용).

    Returns:
        Engine 인스턴스

    Raises:
        RuntimeError: DB 연결 실패 시
    """
    url = database_url or DATABASE_URL

    # MariaDB(pymysql)와 SQLite 모두 지원
    is_mysql = url.startswith("mysql")

    connect_args = {}
    pool_kwargs: dict = {}

    if is_mysql:
        # MariaDB: 커넥션 풀 설정
        pool_kwargs = {
            "pool_size":    5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 1800,   # 30분마다 커넥션 갱신 (타임아웃 방지)
        }
    else:
        # SQLite: 멀티스레드 허용 (테스트용)
        connect_args = {"check_same_thread": False}

    try:
        engine = create_engine(
            url,
            echo=echo,
            connect_args=connect_args,
            **pool_kwargs,
        )
        # 연결 즉시 검증
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"DB 연결 성공: {_mask_url(url)}")
        return engine

    except Exception as e:
        logger.error(f"DB 연결 실패: {e}")
        raise RuntimeError(f"DB 연결 실패 — 설정을 확인하세요: {e}") from e


def _mask_url(url: str) -> str:
    """로그 출력용: 비밀번호를 마스킹한 URL 반환."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.password:
            masked = parsed._replace(
                netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}"
            )
            return urlunparse(masked)
    except Exception:
        pass
    return url


# ──────────────────────────────────────────────
# 세션 팩토리
# ──────────────────────────────────────────────
def get_session_factory(engine):
    """
    SessionLocal 팩토리를 반환한다.
    호출부에서 `with session_factory() as session:` 형태로 사용.
    """
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

"""
setup_default_tickers.py — 기본 종목 초기 등록 스크립트

실행:
    cd data/
    python setup_default_tickers.py

등록 대상:
    - SPY  → user_id='spy_benchmark'  (S&P500 벤치마크 — 시장 대표 지수)
    - NVDA → user_id='local'
    - AAPL → user_id='local'
    - TSLA → user_id='local'

이미 존재하는 종목은 건너뜀 (upsert 아닌 INSERT-if-not-exists).
"""

import sys
from pathlib import Path

# data/ 를 패키지 루트로 추가 (어느 위치에서 실행해도 import 가능)
_DATA_DIR = Path(__file__).resolve().parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from config.database import create_db_engine, get_session_factory  # noqa: E402
from init_db import UserPortfolio                                   # noqa: E402

# ── 등록할 기본 종목 ──────────────────────────────────
# SPY는 spy_benchmark userId로 분리해 일반 포트폴리오와 구분
_DEFAULTS: list[dict] = [
    {"user_id": "spy_benchmark", "ticker": "SPY"},   # S&P500 벤치마크
    {"user_id": "local",         "ticker": "NVDA"},
    {"user_id": "local",         "ticker": "AAPL"},
    {"user_id": "local",         "ticker": "TSLA"},
]


def setup_defaults() -> None:
    engine  = create_db_engine()
    Session = get_session_factory(engine)

    inserted: list[str] = []
    skipped:  list[str] = []

    with Session() as session:
        for item in _DEFAULTS:
            label = f"{item['ticker']} ({item['user_id']})"

            # 이미 존재하면 건너뜀 (UniqueConstraint: user_id + ticker)
            exists = session.query(UserPortfolio).filter_by(
                user_id=item["user_id"],
                ticker=item["ticker"],
            ).first()

            if exists:
                skipped.append(label)
            else:
                session.add(UserPortfolio(
                    user_id=item["user_id"],
                    ticker=item["ticker"],
                ))
                inserted.append(label)

        session.commit()

    # ── 결과 출력 ──
    print("\n=== 기본 종목 등록 결과 ===")
    if inserted:
        print(f"  ✅ 신규 등록 ({len(inserted)}개): {', '.join(inserted)}")
    if skipped:
        print(f"  ⏭  이미 존재 ({len(skipped)}개): {', '.join(skipped)}")
    if not inserted:
        print("  → 추가할 종목 없음 (모두 이미 등록됨)")

    # ── 전체 포트폴리오 목록 출력 ──
    with Session() as session:
        rows = (
            session.query(UserPortfolio)
            .order_by(UserPortfolio.user_id, UserPortfolio.ticker)
            .all()
        )

    print("\n=== user_portfolio 전체 목록 ===")
    for r in rows:
        print(f"  user_id={r.user_id!r:22s}  ticker={r.ticker!r}")
    print()


if __name__ == "__main__":
    setup_defaults()

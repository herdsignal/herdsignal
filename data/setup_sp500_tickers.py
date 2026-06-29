"""
setup_sp500_tickers.py — S&P500 전종목 + 추가 종목 일괄 등록 및 HERD 계산

사용법:
    cd data/
    python setup_sp500_tickers.py             # 종목 등록만
    python setup_sp500_tickers.py --run-now   # 등록 + 즉시 HERD 계산 (약 80분 소요)

등록 대상:
    - S&P500 전종목  (Wikipedia 파싱)
    - BTC-USD, ETH-USD, IONQ, PLTR  (추가 종목)
    userId = 'market_all'  (local / spy_benchmark 와 구분)
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import io
import requests
import pandas as pd

# data/ 를 패키지 루트로 추가
_DATA_DIR = Path(__file__).resolve().parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from config.database import create_db_engine, get_session_factory  # noqa: E402
from collectors.stock_collector import collect                       # noqa: E402
from herd.calculator import run as calc_herd                        # noqa: E402
from herd.saver import save_herd_result                             # noqa: E402
from init_db import UserPortfolio                                   # noqa: E402

logging.basicConfig(
    level=logging.WARNING,   # setup 스크립트 실행 시 로그 최소화 (print로 진행 상황 출력)
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 설정 상수
# ──────────────────────────────────────────────
USER_ID = "market_all"   # S&P500 시장 전체 user_id

# S&P500 외 추가 종목 (암호화폐 + 포트폴리오 핵심 종목)
EXTRA_TICKERS: list[str] = ["BTC-USD", "ETH-USD", "IONQ", "PLTR"]

# Wikipedia S&P500 종목 목록 URL
_SP500_WIKI_URL = (
    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
)

# 모듈 레벨 DB 엔진/세션 (등록 + 계산 모두 재사용)
_engine         = create_db_engine()
_SessionFactory = get_session_factory(_engine)


# ──────────────────────────────────────────────
# 1. S&P500 티커 수집
# ──────────────────────────────────────────────
def fetch_sp500_tickers() -> list[str]:
    """
    Wikipedia에서 S&P500 구성 종목 티커를 파싱한다.
    yfinance 호환을 위해 '.' → '-' 로 치환한다 (예: BRK.B → BRK-B).
    Wikipedia는 기본 User-Agent 요청을 403으로 차단하므로 브라우저 헤더를 사용한다.
    """
    print("  Wikipedia에서 S&P500 종목 목록 파싱 중...", end=" ", flush=True)
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(_SP500_WIKI_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        # StringIO로 감싸야 HTML 문자열을 파일 경로로 오인하지 않음
        tables = pd.read_html(io.StringIO(resp.text))
        # 첫 번째 테이블의 'Symbol' 컬럼 사용
        raw = tables[0]["Symbol"].tolist()
    except Exception as e:
        print(f"실패\n  오류: {e}")
        raise RuntimeError(f"S&P500 목록 파싱 실패: {e}") from e

    # yfinance 형식으로 정규화 (BRK.B → BRK-B)
    normalized = [str(t).strip().replace(".", "-") for t in raw if str(t).strip()]
    print(f"{len(normalized)}개 파싱 완료")
    return normalized


def build_ticker_list() -> list[str]:
    """S&P500 + 추가 종목 합집합을 알파벳 오름차순으로 반환한다."""
    sp500 = fetch_sp500_tickers()
    all_tickers = sorted(set(sp500) | set(EXTRA_TICKERS))
    return all_tickers


# ──────────────────────────────────────────────
# 2. user_portfolio 등록
# ──────────────────────────────────────────────
def register_tickers(tickers: list[str]) -> tuple[list[str], list[str]]:
    """
    user_portfolio 테이블에 tickers를 user_id='market_all' 로 등록한다.
    이미 존재하는 종목은 INSERT IGNORE 방식으로 스킵한다.

    Returns:
        (inserted_list, skipped_list)
    """
    inserted: list[str] = []
    skipped:  list[str] = []

    with _SessionFactory() as session:
        # 이미 등록된 market_all 종목을 일괄 조회 (쿼리 횟수 최소화)
        existing = {
            row.ticker
            for row in session.query(UserPortfolio)
            .filter_by(user_id=USER_ID)
            .all()
        }

        for ticker in tickers:
            if ticker in existing:
                skipped.append(ticker)
            else:
                session.add(UserPortfolio(user_id=USER_ID, ticker=ticker))
                inserted.append(ticker)

        session.commit()

    return inserted, skipped


# ──────────────────────────────────────────────
# 3. HERD 일괄 계산 (--run-now 모드)
# ──────────────────────────────────────────────
def run_herd_for_all(tickers: list[str]) -> None:
    """
    market_all에 등록된 전 종목 HERD를 순차 계산하고 DB에 저장한다.
    개별 종목 실패 시 다음 종목으로 계속 진행한다.
    """
    total = len(tickers)
    success_list: list[str] = []
    failed_list:  list[str] = []

    print()
    print(f"  HERD 일괄 계산 시작 — 총 {total}개 종목")
    print(f"  예상 소요 시간: 약 {total * 10 // 60}~{total * 15 // 60}분")
    print("  " + "─" * 60)

    start_total = time.time()

    for idx, ticker in enumerate(tickers, start=1):
        t0 = time.time()
        try:
            # 데이터 수집 (save_herd_result에 df 필요)
            df = collect(ticker)

            # HERD 계산 (calculator.run 내부에서 collect 재호출 — 기존 패턴 유지)
            herd_result = calc_herd(ticker)

            # DB 저장
            ok = save_herd_result(ticker, herd_result, df)

            elapsed = time.time() - t0
            if ok:
                success_list.append(ticker)
                stage = herd_result.get("stage", "?")
                score = herd_result.get("score", 0.0)
                print(
                    f"  [{idx:>3}/{total}] {ticker:<8} 완료  "
                    f"({score:.2f}, {stage})  {elapsed:.1f}s"
                )
            else:
                failed_list.append(ticker)
                print(
                    f"  [{idx:>3}/{total}] {ticker:<8} DB 저장 실패  {elapsed:.1f}s"
                )

        except Exception as e:
            elapsed = time.time() - t0
            failed_list.append(ticker)
            # 오류 메시지를 한 줄로 압축 (스택트레이스 없이)
            err_msg = str(e).split("\n")[0][:60]
            print(
                f"  [{idx:>3}/{total}] {ticker:<8} 실패 — {err_msg}  {elapsed:.1f}s"
            )

    # ── 최종 요약 ─────────────────────────────
    total_elapsed = time.time() - start_total
    minutes, seconds = divmod(int(total_elapsed), 60)

    print()
    print("  " + "═" * 60)
    print(f"  HERD 일괄 계산 완료 — {minutes}분 {seconds}초 소요")
    print(f"  전체 {total}개  |  성공 {len(success_list)}개  |  실패 {len(failed_list)}개")

    if failed_list:
        print()
        print(f"  실패 종목 ({len(failed_list)}개):")
        # 한 줄에 10개씩 출력
        chunk_size = 10
        for i in range(0, len(failed_list), chunk_size):
            chunk = failed_list[i:i + chunk_size]
            print(f"    {', '.join(chunk)}")

    print("  " + "═" * 60)


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="S&P500 전종목 + 추가 종목 등록 및 HERD 일괄 계산",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예:
  python setup_sp500_tickers.py             종목 등록만
  python setup_sp500_tickers.py --run-now   등록 + 즉시 HERD 계산 (약 80분)
""",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="종목 등록 후 즉시 전 종목 HERD 계산까지 실행 (약 80분 소요)",
    )
    args = parser.parse_args()

    print()
    print("═" * 60)
    print("  S&P500 전종목 + 추가 종목 등록 스크립트")
    print(f"  대상 user_id: '{USER_ID}'")
    print("═" * 60)

    # ── 1. 티커 목록 구성 ──────────────────────
    print()
    print("  [1/2] 티커 목록 구성 중...")
    tickers = build_ticker_list()
    print(f"  S&P500 + 추가 종목 합계: {len(tickers)}개")
    print(f"  추가 종목: {', '.join(EXTRA_TICKERS)}")

    # ── 2. DB 등록 ─────────────────────────────
    print()
    print("  [2/2] user_portfolio 등록 중...")
    inserted, skipped = register_tickers(tickers)

    print(f"  신규 등록: {len(inserted)}개")
    print(f"  이미 존재 (스킵): {len(skipped)}개")

    # DB 전체 market_all 종목 수 확인
    with _SessionFactory() as session:
        total_db = (
            session.query(UserPortfolio)
            .filter_by(user_id=USER_ID)
            .count()
        )
    print(f"  market_all 총 등록 종목: {total_db}개")

    # ── 등록 결과 요약 ─────────────────────────
    print()
    print("═" * 60)
    print(f"  등록 완료 — market_all: {total_db}개 종목")
    if inserted:
        print(f"  신규 추가: {inserted[:5]}{' ...' if len(inserted) > 5 else ''}")
    print("═" * 60)

    # ── 3. HERD 계산 (--run-now 옵션) ──────────
    if args.run_now:
        # DB에서 market_all 전 종목 알파벳 오름차순으로 가져옴
        with _SessionFactory() as session:
            rows = (
                session.query(UserPortfolio)
                .filter_by(user_id=USER_ID)
                .order_by(UserPortfolio.ticker)
                .all()
            )
        all_market_tickers = [r.ticker for r in rows]
        run_herd_for_all(all_market_tickers)
    else:
        print()
        print("  HERD 계산은 실행되지 않았습니다.")
        print("  계산하려면: python setup_sp500_tickers.py --run-now")
        print()


if __name__ == "__main__":
    main()

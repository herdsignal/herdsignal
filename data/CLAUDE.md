# data/ — Python 데이터 엔진

최종 업데이트: 2026-07-03

## 이 폴더의 역할
yfinance로 주가 데이터 수집 + HERD Index 계산 + MariaDB 저장.
Spring Boot나 React와 직접 통신하지 않음. DB만 바라봄.
계산과 저장 전담. Spring Boot는 서빙만 담당.

## 폴더 구조
```
data/
├── collectors/             yfinance 데이터 수집
│   ├── stock_collector.py      주가 데이터 수집 (yfinance)
│   ├── price_collector.py      현재가 실시간 조회 (Tier3 사용)
│   ├── stock_info_collector.py 종목 재무정보 on-demand (yfinance .info)
│   └── finnhub_collector.py    Finnhub 수집기 (운영 미연결)
├── indicators/             개별 지표 계산
│   ├── rsi.py              RSI 계산 (주봉/월봉)
│   ├── ma.py               이동평균 계산
│   ├── position_52w.py     52주 고저 위치 계산
│   ├── volume.py           거래량 강도 계산
│   ├── ma200_weekly.py     200주 MA 위치 계산
│   └── bollinger.py        볼린저 밴드 (백테스트 전용)
├── herd/                   HERD Index 합산 알고리즘 + 저장
│   ├── calculator.py       6개 지표 가중합산 → HERD 점수 산출
│   ├── saver.py            HERD 결과를 MariaDB 4개 테이블에 UPSERT
│   ├── portfolio_calculator.py  포트폴리오 평가금액 계산 + 저장
│   ├── backtest.py         백테스트 엔진
│   ├── backtest_bollinger.py    볼린저 전략 백테스트
│   ├── backtest_config.py  백테스트 설정
│   ├── backtest_strategy.py     백테스트 전략 정의
│   ├── backtest_v3.py      v3 백테스트 (실적 서프라이즈 필터·트레일링 스탑)
│   ├── backtest_weight.py  가중치 탐색 백테스트
│   └── grid_search.py      가중치 그리드 서치
├── scheduler/
│   └── herd_scheduler.py   3-Tier 스케줄러 + on-demand 캐시
├── config/
│   ├── settings.py         설정값 (가중치, 임계값, 스케줄 등)
│   └── database.py         DB 엔진·세션 팩토리
├── init_db.py              ORM 모델 정의 + 테이블 초기화 스크립트
├── setup_default_tickers.py  기본 티커 등록 스크립트
├── setup_sp500_tickers.py  S&P 500 티커 등록 스크립트
├── compare_v1_v2.py        지표 버전 비교 스크립트
├── diagnose_xom.py         XOM 진단 스크립트
└── requirements.txt
```

## HERD Index 구성 지표 v3 (6개)

`settings.py`의 `HERD_WEIGHTS` 기준:

| 지표 | 가중치 | 키 | 비고 |
|------|-------|----|------|
| 월봉 RSI | 24% | `monthly_rsi` | 활성 |
| 주봉 RSI | 19% | `weekly_rsi` | 활성 |
| 52주 고저 위치 | 19% | `position_52w` | 활성 |
| MA200 이격도 | 18% | `ma200_deviation` | 활성 |
| 거래량 강도 | 0% | `volume_strength` | 비활성 — 계산하나 점수 미반영 |
| 200주 MA 위치 | 20% | `ma200_weekly` | 활성 |

`ma200_weekly`는 상장 기간이 200주 미만이면 가용 주봉 수로 대체 계산한다.

## 정규화 원칙
절대값이 아닌 종목별 역사적 상대값으로 정규화.
방식: `scipy.stats.percentileofscore` (백분위수 기반)
→ 모든 종목에 동일한 공식 적용 가능.
→ 엔비디아 RSI 75와 코카콜라 RSI 75가 다른 의미임을 자동 반영.

## 주요 설정 (settings.py)
| 키 | 값 | 설명 |
|----|-----|------|
| `YFINANCE_PERIOD` | `"5y"` | 기본 데이터 수집 기간 |
| `MIN_HISTORY_YEARS` | `2` | 계산에 필요한 최소 데이터 기간 |
| `CACHE_DAYS` | `7` | on-demand 캐시 유효기간 (일) |
| `SCHEDULER_HOUR_ET` | `16` | Tier1 실행 시각 (ET) |
| `SCHEDULER_MINUTE_ET` | `30` | Tier1 실행 분 (ET) |
| `FINNHUB_API_KEY` | — | Finnhub 키 (운영 미연결) |

DB URL은 `settings.py`에서 DB 사용자명/비밀번호를 URL 인코딩해 생성한다.
비밀번호에 `@` 같은 특수문자가 있어도 SQLAlchemy URL 파싱이 깨지지 않아야 한다.

## DB 저장 테이블 (init_db.py 정의)
`saver.py`는 HERD 계산 결과를 4개 테이블에 트랜잭션으로 저장:
- `stocks` — 종목 메타
- `herd_scores` — HERD 점수·단계·신호 (ticker + score_date UPSERT)
- `herd_indicators` — HERD 지표 분해값 (`ma200_weekly` 포함, `volume_strength`는 저장하나 가중치 0%)
- `daily_prices` — 최신 OHLCV

전체 테이블 목록 (`init_db.py`):
- `stocks`, `herd_scores`, `herd_indicators`, `daily_prices`
- `user_portfolio`, `user_watchlist`, `portfolio_history`

## 3-Tier 스케줄러 구조 (herd_scheduler.py)

**Tier 1 — 매일 자동 업데이트 (`run_herd_job`)**
- 실행 시각: 매일 16:30 ET (APScheduler BlockingScheduler)
- 대상: `user_portfolio` + `user_watchlist` 전체 (cache 제외) + SPY 고정
- 유저가 종목 추가 시 다음 스케줄부터 자동 포함
- 완료 후 `portfolio_history` 오늘 스냅샷 UPSERT

**Tier 2 — on-demand 실시간 계산 + 캐싱 (`calculate_on_demand`)**
- 검색/상세 조회 시 Spring Boot가 ProcessBuilder로 호출
- `CACHE_DAYS=7` 이내 데이터 있으면 DB 캐시 반환 (재계산 없음)
- 수동 새로고침 경로는 `force=True`로 호출해 캐시를 무시하고 재계산
- 포트폴리오 수동 새로고침은 `calculate_many_on_demand`로 여러 티커를 한 Python 프로세스에서 순차 갱신
- 캐시 미스 시 즉시 계산 → `user_id='cache'`로 저장

**Tier 3 — 실시간 포트폴리오 계산 (`calculate_current_portfolio`)**
- yfinance 현재가(15분 지연)로 즉시 평가금액 계산
- `daily_prices` DB를 거치지 않아 장중에도 최신 가격 반영
- `portfolio_history` UPSERT (오늘 날짜 스냅샷 갱신)

## 신호 파생 로직 (saver.py `_derive_signal`)
| 조건 | 신호 |
|------|------|
| score ≥ 75 | SELL |
| score ≥ 60 | REDUCE |
| score ≤ 15 | BUY |
| score ≤ 40 | ADD |
| 그 외 | HOLD |

## 코드 원칙
- 지표별로 파일 분리 (indicators/rsi.py, indicators/ma.py 등)
- DB 연결은 config/database.py에서만 관리
- yfinance 호출 실패 시 재시도 로직 포함
- 계산 결과 로깅 필수
- 하드코딩 금지 — 설정값은 config/settings.py에서 관리

## 작업 시 주의
- backend/, frontend/ 폴더는 읽지 말 것
- 이 폴더의 역할은 계산과 저장뿐 (서빙은 Spring Boot 담당)
- DB 스키마 변경 시 init_db.py와 saver.py 함께 수정
- `backtest_v3.py`의 실적 서프라이즈 필터·트레일링 스탑은 백테스트 코드이며 운영 계산 경로에 미연결

## AI 작업 원칙
- 실제 data/ 코드 기준으로 판단한다.
- 구현되지 않은 기능은 완료 처리하지 않는다.
- README보다 실제 코드를 우선한다.
- 추측하지 않는다.
- 작업 범위를 벗어난 파일은 수정하지 않는다.
- data/CLAUDE.md는 data/ 개발만을 위한 문서로 유지한다.

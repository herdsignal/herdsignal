# data/ — Python 데이터 엔진

최종 업데이트: 2026-07-05

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
│   ├── finnhub_collector.py    Finnhub 수집기 (심볼 검색, 회사 프로필, EPS 서프라이즈 보정)
│   └── sector_collector.py     섹터 ETF 상대 강도 보정
├── indicators/             개별 지표 계산
│   ├── rsi.py              RSI 계산 (주봉/월봉)
│   ├── ma.py               이동평균 계산
│   ├── position_52w.py     52주 고저 위치 계산
│   ├── volume.py           거래량 강도 계산
│   ├── ma200_weekly.py     200주 MA 위치 계산
│   └── bollinger.py        볼린저 밴드 (백테스트 전용)
├── herd/                   HERD Index 합산 알고리즘 + 저장
│   ├── calculator.py       6개 지표 가중합산 + v4 보정 승수 → HERD 점수 산출
│   ├── saver.py            HERD 결과를 MariaDB 4개 테이블에 UPSERT
│   ├── portfolio_calculator.py  포트폴리오 평가금액 계산 + 저장
│   ├── backtest.py         백테스트 엔진
│   ├── backtest_bollinger.py    볼린저 전략 백테스트
│   ├── backtest_config.py  백테스트 설정
│   ├── backtest_strategy.py     백테스트 전략 정의
│   ├── backtest_v3.py      v3 백테스트 (실적 서프라이즈 필터·트레일링 스탑)
│   ├── backtest_v4.py      v4 보정 승수 검증 백테스트
│   ├── backtest_v5_volatility.py  v5 후보 변동성 레이어 검증 백테스트
│   ├── backtest_action_layer.py   HERD Action Layer 동적 비율 검증 백테스트
│   ├── history_backfill.py        HERD 히스토리 차트용 과거 점수 백필
│   ├── signal_reliability.py      저장된 HERD 신호의 과거 성능 신뢰도 계산
│   ├── backtest_weight.py  가중치 탐색 백테스트
│   └── grid_search.py      가중치 그리드 서치
├── scheduler/
│   └── herd_scheduler.py   3-Tier 스케줄러 + on-demand 캐시
├── config/
│   ├── settings.py         설정값 (가중치, 임계값, 스케줄 등)
│   └── database.py         DB 엔진·세션 팩토리
├── init_db.py              ORM 모델 정의 + 테이블 초기화 스크립트
├── backfill_stock_profiles.py  stocks 회사명·섹터·로고 URL 백필 스크립트
├── setup_default_tickers.py  기본 티커 등록 스크립트
├── setup_sp500_tickers.py  S&P 500 티커 등록 스크립트
├── compare_v1_v2.py        지표 버전 비교 스크립트
├── diagnose_xom.py         XOM 진단 스크립트
└── requirements.txt
../.env                         루트 단일 환경변수 파일
```

## HERD Index 구성 지표 v4

v4는 v3 6개 지표 가중합산 점수(`herd_base`)를 먼저 계산한 뒤,
EPS 서프라이즈 승수와 섹터 상대 강도 승수를 곱해 최종 점수(`herd_v4`)를 만든다.

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

### v4 보정 승수
- EPS 보정: Finnhub 최근 4분기 EPS 서프라이즈 연속 beat/miss를 `eps_multiplier`로 변환한다.
- 섹터 강도 보정: 종목 90일 수익률과 섹터 ETF 90일 수익률 차이를 `sector_multiplier`로 변환한다.
- 보정 데이터가 없거나 API 호출이 실패하면 각 승수는 1.0으로 폴백해 v3 기본 점수를 보존한다.

### v5 후보 검증
- `backtest_v5_volatility.py`는 VIX/VXN/종목 실현변동성 백분위수 기반 변동성 레이어를 검증한다.
- 운영 계산에는 아직 반영하지 않으며, 4년/10년 비교에서 수익률·MDD·신호 변경률을 확인한 뒤 채택 여부를 판단한다.

### HERD_v5 Action Layer 검증
- `backtest_action_layer.py`는 HERD 점수와 가격 기반 추세 품질을 조합해 동적 매수/익절 비율을 검증한다.
- 운영 HERD 점수 저장값은 변경하지 않는다. HERD_v5는 backend 응답 시점에 HERD_v4 점수를 행동 비율로 번역하는 Action Layer다.
- 채택 기준은 수익률 보존율 70% 이상, MDD 개선 5%p 이상, 연평균 행동 수 4~10회 수준이다.

### 임계값 기준
- 운영 신호(`settings.py`, `saver.py`, Action Layer, 주요 백테스트)는 Rush 75 / Flee 15 기준을 사용한다.
- `calculator.py`의 `herd_stage` 라벨도 `HERD_THRESHOLDS`를 참조해 같은 기준을 따른다.
- frontend 표시 기준은 `frontend/src/utils/herdStage.js`에서 같은 값으로 관리한다.

### HERD 히스토리 백필
- `history_backfill.py`는 StockDetail/Dashboard HERD 히스토리 차트용으로 과거 HERD 점수를 `herd_scores`/`herd_indicators`에 채운다.
- 기본 대상은 포트폴리오 + 관심종목 + SPY이며, `--tickers SPY,AAPL`로 직접 지정할 수 있다. `stocks` 전체는 `--all-stocks`를 명시한 경우에만 포함한다.
- 기본 설정은 `HERD_BACKFILL_YEARS=3`, `HERD_BACKFILL_FREQ=weekly`, `HERD_BACKFILL_SOURCE_PERIOD=10y`다.
- 과거 시점별 EPS/섹터 승수는 무료 API로 안정적 복원이 어려워 백필에서는 `1.0`으로 저장한다. 최신 운영 점수는 기존 v4 계산 경로가 담당한다.
- 개별 티커 전체 실패는 stack trace 없이 warning으로 요약하고, 마지막에 실패 티커 목록만 출력한다.

### HERD 신호 신뢰도
- `signal_reliability.py`는 저장된 `herd_scores`와 yfinance 가격 데이터를 결합해 과거 신호 성능을 계산한다.
- Flee 이후 6개월 반등률, Rush 이후 3개월 하락/낙폭 발생률, Action Layer 방식의 MDD 개선, 수익률 보존율, 연간 행동 수를 반환한다.
- DB 스키마를 변경하지 않는 on-demand 분석이며, backend `GET /api/stocks/{ticker}/herd/reliability`가 ProcessBuilder로 호출한다.
- 기존 `qualityScore`는 데이터 완성도 신뢰도이고, `signal_reliability.py`는 신호 성능 신뢰도다. 두 개념을 혼동하지 않는다.

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
| `FINNHUB_API_KEY` | — | Finnhub 키 (심볼 검색·EPS 서프라이즈 보정) |
| `HERD_BACKFILL_YEARS` | `3` | HERD 히스토리 백필 기간 |
| `HERD_BACKFILL_FREQ` | `"weekly"` | 백필 저장 간격 (`daily`/`weekly`/`monthly`) |
| `HERD_BACKFILL_SOURCE_PERIOD` | `"10y"` | 백필 계산에 사용할 yfinance 원천 수집 기간 |

환경변수는 프로젝트 루트 `.env`에서만 로드한다. 기존 `data/.env`는 운영 기준이 아니며 새 설정은 추가하지 않는다.
DB URL은 `settings.py`에서 DB 사용자명/비밀번호를 URL 인코딩해 생성한다.
비밀번호에 `@` 같은 특수문자가 있어도 SQLAlchemy URL 파싱이 깨지지 않아야 한다.

## DB 저장 테이블 (init_db.py 정의)
`saver.py`는 HERD 계산 결과를 4개 테이블에 트랜잭션으로 저장:
- `stocks` — 종목 메타 (`name`, `sector`, `logo_url`은 Finnhub company profile 기반으로 비어 있을 때만 보강)
- `herd_scores` — HERD v4 최종 점수·단계·신호 (ticker + score_date UPSERT)
- `herd_indicators` — HERD 지표 분해값 (`ma200_weekly`, `herd_base`, `eps_multiplier`, `sector_multiplier` 포함)
- `daily_prices` — 최신 OHLCV

전체 테이블 목록 (`init_db.py`):
- `stocks`, `herd_scores`, `herd_indicators`, `daily_prices`
- `user_portfolio`, `user_watchlist`, `user_cash_balance`, `user_cash_history`, `portfolio_history`, `signal_journal`

`init_db.py`는 기존 DB에도 `stocks.logo_url` nullable 컬럼을 보강한다. Spring Boot가 `ddl-auto=validate`를 사용하므로 스키마 변경 후에는 init_db.py 실행으로 DB 컬럼을 맞춰야 한다.
`user_cash_balance`와 `user_cash_history`는 현금 보유액 현재값/일별 스냅샷 저장용이며, backend가 직접 저장한다. Python 계산 엔진은 현금 계산을 담당하지 않는다.
`signal_journal`은 HERD 판단 기록 장기 보관용 테이블이며, backend `/api/journal`이 직접 저장/조회한다. Python 계산 엔진은 판단 기록을 생성하지 않는다.
기존 종목의 회사명·섹터·로고가 비어 있으면 `backfill_stock_profiles.py`로 포트폴리오/관심종목/SPY 우선 보강한다. 전체 stocks 보강은 Finnhub 호출량이 커서 `--all-stocks`를 명시한 경우에만 수행한다.

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
- 캐시 미스 시 즉시 계산 → `herd_scores`/`herd_indicators`/`daily_prices` 저장

**Tier 3 — 실시간 포트폴리오 계산 (`calculate_current_portfolio`)**
- yfinance 1분봉 + prepost=True 현재가(15분 지연 가능)로 프리장/장중/애프터장 평가금액 계산
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
- `backtest_v4.py`는 현재 승수를 3년 HERD 시계열에 적용하는 sanity check이며, 과거 시점별 EPS/섹터 승수를 완전히 복원하지는 않음
- `backtest_v5_volatility.py`는 v5 후보 검증용이며, 운영 HERD 점수에는 아직 영향을 주지 않음
- `backtest_action_layer.py`는 HERD_v5 Action Layer 검증 기준이다. 운영 HERD 점수 저장값은 변경하지 않지만 backend API 응답의 행동 비율 계산에 반영된다.
- `backtest.py`, `compare_v1_v2.py`, `diagnose_xom.py` 등 초기 실험 스크립트는 연구/진단 아카이브로 본다. 운영 계산 기준은 `calculator.py`, `saver.py`, `scheduler/herd_scheduler.py`, `history_backfill.py`를 우선 확인한다.
- `backfill_spy.py`가 남아 있다면 과거 SPY 전용 백필 유틸로 보고, 신규 백필은 `history_backfill.py`를 사용한다.
- 로컬 실행은 루트에서 `./scripts/run-data.sh <script>`를 우선 사용한다.

## AI 작업 원칙
- 실제 data/ 코드 기준으로 판단한다.
- 구현되지 않은 기능은 완료 처리하지 않는다.
- README보다 실제 코드를 우선한다.
- 추측하지 않는다.
- 작업 범위를 벗어난 파일은 수정하지 않는다.
- data/CLAUDE.md는 data/ 개발만을 위한 문서로 유지한다.

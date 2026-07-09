# HerdSignal — 프로젝트 공통 지침

최종 업데이트: 2026-07-05

## 서비스 개요

미국주식 장기투자자를 위한 데이터 기반 타이밍 도구.
개별 주식마다 HERD Index(0~100)를 산출해 고점 익절 / 저점 추가매수 타이밍을 제안.

## 문서 역할

- README: 사용자/포트폴리오 문서. 프로젝트 소개, 실행 방법, 외부 공개용 설명을 담당.
- CLAUDE.md: AI 개발 문서. 실제 코드 기준 개발 상태, 작업 원칙, 구현 범위를 담당.

## 핵심 개념

- **HERD Index**: 개별주 군중심리 지표 (0~100)
- **5단계**: Flee → Scatter → Calm → Drift → Rush
- **서비스 철학**: Rush일 때 익절, Flee일 때 매수

현재 단계 표시와 행동 신호 기준은 Rush 75 / Flee 15 중심으로 통일한다.
세부 기준은 Python `HERD_THRESHOLDS`, backend Action Layer, frontend `utils/herdStage.js`를 함께 맞춘다.

## 모노레포 구조

```
herdsignal/
├── data/       Python 데이터 엔진
├── backend/    Spring Boot REST API
├── frontend/   React 대시보드
└── scripts/    루트 .env 기반 실행 스크립트
```

- `data/`: yfinance/Finnhub 수집, HERD 계산, MariaDB 저장, 스케줄러.
- `backend/`: MariaDB 데이터를 읽어 React에 제공하는 REST API.
- `frontend/`: Spring Boot API를 호출해 포트폴리오/종목/HERD 데이터와 판단 기록을 시각화.
- `.env`: 프로젝트 루트 단일 환경변수 파일. data/backend 실행은 모두 이 파일을 기준으로 한다.

## 데이터 흐름

```
yfinance → Python(HERD 계산) → MariaDB → Spring Boot API → React
```

Python은 계산 + 저장만. Spring Boot는 서빙만. 역할 분리 엄수.

## 기술 스택

- Python 3.11+ / yfinance / pandas / pandas-ta / scipy / SQLAlchemy / PyMySQL / APScheduler
- Spring Boot 3.5.3 / Java 17 / Gradle / JPA / MariaDB
- React 18.3 / Vite 5 / react-router-dom / axios / recharts

## AI 작업 원칙

- 실제 코드 기준으로 판단한다.
- 구현되지 않은 기능은 완료 처리하지 않는다.
- README보다 실제 코드를 우선한다.
- 추측하지 않는다.
- 작업 범위를 벗어난 파일은 수정하지 않는다.

## 공통 코드 원칙

- 함수/클래스 단위 역할 분리
- 예외처리 필수
- 하드코딩 금지 (설정값은 config 분리)
- 주석 필수
- 한 번에 하나씩 — 파일 구조 먼저 제안 후 코드 작성

## 커밋 메시지 규칙

형식:

```
git commit -m "type: 제목" -m "- 세부사항1" -m "- 세부사항2"
```

type 종류:

- `feat`: 새 기능 추가
- `fix`: 버그 수정
- `chore`: 설정, 패키지 등 기타 작업
- `refactor`: 코드 구조 개선 (기능 변경 없음)
- `docs`: 문서 수정

예시:

```
git commit -m "feat: RSI 계산 함수 구현" -m "- 월봉/주봉 RSI 계산 로직 추가" -m "- pandas_ta 라이브러리 활용" -m "- 종목별 역사적 상대값 정규화 적용"
```

규칙:

- 제목은 50자 이내
- 세부사항은 실제 변경된 내용 구체적으로
- 세부사항 2~4개 권장

### 언급 방식

커밋 타이밍이 되면 아래 형식으로 먼저 알려줄 것.

```
✅ 커밋 타이밍입니다.
작업 내용: (완성된 내용 한 줄 요약)
명령어:
git add .
git commit -m "type: 제목" -m "- 세부사항1" -m "- 세부사항2"
```

## 토큰 절약 규칙

- data/ 작업 시 backend/, frontend/ 파일 읽지 말 것
- backend/ 작업 시 data/, frontend/ 파일 읽지 말 것
- frontend/ 작업 시 data/, backend/ 파일 읽지 말 것
- 각 폴더의 CLAUDE.md만 추가로 참조할 것

## 현재 상태

### 완료

**data/**

- HERD Index v4 계산 (v3 6개 지표 기본 점수 + EPS 서프라이즈/섹터 상대 강도 보정 승수)
- MariaDB 저장 (stocks / herd_scores / herd_indicators / daily_prices — 4개 테이블 UPSERT)
- stocks 메타데이터 캐싱 (Finnhub company profile 기반 name / sector / logo_url)
- 3-Tier 스케줄러
  - Tier 1: 매일 16:30 ET 자동 계산 (user_portfolio + user_watchlist + SPY)
  - Tier 2: on-demand 계산 + 7일 캐시 (검색·상세 조회 시)
  - Tier 3: yfinance 실시간 포트폴리오 평가 + portfolio_history UPSERT
- HERD 히스토리 백필 (`data/herd/history_backfill.py`)
  - StockDetail/Dashboard HERD 히스토리 차트용 과거 점수 생성
  - 기본 대상: 포트폴리오 + 관심종목 + SPY (`--all-stocks` 명시 시 stocks 활성 종목 포함)
  - 과거 EPS/섹터 승수는 1.0으로 저장해 미래 데이터 누수를 피함
- HERD 신호 신뢰도 계산 (`data/herd/signal_reliability.py`)
  - 저장된 HERD 히스토리와 yfinance 가격으로 Flee/Rush 적중률, MDD 개선, 수익률 보존, 연간 행동 수 계산
  - DB 스키마 변경 없는 on-demand 분석
- 백테스트 코드 (backtest_v3.py, backtest_v4.py 기반)

**backend/**

- HERD 조회 API (`GET /api/stocks/{ticker}/herd`, `GET /api/portfolio/herd`)
- HERD 응답에 종목 메타데이터(companyName / sector / logoUrl) 포함
- HERD 강제 갱신 API (`POST /api/stocks/{ticker}/herd/refresh`, `POST /api/portfolio/herd/refresh`)
- 포트폴리오 전체 API (CRUD + summary + history + realtime + 평단가/수량 수정 + 현금 보유액)
- 관심 종목 전체 API (CRUD + HERD 조회)
- 시장 데이터 API (`GET /api/market/spy` — SPY 종가·1개월 수익률)
- 재무정보 API (`GET /api/stocks/{ticker}/financials` — 시가총액·PER·EPS 등)
- HERD 신호 신뢰도 API (`GET /api/stocks/{ticker}/herd/reliability` — 과거 신호 성능)
- Python on-demand 계산 연동 (ProcessBuilder)
- 전역 예외 처리 (404 / 409 / 500)

**frontend/**

- Dashboard: S&P 500 Herd Flow 배너(Overview 애니메이션 + Timeline HERD 히스토리), 총자산/현금 포함 포트폴리오 평가 요약, 편집 모드 현금 입력, 1개월/1년/전체 총자산 히스토리 차트(입출금 포함 총자산 변화로 표시), HERD 판단 기록 전체 요약, KRW/USD 통화 토글, 핵심 리밸런싱 체크, HERD 신호와 목표비중 차이를 함께 반영한 보유 종목 액션 카드, 편집 모드, 평단가·수량 수정 모달, localStorage 캐시, 빠른 새로고침 피드백
- StockDetail: HERD v4 점수·단계·신호, HERD_v6 Action Layer 행동 비율, 현재 신호 근거 데이터 보드, DB 기반 HERD 판단 기록(가격·수량·총액·수익률·메모)과 기록 요약, 현재 신호 기준 신뢰도, HERD Index 히스토리 차트, Fundamental Guard, 지표 분해·보정 승수
- StockDetail: 최근 3년 HERD 신호 신뢰도 데이터 보드(Flee/Rush 적중률, MDD 개선, 수익률 보존, 연간 행동 수)
- HERD 데이터 품질: 핵심 지표 완성도·200주 MA 포함 여부·v4 보정 승수·최신성을 기반으로 qualityScore/qualityLevel/qualityReasons 응답 제공. frontend에서는 낮은 품질만 `데이터 제한/부족`으로 표시한다.
- HERD 모델 구분: HERD_v4는 DB에 저장되는 점수 모델, HERD_v6는 HERD_v4 점수에 Progressive Action Layer를 얹은 응답 시점 행동 모델이다.
- HERD Action Layer: HERD 점수·지표 분해값·데이터 품질·최근 HERD 변화율을 기반으로 actionModelVersion/actionScore/actionLabel/actionRatio/actionRegime 응답 제공. frontend에서는 actionScore를 `강도`로 표시하고, DB 저장 없이 backend 응답 시점에 계산한다.
- HERD 신호 지속 기간: backend가 저장된 HERD 히스토리 기준으로 현재 signal/stage 시작일과 지속 일수를 응답하고, frontend는 보유종목/관심종목/상세 화면에 `신호 N일째`를 표시한다.
- Search: Finnhub 심볼 검색 API, Inclusion Check 상태 패널, 디바운스 검색, HERD 미리보기, 편입 판단, HERD 준비됨/계산 필요/데이터 부족 상태 표시, 최근 검색, 포트폴리오/관심종목 추가, 포트폴리오 추가 후 평단가·수량 입력 연결
- Watchlist: S&P 500 Herd Flow 배너, Buy Queue/Observe/Overheat 요약 보드, Flee/Scatter 우선 기회 대기열, 매수 후보 우선 Action Queue 리스트, 삭제
- StockAvatar: 회사 로고 URL이 있으면 로고 표시, 없거나 이미지 로딩 실패 시 티커 배지 fallback
- HERD Lab: 현재 HERD 모델 버전 검증 히어로 보드, 핵심 성과 수치, 종목별 백테스트 verdict, 5단계 행동 매트릭스. 표시 데이터는 `frontend/src/data/herdModelReport.js`에서 관리한다.
- Journal: StockDetail에서 저장한 HERD 판단 기록 전체 목록과 매수/익절 요약을 `signal_journal` DB 기반으로 표시
- 사이드바 노출 MVP 메뉴: 대시보드, 관심 종목, 종목 검색, HERD Lab
- 보류/내부 접근 라우트: AiRebalance(`/ai`), History(`/history`), Journal(`/journal`), HerdFlowPreview(`/herd-flow`)

**문서**

- data/CLAUDE.md 최신화
- README.md 최신화
- 루트 CLAUDE.md 최신화
- 루트 `.env` 단일화 및 실행 스크립트 (`scripts/run-backend.sh`, `scripts/run-data.sh`, `scripts/run-frontend.sh`)

### 진행 중

없음

### 다음 단계

- 실제 사용 시나리오 테스트와 버그 정리

---

## HERD Index 현재 버전 (운영 계산 기준)

### 알고리즘

- 정규화 방식: 백분위수 (scipy.stats.percentileofscore)
- 데이터 기간: 기본 5년 (`YFINANCE_PERIOD=5y`)
- 운영 계산: 6개 지표를 계산해 v3 기본 점수를 만들고, v4 보정 승수를 곱해 최종 점수 산출
- 구성 지표:
  - 월봉 RSI 24%
  - 주봉 RSI 19%
  - 52주 위치 19%
  - MA200 이격도 18%
  - 거래량 강도 0% (계산 코드는 유지, 운영 가중치 비활성)
  - 200주 MA 위치 20%
- HERD v4 보정:
  - EPS 서프라이즈 최근 4분기 연속 beat/miss → `eps_multiplier`
  - 90일 종목 수익률 - 섹터 ETF 수익률 → `sector_multiplier`
  - 최종 점수: `herd_v4 = herd_base × eps_multiplier × sector_multiplier`
- `herd_scores.herd_score`는 최종 v4 점수를 저장한다.
- `herd_indicators` DB 테이블과 `HerdScoreResponse` API 응답은 200주 MA 위치(`ma200_weekly`), `herd_base`, `eps_multiplier`, `sector_multiplier`, `herd_v4`를 포함함.

### 임계값

- Rush ≥ 75 → 30% 익절
- Drift 60~75 → 5% 익절
- Calm 40~60 → 보유 유지
- Scatter 15~40 → 10% 추가매수 (1단계 신호)
- Flee ≤ 15 → 30% 추가매수 (2단계 신호)

### 신호 규칙

- 신호 중복 제거: 20일 이내 재발생 무시
- `saver.py` 기준 신호 파생:
  - score >= 75: SELL
  - score >= 60: REDUCE
  - score <= 15: BUY
  - score <= 40: ADD
  - 그 외: HOLD
- `backtest_v4.py`는 현재 승수를 3년 HERD 시계열에 적용하는 sanity check이며, 과거 시점별 EPS/섹터 승수를 완전히 복원하지는 않음.

### 백테스트 검증 결과

- 평균 MDD 8.9%p 개선
- 평균 수익률 59.3% 보존
- Flee 신호 분포 6~10% (이상적)
- Rush 신호 분포 3~9% (종목 특성에 따라 상이)

---

## 현재 구현 완료 기능

### data/

- [x] yfinance 기반 가격 수집
- [x] HERD Index 계산 (`herd/calculator.py`)
- [x] MariaDB 저장 (`herd/saver.py`)
- [x] 9개 테이블 생성 (`init_db.py`)
  - stocks
  - herd_scores
  - herd_indicators
  - daily_prices
  - user_portfolio
  - user_watchlist
  - user_cash_balance
  - user_cash_history
  - portfolio_history
- [x] Tier 1 일일 스케줄러 (`scheduler/herd_scheduler.py`)
  - user_portfolio + user_watchlist + SPY 대상
  - 매일 16:30 ET 실행
- [x] Tier 2 on-demand HERD 계산
  - 상세/검색 조회 시 DB에 최신 데이터가 없으면 Python 즉시 계산
  - `CACHE_DAYS=7`
  - `herd_scores` 최신 날짜 기준 캐시 판정
- [x] Tier 3 실시간 포트폴리오 평가
  - yfinance 현재가 기반 계산
  - portfolio_history 오늘 스냅샷 UPSERT

### backend/

- [x] HERD 조회 API
  - GET `/api/stocks/{ticker}/herd`
  - GET `/api/portfolio/herd`
- [x] 포트폴리오 API
  - GET `/api/portfolio`
  - POST `/api/portfolio`
  - DELETE `/api/portfolio/{ticker}`
  - GET `/api/portfolio/summary`
  - GET `/api/portfolio/history?period=month|year|all`
  - GET `/api/portfolio/cash`
  - PUT `/api/portfolio/cash`
  - PATCH `/api/portfolio/{ticker}/avg-price`
  - GET `/api/portfolio/realtime`
- [x] 관심 종목 API
  - GET `/api/watchlist`
  - GET `/api/watchlist/herd`
  - POST `/api/watchlist`
  - DELETE `/api/watchlist/{ticker}`
- [x] Python on-demand 계산 연동
  - DB에 HERD 데이터가 없으면 ProcessBuilder로 Python 계산 실행
- [x] 전역 예외 처리
  - 404 ResourceNotFound
  - 409 DuplicateResource

### frontend/

- [x] Dashboard (`/`)
  - S&P 500 Herd Flow 배너
  - 현금 포함 포트폴리오 평가금액 요약
  - 총자산 히스토리 차트
  - KRW/USD 통화 토글
  - 목표 비중 기반 핵심 리밸런싱 체크
  - 보유 수량/평단/목표 비중 차이를 표시하는 보유 종목 카드
  - 편집 모드/삭제
  - 평단가·수량 수정 모달
  - localStorage 캐시 우선 로딩
  - 수동 새로고침은 DB 조회 기반 빠른 갱신
- [x] StockDetail (`/stock/:ticker`)
  - HERD v4 점수/단계/Timing Signal
  - Action Layer 행동 비율
  - 현재 신호 기준 HERD 신뢰도
  - 지표 분해 UI + EPS/섹터 강도 보정 승수
  - HERD Index 히스토리 차트
  - 포트폴리오 추가
  - 관심종목 추가
- [x] Search (`/search`)
  - 300ms 디바운스 검색
  - HERD 미리보기
  - 최근 검색 localStorage 저장
  - 포트폴리오/관심종목 추가
- [x] Watchlist (`/watchlist`)
  - S&P 500 Herd Flow 배너
  - 관심 종목 HERD 카드
  - 매수 대기열
  - 매수 우선도순 자동 정렬
  - 관심 종목 삭제
- [x] HERD Lab (`/herd-lab`)
  - 현재 HERD 모델 버전(`HERD_v6`) 검증 데이터 보드
  - Action Layer 백테스트 요약
  - 5단계 행동 매트릭스
- [x] AiRebalance (`/ai`)
  - 보류/내부 접근 라우트, 사이드바 미노출
  - 목표 비중·현금 목표·리밸런싱 예산 설정
  - 보수적/표준/공격적 리밸런싱 강도 선택
  - 현재 비중 vs 목표 비중 비교
  - 규칙 기반 매수/매도/보류 실행안
- [x] History (`/history`)
  - 보류/내부 접근 라우트, 사이드바 미노출
  - 월/년 기간 토글
  - recharts 기반 총 평가금액 차트
  - portfolio_history 시계열 표시
  - 시작 대비·고점 대비·점검 포인트 자산 진단
- [x] HerdFlowPreview (`/herd-flow`)
  - 실제 데이터와 무관한 Herd Flow 5단계 애니메이션 확인용
  - 사이드바 미노출

### frontend localStorage

- `hs_portfolio_realtime`: 포트폴리오 실시간 평가 캐시
- `hs_portfolio_herd`: 포트폴리오 HERD 캐시
- `hs_spy_herd`: SPY HERD 캐시
- `hs_spy_history`: SPY HERD 히스토리 캐시
- `hs_cache_time`: 캐시 저장 시각
- `hs_recent_searches`: 최근 검색
- `hs_target_weights`: 포트폴리오 종목별 목표 비중
- `hs_rebalance_settings`: 리밸런싱 예산·현금 목표·강도 설정
- `herdsignal_currency`: 통화 표시 모드

HERD 판단 기록은 localStorage가 아니라 DB `signal_journal`과 backend `/api/journal`을 기준으로 저장한다.

---

## 미구현 또는 부분 구현

- StockDetail 최근 뉴스, 애널리스트 컨센서스, 내부자 거래 섹션은 frontend에서 제거됨. 뉴스/애널리스트/내부자 거래 관련 backend API/DTO와 Python collector 함수도 제거했다.
- StockDetail 재무정보는 원본 재무제표 섹션이 아니라 Fundamental Guard로 표시한다. 이 카드는 안전 보증이 아니라 PER/EPS/영업이익률/매출/시가총액 기반의 재무 경고 필터다.
- 리밸런싱 플랜은 아직 Claude API를 호출하지 않는 frontend 규칙 기반 MVP다.
- 목표 비중과 리밸런싱 설정은 localStorage 저장이며 DB 저장 기능은 없다.
- History의 자산 진단은 portfolio_history 기반 수익률/MDD 요약이며 실제 HERD 전략 백테스트가 아니다.
- `backtest_v5_volatility.py`는 v5 후보 검증용이며 운영 HERD 점수에는 미반영이다.
- 로그인/멀티유저 UI는 없음. MVP는 `AppConstants.DEFAULT_USER_ID` 기반 `local` 사용자 고정.
- SPY 배너의 SPY 종가, 1개월 수익률 표시는 아직 `—` placeholder.

---

## README와 현재 코드의 차이

- README.md / README.ko.md는 2026-07-05 기준 현재 MVP 상태를 반영한다.
- 공개 소개 문서에서는 운영 중인 HERD v4, Herd Flow, HERD_v6 Action Layer, Dashboard/Watchlist/Search/HERD Lab 중심 MVP만 전면에 둔다.
- README에서 구현 완료로 보이면 안 되는 항목은 Claude API 기반 AI 리밸런싱, 멀티유저/인증, 증권사 연동, 배포다.
- StockDetail은 가격 차트가 아니라 HERD Index 히스토리 차트를 보여준다.
- 뉴스/애널리스트/내부자 거래/가격 히스토리 API는 현재 backend 공개 API에서 제거했다. 필요하면 별도 기능으로 재도입한다.
- README의 로드맵은 ROADMAP.md와 역할이 겹치지 않게 간결화한다.

---

## 현재 한계 (인지하고 개발할 것)

- 운영 HERD 계산은 여전히 기술적 지표 중심이다.
- 거시경제 지표(VIX, DXY, 10년물 국채 수익률)는 운영 계산에 반영되어 있지 않다.
- 옵션 Put/Call, 공매도 비율, 종목 간 상관관계는 운영 계산에 반영되어 있지 않다.
- Python과 Spring Boot는 DB 중심으로 통신하지만, on-demand 계산과 실시간 포트폴리오 평가에서는 Spring Boot가 ProcessBuilder로 Python을 실행한다.
- 리밸런싱 플랜은 보류/내부 접근 기능이며 아직 투자 성과를 검증하는 백테스트 엔진과 연결되어 있지 않다.
- backend 공개 API는 현재 MVP에서 쓰는 HERD/검색/재무/포트폴리오/관심종목 중심으로 정리했다.
- Dashboard.jsx, StockDetail.jsx, HerdService.java는 기능이 누적되어 큰 파일이 되었다. 동작 안정화 이후 화면 섹션/서비스 책임 단위로 분리 검토한다.
- HERD_v6 후보는 Rush/Flee 내부 강도와 피크아웃/바닥 확인 로직이다. 구현 전 백테스트로 수익률 보존, MDD 개선, 연간 행동 횟수를 먼저 검증한다.

---

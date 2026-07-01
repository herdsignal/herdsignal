# HerdSignal — 프로젝트 공통 지침

최종 업데이트: 2026-07-02

## 서비스 개요
미국주식 장기투자자를 위한 데이터 기반 타이밍 도구.
개별 주식마다 HERD Index(0~100)를 산출해 고점 익절 / 저점 추가매수 타이밍을 제안.

## 문서 역할
- README: 사용자/포트폴리오 문서. 프로젝트 소개, 실행 방법, 외부 공개용 설명을 담당.
- CLAUDE.md: AI 개발 문서. 실제 코드 기준 개발 상태, 작업 원칙, 구현 범위를 담당.

## 핵심 개념
- **HERD Index**: 개별주 군중심리 지표 (0~100)
- **5단계**: Flee(0~20) → Scatter(20~40) → Calm(40~60) → Drift(60~80) → Rush(80~100)
- **버핏 철학**: Rush일 때 익절, Flee일 때 매수

## 모노레포 구조
```
herdsignal/
├── data/       Python 데이터 엔진
├── backend/    Spring Boot REST API
└── frontend/   React 대시보드
```
- `data/`: yfinance 수집, HERD 계산, MariaDB 저장, 스케줄러.
- `backend/`: MariaDB 데이터를 읽어 React에 제공하는 REST API.
- `frontend/`: Spring Boot API를 호출해 포트폴리오/종목/HERD 데이터를 시각화.

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

## 현재 개발 단계
- [x] 기획 완료
- [x] GitHub 세팅 완료
- [x] data/ HERD Index 계산·DB 저장·스케줄러 구현
- [x] backend/ Spring Boot REST API 구현
- [x] frontend/ React 대시보드 구현
- [ ] 지표/API 정합성 보완 및 문서 최신화 ← 현재

---

## HERD Index 현재 버전 (운영 계산 기준)

### 알고리즘
- 정규화 방식: 백분위수 (scipy.stats.percentileofscore)
- 데이터 기간: 기본 5년 (`YFINANCE_PERIOD=5y`)
- 운영 계산: 6개 지표를 계산해 가중합산
- 구성 지표:
  - 월봉 RSI 24%
  - 주봉 RSI 19%
  - 52주 위치 19%
  - MA200 이격도 18%
  - 거래량 강도 0% (계산 코드는 유지, 운영 가중치 비활성)
  - 200주 MA 위치 20%
- 주의: `herd_indicators` DB 테이블과 `HerdScoreResponse` API 응답은 아직 200주 MA 컬럼을 포함하지 않음. 따라서 화면의 지표 분해는 5개 저장 지표 중심으로 표시됨.

### 임계값
- Rush  ≥ 75  → 30% 익절
- Drift 60~75 → 5% 익절
- Calm  40~60 → 보유 유지
- Scatter 15~40 → 10% 추가매수 (1단계 신호)
- Flee  ≤ 15  → 30% 추가매수 (2단계 신호)

### 신호 규칙
- 신호 중복 제거: 20일 이내 재발생 무시
- `saver.py` 기준 신호 파생:
  - score >= 75: SELL
  - score >= 60: REDUCE
  - score <= 15: BUY
  - score <= 40: ADD
  - 그 외: HOLD
- `backtest_v3.py`의 실적 서프라이즈 필터·트레일링 스탑은 백테스트 전략이며, 현재 운영 계산 경로에는 연결되어 있지 않음.

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
- [x] 7개 테이블 생성 (`init_db.py`)
  - stocks
  - herd_scores
  - herd_indicators
  - daily_prices
  - user_portfolio
  - user_watchlist
  - portfolio_history
- [x] Tier 1 일일 스케줄러 (`scheduler/herd_scheduler.py`)
  - user_portfolio + user_watchlist + SPY 대상
  - 매일 16:30 ET 실행
- [x] Tier 2 on-demand HERD 계산
  - 상세/검색 조회 시 DB에 최신 데이터가 없으면 Python 즉시 계산
  - `CACHE_DAYS=7`
  - `user_id='cache'`로 캐시 티커 저장
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
  - GET `/api/portfolio/history?period=month|year`
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
  - S&P 500 HERD 배너
  - 포트폴리오 평가금액 요약
  - KRW/USD 통화 토글
  - 보유 종목 카드
  - 편집 모드/삭제
  - 평단가·수량 수정 모달
  - localStorage 캐시 우선 로딩
  - 수동 새로고침
- [x] StockDetail (`/stock/:ticker`)
  - HERD 점수/단계/Timing Signal
  - 지표 분해 UI
  - 포트폴리오 추가
  - 관심종목 추가
- [x] Search (`/search`)
  - 300ms 디바운스 검색
  - HERD 미리보기
  - 인기 종목 그리드
  - 최근 검색 localStorage 저장
  - 포트폴리오/관심종목 추가
- [x] Watchlist (`/watchlist`)
  - 관심 종목 HERD 카드
  - 관심 종목 삭제
  - S&P 500 HERD 배너
- [x] History (`/history`)
  - 월/년 기간 토글
  - recharts 기반 총 평가금액 차트
  - portfolio_history 시계열 표시

### frontend localStorage
- `hs_portfolio_realtime`: 포트폴리오 실시간 평가 캐시
- `hs_portfolio_herd`: 포트폴리오 HERD 캐시
- `hs_spy_herd`: SPY HERD 캐시
- `hs_cache_time`: 캐시 저장 시각
- `hs_recent_searches`: 최근 검색
- `herdsignal_currency`: 통화 표시 모드

---

## 미구현 또는 부분 구현

- StockDetail의 재무 정보, 뉴스, 애널리스트 목표가, 내부자 거래는 UI 자리만 있고 실제 데이터 연동은 없음.
- Finnhub collector와 `FINNHUB_API_KEY` 설정은 존재하지만 운영 화면/API에 연결되어 있지 않음.
- 200주 MA는 운영 점수 계산에 포함되지만 DB/API 지표 분해 응답에는 아직 없음.
- `backtest_v3.py`의 실적 서프라이즈 필터·트레일링 스탑은 백테스트 코드이며 운영 계산에는 미연동.
- 로그인/멀티유저 UI는 없음. MVP는 `AppConstants.DEFAULT_USER_ID` 기반 `local` 사용자 고정.
- SPY 배너의 SPY 종가, 1개월 수익률 표시는 아직 `—` placeholder.

---

## README와 현재 코드의 차이

- README는 HERD 알고리즘을 5개 지표 동일 가중치로 설명하지만, 현재 운영 계산은 6개 지표 가중합산이며 거래량 가중치는 0%다.
- README는 데이터 기간을 10년으로 설명하지만, 현재 기본 설정은 `YFINANCE_PERIOD=5y`다.
- README의 Phase 1 완료 목록은 대체로 맞지만 History, localStorage 캐시, 평단가·수량 수정, 실시간 포트폴리오 평가 API를 충분히 설명하지 않는다.
- README의 Stock Detail 애널리스트 목표가는 Phase 2로 적혀 있으며, 실제 코드도 아직 placeholder 상태다.
- README의 v1 한계/로드맵 표현은 현재 코드의 v3 가중치·백테스트 파일명과 충돌한다. 실제 코드 기준으로 문서를 우선 갱신할 것.

---

## 현재 한계 (인지하고 개발할 것)

- 운영 HERD 계산은 여전히 기술적 지표 중심이다.
- 거시경제 지표(VIX, DXY, 10년물 국채 수익률)는 운영 계산에 반영되어 있지 않다.
- 옵션 Put/Call, 공매도 비율, 종목 간 상관관계는 운영 계산에 반영되어 있지 않다.
- DB/API 지표 분해 스키마가 운영 계산 지표(200주 MA)를 완전히 반영하지 못한다.
- Python과 Spring Boot는 DB 중심으로 통신하지만, on-demand 계산과 실시간 포트폴리오 평가에서는 Spring Boot가 ProcessBuilder로 Python을 실행한다.

---

## 개발 현황

### 완료
- [x] data/ HERD Index 계산 및 백테스트 코드
- [x] data/ DB 저장 로직
- [x] data/ 일일 스케줄러
- [x] backend/ Spring Boot REST API
- [x] frontend/ Dashboard
- [x] frontend/ StockDetail
- [x] frontend/ Search
- [x] frontend/ Watchlist
- [x] frontend/ History
- [x] frontend/ localStorage 캐시

### 진행 중
- [ ] CLAUDE.md / README 최신화
- [ ] 200주 MA 지표의 DB/API 응답 반영 여부 결정
- [ ] placeholder 데이터 영역 실제 연동 여부 결정

# frontend/ — React 대시보드

최종 업데이트: 2026-07-05

## 이 폴더의 역할
Spring Boot API를 호출해서 HERD Index 데이터를 시각화.
프론트엔드 개발 전용 문서이며, data/backend 구현 판단은 루트 CLAUDE.md를 우선한다.
데이터 엔진 계산은 하지 않지만, 화면 표시를 위한 localStorage 캐시·통화 변환·요약값 갱신은 프론트에서 처리한다.

## 폴더 구조
```
src/
├── components/     재사용 컴포넌트
│   ├── HerdDots/   Herd Flow 점 애니메이션
│   ├── HerdHistoryChart/ HERD Index 히스토리 차트
│   ├── SpectrumBar/ Flee~Rush 스펙트럼 바
│   ├── StockAvatar/ 회사 로고 + 티커 fallback 아바타
│   ├── Layout/     사이드바 + Outlet 레이아웃
│   ├── AvgPriceModal/ 평균 매수가·수량 수정 모달
│   └── SignalJournalModal/ HERD 판단 기록 입력 모달
├── pages/          화면 단위
│   ├── Dashboard/  포트폴리오 대시보드
│   ├── StockDetail/ 종목 상세
│   ├── Search/     종목 검색 & 추가
│   ├── Watchlist/  관심 종목
│   ├── HerdLab/    HERD 검증과 방법론
│   ├── Journal/    전체 HERD 판단 기록
│   ├── AiRebalance/ 리밸런싱 플랜
│   ├── HerdFlowPreview/ Herd Flow 확인용
│   └── History/    자산 기록
├── styles/         전역 CSS 변수
├── assets/brand/   HerdSignal 로고/심볼 SVG 자산
├── utils/          통화/환율 유틸
│   ├── currency.js 통화 변환
│   ├── decision.js HERD 점수 + 보유/포트폴리오 컨텍스트 기반 행동 문장
│   └── portfolioTools.js 목표비중·리밸런싱·매수 대기열 계산
└── api/            Spring Boot API 호출
    └── herdApi.js
```

## 디자인 원칙
- Simply Wall St처럼 이해하기 쉬운 종목 분석 + Koyfin/TIKR처럼 차분한 금융 SaaS 톤을 지향한다.
- 순수 블랙보다 차콜/블루블랙 기반 배경을 사용하고, HERD 단계색만 강한 신호색으로 쓴다.
- 장식성 파랑/글로우는 최소화하고, 강한 색은 HERD 단계·액션·상승/하락 의미가 있을 때만 사용한다.
- 카드 radius, border, padding, 배지, 숫자 크기를 페이지별로 흩어지지 않게 통일한다.
- 현재 UI 문구는 한국어 중심
- 숫자 + 짧은 판단 문장을 함께 보여준다. 긴 설명문보다 행동 판단이 먼저 보여야 한다.

## HERD 5단계 색상
```
Flee    #3B82F6  (파랑)
Scatter #60A5FA  (연파랑)
Calm    #A3AAB8  (회색)
Drift   #FB923C  (오렌지)
Rush    #EF4444  (레드)
```

## 핵심 UI 컴포넌트
- HerdDots: Herd Flow 점 애니메이션 (Flee=전 영역 듬성듬성 분산, Scatter=작은 군집들이 깨져 흩어짐, Calm=중앙 균형, Drift=오른쪽 쏠림, Rush=좁은 군중 밀집)
- HerdHistoryChart: HERD 점수 히스토리 공용 차트 (Flee~Rush 구간 배경, 현재 점수 기준선, 현재 위치/평균 대비/기간 평균/저점-고점 데이터 보드, 이력 부족 배지)
- SpectrumBar: Flee~Rush 스펙트럼 바
- StockAvatar: `logoUrl`이 있으면 회사 로고를 표시하고, 없거나 이미지 로딩 실패 시 티커 배지를 표시한다.
- Layout: 공통 사이드바 + 페이지 Outlet
- Brand assets: Particle H 심볼은 왼쪽 Flee 분산, 오른쪽 Rush 밀집을 단순화한 SVG로 관리한다.
- AvgPriceModal: 평균 매수가·수량 수정 모달

## 현재 구현된 페이지
- 사이드바 노출 메뉴는 MVP 기준으로 Dashboard, Watchlist, Search, HerdLab만 유지한다.
- AiRebalance(`/ai`), History(`/history`), Journal(`/journal`), HerdFlowPreview(`/herd-flow`) 라우트는 유지하지만 사이드바에는 노출하지 않는다.
- Dashboard (`/`)
  - Signal Command Center 구조: 시장 HERD 신호 → 3개 핵심 Action Queue → 포트폴리오 요약 바 → 보유 종목 테이블 순으로 표시
  - S&P 500 HERD 배너 (Overview=Herd Flow 시그니처 애니메이션 + 1일/1달/1년 평균, Timeline=1M/3M/1Y/3Y HERD Index 히스토리 차트)
  - 포트폴리오 요약 바 (총자산 + 주식 평가액 + 현금 보유액 + 오늘 등락)
  - 총자산 히스토리 버튼 클릭 시 1개월/1년/전체 자산 히스토리 차트 표시. backend 히스토리 포인트에 현재 summary/cash 포인트를 합성해 현금 저장 직후에도 마지막 값이 즉시 반영된다.
  - 자산 히스토리는 사용자가 기준일을 직접 관리하지 않고, 선택 기간의 시작값/현재값/총자산 변화(입출금 포함)/고점 대비/현금·주식 평가액을 표시한다.
  - 현금 보유액 표시 및 편집 모드 입력/저장
  - HERD 판단 기록 전체 요약: `/api/journal` 기반 매수/익절 횟수·금액·평균 익절률·최근 기록 표시
  - KRW/USD 통화 토글
  - 목표 비중 기반 핵심 리밸런싱 체크
  - 보유 종목 테이블
  - 보유 종목 행에 회사 로고/티커/HERD 단계색/보유 수량/평단/목표 비중 차이 표시
  - 보유 종목 정렬(행동순/HERD 낮은순/HERD 높은순/비중순)
  - 편집 모드/삭제
  - 편집 모드에서 현금 보유액과 종목별 목표 비중을 수정한다. 목표 비중은 `hs_target_weights`에 저장한다.
  - 평단가·수량 수정 모달
  - localStorage 캐시 우선 로딩
  - 수동 새로고침은 `/api/portfolio/realtime`으로 yfinance 현재가를 다시 조회하고, HERD/SPY는 DB 최신값을 조회한다.
  - 수동 새로고침 완료 후 `현재가 갱신`/`HERD 조회`/`SPY 갱신` 결과를 짧게 표시
  - 보유 종목 행은 `ADD 10%`/`HOLD`/`SELL 30%` 같은 액션 코드를 우선 표시하고, 매수는 목표 투자금 기준·익절은 보유 평가금액 기준으로 비율 의미를 명시한다.
  - 보유 종목 액션은 HERD 신호와 현재 비중/목표 비중 차이를 함께 본다. 예: ADD 신호여도 목표비중을 초과하면 `WAIT`, SELL/REDUCE 신호와 목표비중 초과가 겹치면 비중 축소 우선으로 표시한다.
- StockDetail (`/stock/:ticker`)
  - HERD v4 점수/단계/Timing Signal
  - Action Layer 행동 점수/행동 비율/세부 국면 표시
  - 현재 HERD 판단을 움직인 핵심 근거 데이터 보드
  - HERD 판단 기록: 매수/보류/익절 판단 시 가격·수량·총액·수익률·메모를 DB `signal_journal`에 저장하고, 매수/익절 횟수·금액·평균 익절률을 요약 표시
  - 최근 3년 HERD 신호 신뢰도 데이터 보드
  - 1M/3M/1Y/3Y HERD Index 히스토리 차트
  - Fundamental Guard: 시가총액/PER/EPS/영업이익률/매출 기반 재무 경고 필터
  - 지표 분해 UI + EPS/섹터 강도 보정 승수 표시
  - 낮은 HERD 데이터 품질만 배지 표시
  - 포트폴리오 추가
  - 관심종목 추가
- Search (`/search`)
  - Stock Finder 패널에서 보유/대기 종목 수와 Ready/Pending/Limited 상태 기준을 먼저 보여준다.
  - 300ms 디바운스 검색
  - Finnhub 심볼 검색 API 기반 회사명/티커 검색
  - 대표 종목 티커/종목명 로컬 매칭 fallback
  - HERD 미리보기
  - 검색 결과 HERD 준비 상태 표시 (`HERD 준비됨` / `계산 필요` / `데이터 부족`)
  - `계산 필요` 상태는 포트폴리오/관심종목 추가 버튼을 비활성화한다.
  - 최근 검색 localStorage 저장
  - 포트폴리오/관심종목 중복 상태 표시
  - 포트폴리오 추가 후 평단가·수량 입력 모달 연결
  - 관심종목 추가
- Watchlist (`/watchlist`)
  - Buy Queue/Observe/Overheat 요약 보드로 관심종목 상태를 먼저 구분한다.
  - 관심 종목은 카드 그리드가 아니라 Action Queue 한 줄 리스트로 표시한다.
  - 낮은 HERD 데이터 품질만 배지 표시
  - 관심 종목 행은 `티커/HERD/액션/신호 지속/업데이트`를 스캔 가능한 컬럼으로 표시한다.
  - 매수 대기열 (Flee/Scatter + BUY/ADD 신호 우선, 최대 5개)
  - 매수 후보 우선 자동 정렬
  - 빠른 새로고침
  - 관심 종목 삭제
  - S&P 500 HERD 배너 (Dashboard와 같은 1일/1달/1년 평균 표시)
- HerdLab (`/herd-lab`)
  - 현재 HERD 모델 버전(`HERD_v5`) 검증 히어로 보드
  - Buy & Hold 대비 수익률 보존/MDD 개선/행동 횟수 표시
  - 목표 대비 PASS/WATCH 판정과 종목별 백테스트 verdict 표시
  - HERD 5단계 행동 매트릭스와 v4 가중치 표시
  - 설명문은 최소화하고 모델 버전·검증 기간·핵심 성과 수치 중심으로 표시
  - 표시 데이터는 `src/data/herdModelReport.js`에서 관리하며 JSX에 백테스트 숫자를 직접 하드코딩하지 않는다.
- Journal (`/journal`)
  - `/api/journal` 전체 기록을 종목/액션/가격/수량/총액/수익률/HERD/날짜 테이블로 표시
  - 전체/매수/익절/보류 필터와 매수·익절 금액, 평균 익절률 요약 표시
  - Dashboard 판단 기록 요약에서 진입하며, 사이드바에는 노출하지 않는다.
- AiRebalance (`/ai`)
  - 목표 비중·현금 목표·리밸런싱 예산 설정
  - 보수적/표준/공격적 리밸런싱 강도 선택
  - 현재 비중 vs 목표 비중 비교
  - 규칙 기반 매수/매도/보류 실행안
  - AI 연결 전 규칙 기반 플랜 요약
- HerdFlowPreview (`/herd-flow`)
  - 실제 데이터와 무관한 HerdDots 5단계 애니메이션 확인용 페이지
  - 사이드바에는 노출하지 않는다
- History (`/history`)
  - 월/년 기간 토글
  - recharts 기반 총 평가금액 차트
  - portfolio_history 시계열 표시

## 부분 구현 / 미구현
- StockDetail 최근 뉴스, 애널리스트 컨센서스, 내부자 거래 섹션은 제거됨. 상세 화면은 HERD와 Action Layer 중심 단일 컬럼으로 유지한다.
- StockDetail 재무정보는 원본 재무제표 표가 아니라 Fundamental Guard로 표시한다. `확인된 주요 경고 없음`/`재무 확인 필요`/`재무 리스크 큼` 문구를 사용하며, 안전 보증처럼 표현하지 않는다.
- 목표 비중은 Dashboard 편집 모드와 AiRebalance에서 수정하며 `hs_target_weights` localStorage에 저장한다. 아직 DB 저장 기능은 없다.
- 리밸런싱 플랜 설정은 `hs_rebalance_settings` localStorage에 저장하며, 아직 Claude API를 호출하지 않는다.
- Dashboard에서는 HERD 변화 요약과 portfolio_history 기반 간이 백테스트를 제거했다. 검증 데이터는 HerdLab/History에서 다룬다.
- StockDetail 지표 분해는 `ma200Weekly`를 표시하고, 가중치 0%인 거래량 강도는 표시하지 않는다.
- StockDetail HERD 카드 점수는 `herdV4`를 우선 사용하고, 구버전 응답이면 `herdScore`로 fallback한다.
- StockDetail 상단 회사명/섹터/로고는 `GET /api/stocks/{ticker}/herd` 응답의 `companyName`/`sector`/`logoUrl`을 사용한다.
- HERD 데이터 품질은 backend 응답의 `qualityScore`/`qualityLevel`/`qualityReasons`를 사용하되, frontend에서는 낮은 품질만 `데이터 제한/부족`으로 표시한다.
- HERD 신호 신뢰도는 `GET /api/stocks/{ticker}/herd/reliability` 응답을 사용한다. 데이터 완성도(`qualityScore`)가 아니라 과거 Flee/Rush 적중률, MDD 개선, 수익률 보존, 연간 행동 수를 보여준다.
- Action Layer는 backend 응답의 `actionScore`/`actionLabel`/`actionRatio`/`actionReasons`를 사용하며, frontend에서는 actionScore를 `강도`로 표시하고 별도 행동 점수 계산을 하지 않는다.
- Dashboard/Watchlist/StockDetail은 backend 응답의 `signalDurationDays`/`stageDurationDays`를 사용해 현재 HERD 신호가 며칠째 이어지는지 표시한다.
- Search에서 포트폴리오/관심종목 추가는 HERD 데이터가 준비된 종목만 허용한다. 포트폴리오 추가 성공 시 Dashboard localStorage 캐시(`hs_portfolio_realtime`, `hs_portfolio_herd`, `hs_cache_time`)를 비우고 평단가·수량 입력 모달을 연다.
- Dashboard 보유 종목의 `오늘` 등락률은 backend `dailyChangePct`를 그대로 표시한다. 하루 경계는 backend에서 KST 22:30 기준으로 계산한다.
- Decision Layer는 frontend 표시용 해석 레이어이며, 운영 HERD 점수나 DB 저장값을 변경하지 않는다.
- Dashboard/Watchlist의 SPY 배너에서 SPY 종가, 1개월 수익률은 아직 `—` placeholder.
- HERD 단계 표시 기준은 `src/utils/herdStage.js`에서 관리한다. backend Action Layer와 같은 Rush 75 / Flee 15 기준을 따른다.

## API 연동
모든 API 호출은 src/api/herdApi.js에서만 관리.
개발 환경은 Vite proxy(`/api` → `localhost:8080`)를 사용한다.
프로덕션 또는 명시 설정이 필요하면 루트 `.env`의 `VITE_API_BASE_URL` 환경변수를 사용한다.
로컬 실행은 루트에서 `./scripts/run-frontend.sh`를 우선 사용한다.

현재 herdApi.js에서 관리하는 호출:
- getPortfolio / getPortfolioHerd / refreshPortfolioHerd / getPortfolioRealtime / getPortfolioSummary / getPortfolioHistory
- getCashBalance / updateCashBalance
- addToPortfolio / removeFromPortfolio / updateAvgPrice
- getWatchlistHerd / addToWatchlist / removeFromWatchlist
- getStockHerd / refreshStockHerd / getStockHerdHistory / getSpyHerdHistory
- getStockFinancials
- getStockHerdReliability
- searchStocks

## localStorage 사용
- `hs_portfolio_realtime`: 포트폴리오 실시간 평가 캐시
- `hs_portfolio_herd`: 포트폴리오 HERD 캐시
- `hs_spy_herd`: SPY HERD 캐시
- `hs_cache_time`: 캐시 저장 시각
- `hs_recent_searches`: 최근 검색
- `hs_target_weights`: 포트폴리오 종목별 목표 비중
- `hs_dashboard_sort`: Dashboard 보유 종목 정렬 기준
- `hs_rebalance_settings`: 리밸런싱 예산·현금 목표·강도 설정
- `herdsignal_currency`: 통화 표시 모드

HERD 판단 기록은 localStorage가 아니라 backend `/api/journal`과 DB `signal_journal`을 기준으로 저장한다.

## AI 작업 원칙
- 실제 frontend 코드 기준으로 판단한다.
- 구현되지 않은 기능은 완료 처리하지 않는다.
- README보다 실제 코드를 우선한다.
- 추측하지 않는다.
- 작업 범위를 벗어난 파일은 수정하지 않는다.
- frontend/CLAUDE.md는 frontend 개발만을 위한 문서로 유지한다.

## 작업 시 주의
- data/, backend/ 폴더는 읽지 말 것
- API 호출 정의와 사용 방식은 src/api/herdApi.js 및 실제 페이지 구현을 기준으로 확인할 것
- 포트폴리오/관심종목 데이터는 Spring Boot API + DB 기준이며, localStorage는 캐시·최근 검색·통화 모드 저장 용도

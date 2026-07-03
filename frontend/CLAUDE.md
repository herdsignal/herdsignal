# frontend/ — React 대시보드

최종 업데이트: 2026-07-03

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
│   ├── Layout/     사이드바 + Outlet 레이아웃
│   └── AvgPriceModal/ 평균 매수가·수량 수정 모달
├── pages/          화면 단위
│   ├── Dashboard/  포트폴리오 대시보드
│   ├── StockDetail/ 종목 상세
│   ├── Search/     종목 검색 & 추가
│   ├── Watchlist/  관심 종목
│   ├── HerdLab/    HERD 검증과 방법론
│   ├── AiRebalance/ 리밸런싱 플랜
│   ├── HerdFlowPreview/ Herd Flow 확인용
│   └── History/    자산 기록
├── styles/         전역 CSS 변수
├── utils/          통화/환율 유틸
│   ├── currency.js 통화 변환
│   ├── decision.js HERD 점수 + 보유/재무 컨텍스트 기반 행동 문장
│   └── portfolioTools.js 목표비중·리밸런싱·기회 대기열 계산
└── api/            Spring Boot API 호출
    └── herdApi.js
```

## 디자인 원칙
- 클린 미니멀 (토스, 애플 느낌)
- 현재 UI 문구는 한국어 중심
- 숫자보다 감각으로 먼저 전달

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
- HerdHistoryChart: HERD 점수 히스토리 공용 차트 (Flee~Rush 구간 배경, 현재 점수 기준선, 이력 부족 배지)
- SpectrumBar: Flee~Rush 스펙트럼 바
- Layout: 공통 사이드바 + 페이지 Outlet
- AvgPriceModal: 평균 매수가·수량 수정 모달

## 현재 구현된 페이지
- 사이드바 노출 메뉴는 MVP 기준으로 Dashboard, Watchlist, Search, HerdLab만 유지한다.
- AiRebalance(`/ai`), History(`/history`), HerdFlowPreview(`/herd-flow`) 라우트는 유지하지만 사이드바에는 노출하지 않는다.
- Dashboard (`/`)
  - S&P 500 HERD 배너 (Overview=Herd Flow 시그니처 애니메이션, Timeline=HERD Index 히스토리 차트)
  - 포트폴리오 평가금액 요약
  - KRW/USD 통화 토글
  - 목표 비중 기반 핵심 리밸런싱 체크
  - 보유 종목 카드
  - 편집 모드/삭제
  - 평단가·수량 수정 모달
  - localStorage 캐시 우선 로딩
  - 수동 새로고침은 DB 조회 기반 빠른 갱신만 수행
  - 수동 새로고침 완료 후 `가격 갱신`/`HERD 조회`/`SPY 갱신` 결과를 짧게 표시
  - 보유 종목 카드는 `ADD 10%`/`HOLD`/`SELL 30%` 같은 액션 코드를 우선 표시하고 HERD 점수는 보조 메타로 표시
- StockDetail (`/stock/:ticker`)
  - HERD v4 점수/단계/Timing Signal
  - Action Layer 행동 점수/행동 비율/세부 국면 표시
  - HERD Index 히스토리 차트
  - 지표 분해 UI + EPS/섹터 강도 보정 승수 표시
  - 낮은 HERD 데이터 품질만 배지 표시
  - 재무 정보
  - 포트폴리오 추가
  - 관심종목 추가
- Search (`/search`)
  - 300ms 디바운스 검색
  - Finnhub 심볼 검색 API 기반 회사명/티커 검색
  - 대표 종목 티커/종목명 로컬 매칭 fallback
  - HERD 미리보기
  - 검색 결과 HERD 준비 상태 표시 (`HERD 준비됨` / `계산 필요` / `데이터 부족`)
  - 최근 검색 localStorage 저장
  - 포트폴리오/관심종목 중복 상태 표시
  - 포트폴리오 추가 후 평단가·수량 입력 모달 연결
  - 관심종목 추가
- Watchlist (`/watchlist`)
  - 관심 종목 HERD 카드
  - 낮은 HERD 데이터 품질만 배지 표시
  - 관심 종목 카드는 `강도 · 행동 비율 · 행동 라벨`로 Action Layer를 축약 표시
  - 기회 대기열 (Flee/Scatter + BUY/ADD 신호 우선)
  - 매수 후보 우선 자동 정렬
  - 빠른 새로고침
  - 관심 종목 삭제
  - S&P 500 HERD 배너
- HerdLab (`/herd-lab`)
  - 현재 HERD 모델 버전(`HERD_v5`) 검증 데이터 보드
  - Buy & Hold 대비 수익률 보존/MDD 개선/행동 횟수 표시
  - 목표 대비 PASS/WATCH 판정과 종목별 백테스트 verdict 표시
  - HERD 5단계 행동 매트릭스와 v4 가중치 표시
  - 표시 데이터는 `src/data/herdModelReport.js`에서 관리하며 JSX에 백테스트 숫자를 직접 하드코딩하지 않는다.
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
- 목표 비중은 `hs_target_weights` localStorage에 저장하며, 아직 DB 저장 기능은 없다.
- 리밸런싱 플랜 설정은 `hs_rebalance_settings` localStorage에 저장하며, 아직 Claude API를 호출하지 않는다.
- Dashboard에서는 HERD 변화 요약과 portfolio_history 기반 간이 백테스트를 제거했다. 검증 데이터는 HerdLab/History에서 다룬다.
- StockDetail 지표 분해는 `ma200Weekly`를 표시하고, 가중치 0%인 거래량 강도는 표시하지 않는다.
- StockDetail HERD 카드 점수는 `herdV4`를 우선 사용하고, 구버전 응답이면 `herdScore`로 fallback한다.
- HERD 데이터 품질은 backend 응답의 `qualityScore`/`qualityLevel`/`qualityReasons`를 사용하되, frontend에서는 낮은 품질만 `데이터 제한/부족`으로 표시한다.
- Action Layer는 backend 응답의 `actionScore`/`actionLabel`/`actionRatio`/`actionReasons`를 사용하며, frontend에서는 actionScore를 `강도`로 표시하고 별도 행동 점수 계산을 하지 않는다.
- Search에서 포트폴리오 추가 성공 시 Dashboard localStorage 캐시(`hs_portfolio_realtime`, `hs_portfolio_herd`, `hs_cache_time`)를 비우고 평단가·수량 입력 모달을 연다.
- Dashboard 보유 종목의 `오늘` 등락률은 backend `dailyChangePct`를 그대로 표시한다. 하루 경계는 backend에서 KST 22:30 기준으로 계산한다.
- Decision Layer는 frontend 표시용 해석 레이어이며, 운영 HERD 점수나 DB 저장값을 변경하지 않는다.
- Dashboard/Watchlist의 SPY 배너에서 SPY 종가, 1개월 수익률은 아직 `—` placeholder.

## API 연동
모든 API 호출은 src/api/herdApi.js에서만 관리.
개발 환경은 Vite proxy(`/api` → `localhost:8080`)를 사용한다.
프로덕션 또는 명시 설정이 필요하면 `VITE_API_BASE_URL` 환경변수를 사용한다.

현재 herdApi.js에서 관리하는 호출:
- getPortfolio / getPortfolioHerd / refreshPortfolioHerd / getPortfolioRealtime / getPortfolioSummary / getPortfolioHistory
- addToPortfolio / removeFromPortfolio / updateAvgPrice
- getWatchlistHerd / addToWatchlist / removeFromWatchlist
- getStockHerd / refreshStockHerd / getStockHerdHistory / getSpyHerdHistory
- searchStocks
- getStockFinancials

## localStorage 사용
- `hs_portfolio_realtime`: 포트폴리오 실시간 평가 캐시
- `hs_portfolio_herd`: 포트폴리오 HERD 캐시
- `hs_spy_herd`: SPY HERD 캐시
- `hs_cache_time`: 캐시 저장 시각
- `hs_recent_searches`: 최근 검색
- `hs_target_weights`: 포트폴리오 종목별 목표 비중
- `hs_rebalance_settings`: 리밸런싱 예산·현금 목표·강도 설정
- `herdsignal_currency`: 통화 표시 모드

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

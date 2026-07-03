# frontend/ — React 대시보드

최종 업데이트: 2026-07-02

## 이 폴더의 역할
Spring Boot API를 호출해서 HERD Index 데이터를 시각화.
프론트엔드 개발 전용 문서이며, data/backend 구현 판단은 루트 CLAUDE.md를 우선한다.
데이터 엔진 계산은 하지 않지만, 화면 표시를 위한 localStorage 캐시·통화 변환·요약값 갱신은 프론트에서 처리한다.

## 폴더 구조
```
src/
├── components/     재사용 컴포넌트
│   ├── HerdDots/   무리 점 애니메이션
│   ├── SpectrumBar/ Flee~Rush 스펙트럼 바
│   ├── Layout/     사이드바 + Outlet 레이아웃
│   └── AvgPriceModal/ 평균 매수가·수량 수정 모달
├── pages/          화면 단위
│   ├── Dashboard/  포트폴리오 대시보드
│   ├── StockDetail/ 종목 상세
│   ├── Search/     종목 검색 & 추가
│   ├── Watchlist/  관심 종목
│   └── History/    자산 기록
├── styles/         전역 CSS 변수
├── utils/          통화/환율 유틸
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
Scatter #93C5FD  (연파랑)
Calm    #9CA3AF  (회색)
Drift   #FB923C  (오렌지)
Rush    #EF4444  (레드)
```

## 핵심 UI 컴포넌트
- HerdDots: 무리 점 애니메이션 (Rush=오른쪽 뭉침, Flee=흩어짐)
- SpectrumBar: Flee~Rush 스펙트럼 바
- Layout: 공통 사이드바 + 페이지 Outlet
- AvgPriceModal: 평균 매수가·수량 수정 모달

## 현재 구현된 페이지
- Dashboard (`/`)
  - S&P 500 HERD 배너
  - 포트폴리오 평가금액 요약
  - KRW/USD 통화 토글
  - 보유 종목 카드
  - 편집 모드/삭제
  - 평단가·수량 수정 모달
  - localStorage 캐시 우선 로딩
  - 수동 새로고침은 DB 조회 기반 빠른 갱신만 수행
- StockDetail (`/stock/:ticker`)
  - HERD 점수/단계/Timing Signal
  - 지표 분해 UI
  - 포트폴리오 추가
  - 관심종목 추가
- Search (`/search`)
  - 300ms 디바운스 검색
  - 대표 종목 티커/종목명 로컬 매칭
  - HERD 미리보기
  - 인기 종목 그리드
  - 최근 검색 localStorage 저장
  - 포트폴리오/관심종목 중복 상태 표시
  - 포트폴리오/관심종목 추가
- Watchlist (`/watchlist`)
  - 관심 종목 HERD 카드
  - 매수/중립/익절 후보 요약
  - HERD 점수·최신일·티커 정렬
  - 빠른 새로고침
  - 관심 종목 삭제
  - S&P 500 HERD 배너
- History (`/history`)
  - 월/년 기간 토글
  - recharts 기반 총 평가금액 차트
  - portfolio_history 시계열 표시

## 부분 구현 / 미구현
- StockDetail의 재무 정보, 뉴스, 애널리스트 목표가, 내부자 거래는 placeholder UI만 있음.
- StockDetail 지표 분해는 `ma200Weekly`를 표시하고, 가중치 0%인 거래량 강도는 표시하지 않는다.
- Dashboard/Watchlist의 SPY 배너에서 SPY 종가, 1개월 수익률은 아직 `—` placeholder.

## API 연동
모든 API 호출은 src/api/herdApi.js에서만 관리.
개발 환경은 Vite proxy(`/api` → `localhost:8080`)를 사용한다.
프로덕션 또는 명시 설정이 필요하면 `VITE_API_BASE_URL` 환경변수를 사용한다.

현재 herdApi.js에서 관리하는 호출:
- getPortfolio / getPortfolioHerd / refreshPortfolioHerd / getPortfolioRealtime / getPortfolioSummary / getPortfolioHistory
- addToPortfolio / removeFromPortfolio / updateAvgPrice
- getWatchlistHerd / addToWatchlist / removeFromWatchlist
- getStockHerd / refreshStockHerd

## localStorage 사용
- `hs_portfolio_realtime`: 포트폴리오 실시간 평가 캐시
- `hs_portfolio_herd`: 포트폴리오 HERD 캐시
- `hs_spy_herd`: SPY HERD 캐시
- `hs_cache_time`: 캐시 저장 시각
- `hs_recent_searches`: 최근 검색
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

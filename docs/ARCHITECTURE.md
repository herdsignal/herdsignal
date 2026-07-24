# HerdSignal 코드 구조

이 문서는 파일 크기보다 **변경 이유와 장애 경계**를 기준으로 코드를 찾기 위한 안내서다.

## 백엔드

컨트롤러는 공개 API 계약만 담당하고 `PortfolioService`, `HerdService` 같은 유스케이스
서비스를 호출한다.

### 포트폴리오

- `PortfolioService`: 컨트롤러가 의존하는 파사드와 보유 종목 쓰기
- `PortfolioQueryService`: 현재 요약과 자산 히스토리 읽기 모델 조립
- `PortfolioHoldingValuationService`: 종목별 가격 조회와 평가 계산
- `PortfolioCashService`: 현금 현재값과 날짜별 원장
- `PortfolioRealtimeRunner`: Python 프로세스 실행과 JSON 변환
- `UsMarketSessionClock`: 미국장 기준 스냅샷 날짜

가격 계산, 현금 저장, 외부 프로세스 실행을 다시 `PortfolioService`에 넣지 않는다.

### HERD 조회

- `HerdService`: DB/on-demand 조회와 배치 오케스트레이션
- `HerdResponseAssembler`: 미리 조회한 데이터의 응답 DTO 조립
- `HerdQualityEvaluator`: 산출물 완성도·최신성 평가
- `HerdSignalDurationCalculator`: 신호·단계 연속 기간 계산
- `ActionDecisionService`: 레거시 v6.1 연구 행동 재현
- `UserActionBoundary`: 기본 사용자 응답·저널의 행동을 HOLD·0%로 잠그는
  단일 fail-closed 정책
- `OperationalActionPromotionPort`: 향후 통과 모델이 들어오는 유일한 포트
- `AuditedOperationalActionPromotionPort`: 모델·산출물 해시·holdout·사람
  승인을 대조하고 감사 저장 성공 후 최대 5% 부분 행동만 발급
- `model_promotion_audits`: 승격 요청의 승인·거절 사유와 승인 파일 해시

HERD 상태 계산, 산출물 품질, 개인 행동은 서로 다른 개념이다. 한 계산식으로 합치지 않는다.
연구용 `ActionDecision`을 사용자 응답에 직접 매핑하지 않는다.

## 프론트엔드

페이지는 배치와 사용자 흐름을, 커스텀 훅은 비동기 상태를, 모델 모듈은 순수 계산을 담당한다.

### Dashboard

- `dashboardCache`: 저장소 키, 만료, API 응답 정규화
- `dashboardActions`: 행동 표시와 정렬 규칙
- `dashboardPresentation`: 숫자·날짜·차트 표시 모델
- `dashboardModel`: 이전 import 경로를 보존하는 공개 배럴
- `useDashboardMarketData`: SPY와 시장 데이터
- `useDashboardAssetHistory`: 자산 히스토리 요청과 차트 파생값
- `useDashboardSupportingData`: 데이터 상태와 판단 기록
- `useDashboardData`: 위 기능을 조합하는 페이지 유스케이스
- `DashboardHeader`: 페이지 상태와 갱신 명령
- `DashboardCommandCenter`: SPY 시장 무대와 포트폴리오 요약
- `DashboardPortfolioEditor`: 현금 입력 경계
- `Dashboard.module.css`: 페이지 프레임과 여러 자식이 공유하는 스타일
- `Dashboard{Component}.module.css`: 해당 자식 컴포넌트만 사용하는 스타일

자식 컴포넌트는 공통 모듈과 자기 모듈을 합쳐 기존 CSS Module 계약을 유지한다. 여러
컴포넌트가 함께 쓰거나 결합 선택자로 연결된 규칙은 공통 모듈에 남긴다.

### StockDetail·Watchlist

- `StockDetailHero`: HERD 상태와 연구 Action Layer
- `StockDetailAnalysis`: 신호 근거·지표·신뢰도 상세
- `StockDetailHistory`: 기간별 HERD 차트
- `StockDetailRecords`: 재무 가드와 판단 기록 조합
- `WatchlistMarketBanner`: SPY 시장 상태와 타임라인
- `WatchlistQueue`: 요약, 우선 관찰, 전체 관찰 종목 목록
- `Watchlist`: 조회·삭제 상태와 페이지 조합

### Search

- `searchModel`: 후보, 검색 매칭, 최근 검색, 편입 표시 규칙
- `SearchResultContent`: 검색 결과 상태별 표시
- `Search`: 검색 요청과 사용자 상호작용

단계 색상, 기간 목록, API 호스트, 행동 강도는 `src/utils`의 공통 모듈을 사용한다.

### 화면 회귀 검증

Playwright가 대시보드, 종목 상세, 대기열을 데스크톱·모바일에서 캡처한다. 인증, API,
환율, 날짜, 난수와 애니메이션 프레임은 테스트에서 고정한다.

```bash
cd frontend
npm run test:visual
```

의도적으로 화면을 변경한 경우에만 `npm run test:visual:update`로 기준 이미지를 갱신하고,
일반 리팩터링에서는 기존 이미지와 일치해야 한다.

## Python

`data/scheduler`는 운영 경로이고 `data/herd`는 연구 경로다.

- `scheduler/herd_scheduler.py`: 기존 외부 import를 보존하는 운영 파사드와 Tier 1 잡
- `scheduler/on_demand.py`: 요청 기반 HERD 캐시·계산
- `scheduler/daemon.py`: APScheduler 데몬 구성
- `scheduler/realtime_portfolio.py`: 실시간 포트폴리오 조회·평가·스냅샷 저장
- `herd/*_vN.py`와 고정 계약/리포트: 연구 재현 산출물

연구 파일은 길다는 이유만으로 수정하지 않는다. 계약 해시나 결과 재현 경로에 연결된 파일은
새 버전을 추가하고 기존 버전을 보존한다. 운영 코드와 현재 진행 중인 재사용 모듈만 일반
리팩터링 대상으로 삼는다.

## 변경 원칙

1. 한 변경은 한 목적만 가진다. 기능 변경과 대규모 이동을 같은 변경에 섞지 않는다.
2. 공개 API와 기존 import 경로는 파사드나 배럴로 먼저 보존한다.
3. 순수 계산을 먼저 추출하고 계약 테스트를 추가한 뒤 I/O 오케스트레이션을 줄인다.
4. 줄 수만 줄이는 래퍼, 한 번만 쓰는 추상화, 이름만 다른 중복 계층은 만들지 않는다.
5. 백엔드 전체 테스트, 프론트 테스트·lint·build, 관련 Python 테스트가 모두 통과해야 한다.

현재 남은 큰 경계는 `useDashboardData`, `useStockDetail`의 비동기 상태 조합과
`HerdScoreResponse` DTO의 과도한 필드 수다. 화면 회귀 기준과 API 호환 테스트를
유지하면서 작은 변경 단위로 처리한다.

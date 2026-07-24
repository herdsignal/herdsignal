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
- `ActionDecisionService`: 개인 행동 번역 오케스트레이션

HERD 상태 계산, 산출물 품질, 개인 행동은 서로 다른 개념이다. 한 계산식으로 합치지 않는다.

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

### Search

- `searchModel`: 후보, 검색 매칭, 최근 검색, 편입 표시 규칙
- `SearchResultContent`: 검색 결과 상태별 표시
- `Search`: 검색 요청과 사용자 상호작용

단계 색상, 기간 목록, API 호스트, 행동 강도는 `src/utils`의 공통 모듈을 사용한다.

## Python

`data/scheduler`는 운영 경로이고 `data/herd`는 연구 경로다.

- `scheduler/herd_scheduler.py`: Tier 1/2/3 작업 오케스트레이션
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

현재 남은 큰 경계는 Dashboard/StockDetail의 컴포넌트별 CSS, Watchlist의 시장 배너와 목록
상태, `HerdScoreResponse` DTO의 과도한 필드 수다. 이들은 UI 개편 또는 API 버전 변경과 함께
작은 변경 단위로 처리한다.

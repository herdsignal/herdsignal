# HerdSignal 코드 구조

상태: `CURRENT`

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

### 장기 운용 검토

- `ObjectiveEvidenceService`: State S1을 근거 패킷으로 변환하고 미연결 영역을 `NO_VIEW`로 유지
- `EvidenceGate`: 필수 사실의 출처·시점·최신성·PIT 계약 검사
- `LongTermOperatingReviewService`: 사용자 운용 조건과 실제 포트폴리오 비중 연결
- `DecisionSynthesisPolicy`: 데이터·위험·기업 훼손 우선순위의 결정론적 종합
- `OperatingReviewSnapshotService`: 명시적 판단 JSON·해시·기준 가격 append-only 기록

객관 조회 `GET /api/operating-reviews/{ticker}/objective`만 공개한다. 개인
검토와 기록 원장은 인증이 필요하며 GET 요청은 스냅샷을 자동 생성하지 않는다.
- `ActionDecisionService`: 레거시 v6.1 연구 행동 재현. 운영 HERD 조회에서는
  실행하지 않으며 회귀 테스트와 명시적 연구 경로에서만 사용
- `UserActionBoundary`: 기본 사용자 응답·저널의 행동을 HOLD·0%로 잠그는
  단일 fail-closed 정책
- `OperationalActionPromotionPort`: 향후 통과 모델이 들어오는 유일한 포트
- `AuditedOperationalActionPromotionPort`: 모델·산출물 해시·holdout·사람
  승인을 대조하고 감사 저장 성공 후 최대 5% 부분 행동만 발급
- `model_promotion_audits`: 승격 요청의 승인·거절 사유와 승인 파일 해시

HERD 상태 계산, 산출물 품질, 개인 행동은 서로 다른 개념이다. 한 계산식으로 합치지 않는다.
연구용 `ActionDecision`을 사용자 응답에 직접 매핑하지 않는다.

차세대 의사결정 연구는 `HERD State → Action Edge → Portfolio Policy`의
단방향 계층을 따른다. Action Edge가 채택되지 않으면 Portfolio Policy는
비율을 계산하지 않는다. 상세 계약은 `HERD_DECISION_ARCHITECTURE.md`다.

## 프론트엔드

페이지는 배치와 사용자 흐름을, 커스텀 훅은 비동기 상태를, 모델 모듈은 순수 계산을 담당한다.

### Dashboard

- `Dashboard`: SPY 관찰·종목 검색·선택형 자산 패널·보유 종목을 조립
- `HerdObservationPanel`: SPY 또는 선택 종목의 HERD 상태를 같은 시각 문법으로 표시
- `TickerSearch`: 자동완성·최근 검색·키보드 제출을 담당
- `useMarketHomeData`: SPY 관찰값과 이력 요청
- `MarketField`: SPY 집계 전용 시각화
- `usePortfolioData`: 사용자별 포트폴리오·State S1 캐시와 갱신
- `usePortfolioAssetHistory`: 자산 이력 요청과 차트 파생값
- `usePortfolioMutations`: 현금·평단·수량·삭제 변경
- `portfolioDataModel`: API 응답 정규화와 캐시 정책
- `portfolioModel`: 보유 종목·오늘 등락·차트 순수 계산

시장 상태는 대시보드의 기본 관찰값으로 유지하고 개인 자산은 사용자가 열었을 때만
표시한다. 계정 메뉴에서도 별도 행동 알림을 계산하지 않는다.

### StockDetail·Watchlist

- `StockDetailHero`: 개별 종목 State/Transition S1
- `StockDetailAnalysis`: 네 증거군과 하방 위험 맥락
- `StockDetailHistory`: 기간별 State S1 차트
- `StockDetailRecords`: 기업 상태와 사용자 판단 기록
- `StockOperatingReview`: 장기 운용 영역, 제한, veto와 명시적 원장 기록
- `useOperatingReview`: 공개 객관 근거와 인증 개인 검토의 실패 경계 분리
- `WatchlistQueue`: 낮은 HERD부터 높은 HERD까지 관찰 목록
- `Watchlist`: 조회·삭제 상태와 페이지 조합

### 대시보드 검색

- `searchModel`: 후보, 검색 매칭, 최근 검색, 편입 표시 규칙
- `useStockSearch`: 검색 요청과 최근 검색 상태
- `useTickerMembership`: 포트폴리오·관찰 목록 편입 상태

단계 색상, 기간 목록, API 호스트, 관찰값 정규화는 `src/utils`의 공통 모듈을 사용한다.

### 화면 회귀 검증

Playwright가 공개 홈·로그인과 보호된 9개 화면 전체를 1920px 와이드,
1440px 데스크톱, 412px 모바일에서 캡처한다. 인증, API, 환율, 날짜와
애니메이션 프레임은 테스트에서 고정한다.

```bash
cd frontend
npm run test:visual
npm run test:bundle
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

현재 남은 큰 경계는 레거시 호환 `HerdScoreResponse` DTO의 과도한 필드 수와
운영 PIT 기업·기대 데이터의 부재다. 화면 회귀 기준과 API 호환 테스트를
유지하면서 작은 변경 단위로 처리한다.

# backend 개발 지침

최종 업데이트: 2026-07-27

## 역할

Spring Boot backend는 MariaDB의 시장·HERD 데이터와 사용자 데이터를 API로
제공한다. 공식 계산은 Python이 담당하며 backend는 조회, 사용자 격리,
인증, 운영 안전장치와 제한된 Python 실행만 담당한다.

## 구조

```text
controller/   HTTP 계약과 입력 검증
service/      조회·조합·정책·외부 프로세스 경계
repository/   JPA 데이터 접근
domain/       영속 엔티티
dto/          API 요청·응답
config/       OAuth2·세션·운영 작업 설정
exception/    일관된 API 오류
```

주요 서비스 경계:

- `HerdObservationService`: State S1 현재값·이력
- `HerdService`: 레거시 HERD 호환 응답과 연구 정보
- `HerdOnDemandRunner`, `PythonProcessGateway`: 제한된 Python 실행
- `PortfolioQueryService`, `PortfolioCashService`,
  `PortfolioHoldingValuationService`: 포트폴리오 조회·평가
- `PortfolioRealtimeRunner`: 실시간 평가 프로세스 경계
- `PortfolioLedgerService`, `PortfolioPerformanceService`: 원장·성과
- `ObservationChangeService`: 상태 변화와 사용자 확인
- `UserActionBoundary`: 운영 행동의 fail-closed 경계
- `OperationalPromotionGate`, `AuditedOperationalActionPromotionPort`:
  연구 후보 승격 검증과 감사
- `CurrentUserService`: 인증 사용자 경계

## 운영 모델 경계

- 기본 사용자 상태는 State S1이다.
- v4·v6.1 응답은 호환·연구 재현용이다.
- `ActionDecisionService`는 레거시 연구 계산기이며 운영 권한을 발급하지 않는다.
- 승인된 증거·완결 사이클·PIT·holdout 조건이 없으면 행동은 `HOLD·0%`다.
- 누락된 승인 값이나 감사 저장 실패는 반드시 차단한다.

## API 기준

공개 API 목록은 `README.md`를 단일 사용자 문서로 유지한다. Controller를
변경하면 README API 표와 frontend 호출부를 함께 확인한다. 핵심 영역은
다음과 같다.

- `/api/observations`, `/api/observation-changes`
- `/api/stocks/{ticker}/herd`, history, refresh, reliability
- `/api/stocks/search`, financials
- `/api/portfolio`, summary, realtime, history, ledger, performance
- `/api/watchlist`, `/api/journal`
- `/api/model/validation`, `/api/system/data-status`
- `/api/investor-profile`, `/api/auth`

## 데이터와 인증

- Flyway와 현재 엔티티가 스키마의 변경 이력을 관리한다.
- `ddl-auto=validate`로 런타임 스키마 불일치를 드러낸다.
- Google OAuth2 로그인과 JDBC 영속 세션을 사용한다.
- 인증 비활성 로컬 개발에서만 `local` 사용자 폴백을 허용한다.
- 모든 포트폴리오·관찰·판단 기록 조회는 현재 사용자 범위로 제한한다.

## Python 실행

- 직접 `ProcessBuilder`를 흩뿌리지 않고 `PythonProcessGateway`와 전용 runner를 사용한다.
- 실행 경로·타임아웃·출력 파싱은 중앙 경계에서 관리한다.
- 실패 시 오래된 값을 최신값처럼 가장하지 않는다.
- 로컬 실행은 루트 `.env`를 읽는 `./scripts/run-backend.sh`를 사용한다.

## 코드 원칙

- Controller에 비즈니스 로직을 넣지 않는다.
- Repository에는 DB 접근만 둔다.
- Entity를 API 응답으로 직접 노출하지 않는다.
- 시간·미국장 세션 판단은 `UsMarketSessionClock`을 재사용한다.
- 티커 입력은 `TickerSymbolPolicy`를 통과시킨다.
- 예외 응답은 `GlobalExceptionHandler`와 `ApiResponse` 계약을 따른다.
- 모델 승격 경계를 우회하는 환경변수·임시 분기를 만들지 않는다.

## 검증

```bash
cd backend
./gradlew test
```

DB 마이그레이션이나 인증 변경은 단위 테스트 외에 실제 로컬 실행과
`/api/auth/me`, `/api/system/data-status` smoke test를 별도로 확인한다.

# backend/ — Spring Boot REST API

최종 업데이트: 2026-07-05

## 이 폴더의 역할
MariaDB에 저장된 HERD Index 데이터를 React에 서빙.
backend 개발 전용 문서이며, frontend/data 구현 판단은 루트 CLAUDE.md를 우선한다.
HERD 공식 계산은 Python이 담당한다. backend는 DB 조회/저장, API 응답, 예외 처리, 필요 시 Python 계산 트리거를 담당한다.

## 패키지 구조
```
src/main/java/com/herdsignal/
├── controller/     REST API 엔드포인트
├── service/        비즈니스 로직
├── repository/     DB 접근 (JPA)
├── domain/         엔티티 클래스
├── dto/            요청/응답 DTO
├── exception/      전역 예외 처리 및 커스텀 예외
└── config/         설정 (DB, CORS 등)
```

## 주요 API 엔드포인트
```
GET    /api/stocks/{ticker}/herd              종목 HERD Index + 지표 분해 조회
POST   /api/stocks/{ticker}/herd/refresh      종목 HERD Index 강제 재계산 후 조회
GET    /api/stocks/search?q=apple             회사명/티커 기반 종목 심볼 검색 (Finnhub)
GET    /api/stocks/{ticker}/financials        종목 재무정보 조회 (yfinance .info)
GET    /api/stocks/{ticker}/herd/history      종목 HERD 히스토리 조회 (period=1m|3m|1y|3y)
GET    /api/stocks/{ticker}/herd/reliability  종목 HERD 신호 신뢰도 조회 (years=3)
GET    /api/portfolio/herd                    포트폴리오 전체 HERD 조회
POST   /api/portfolio/herd/refresh            포트폴리오 전체 HERD 강제 재계산 후 조회

GET    /api/portfolio                         포트폴리오 목록 조회
POST   /api/portfolio                         포트폴리오 종목 추가
DELETE /api/portfolio/{ticker}                포트폴리오 종목 삭제
GET    /api/portfolio/summary                 포트폴리오 평가 요약 조회
GET    /api/portfolio/history?period=month|year|all 포트폴리오 히스토리 조회
GET    /api/portfolio/cash                    현재 현금 보유액 조회
PUT    /api/portfolio/cash                    현금 보유액 수정 + 오늘 스냅샷 저장
PATCH  /api/portfolio/{ticker}/avg-price      평균 매수가·수량 수정
GET    /api/portfolio/realtime                yfinance 실시간 포트폴리오 계산

GET    /api/journal                           전체 HERD 판단 기록 조회
GET    /api/journal?ticker=NVDA               특정 종목 HERD 판단 기록 조회
POST   /api/journal                           HERD 판단 기록 저장
DELETE /api/journal/{id}                      HERD 판단 기록 삭제

GET    /api/watchlist                         관심 종목 목록 조회
GET    /api/watchlist/herd                    관심 종목 전체 HERD 조회
POST   /api/watchlist                         관심 종목 추가
DELETE /api/watchlist/{ticker}                관심 종목 삭제

```

## 기술 스택
- Spring Boot 3.5.3
- Java 17
- Gradle
- Spring Data JPA
- MariaDB
- Lombok

## 현재 구현된 서비스
- HerdService
  - 최신 HERD 점수와 지표 분해값 조회
  - DB에 데이터가 없으면 Python on-demand 계산을 ProcessBuilder로 실행 후 재조회
  - 포트폴리오/관심종목 HERD 조회용 공통 로직 제공
  - HERD 데이터 품질과 Action Layer 응답 계산
  - stocks 메타데이터를 조회해 companyName / sector / logoUrl을 HERD 응답에 포함
- ActionDecisionService
  - HERD 점수 + 지표 분해값 + 데이터 품질 기반 장기투자 행동 강도 계산
  - DB 저장 없이 API 응답 시점에 actionScore/actionLabel/actionRatio/actionRegime을 산출
- PortfolioService
  - 포트폴리오 CRUD
  - 현금 보유액 조회/수정
  - 평가 요약 조회 (주식 평가액 + 현금 보유액 + 총자산)
  - portfolio_history + user_cash_history 기반 총자산 히스토리 조회
  - 기간 이전 최신 현금 스냅샷을 조회 시작 시점 현금으로 이월
  - 평균 매수가·수량 수정
  - Python 실시간 포트폴리오 계산 실행
- WatchlistService
  - 관심 종목 CRUD
  - HerdService를 재사용한 관심 종목 HERD 조회
- TickerReadinessService
  - 포트폴리오/관심종목 추가 전 티커 형식과 HERD 데이터 준비 여부 검증
  - HERD 점수가 없는 심볼은 저장하지 않아 백필/스케줄러 대상 오염을 방지
- FinancialsService
  - Python stock_info_collector.get_stock_financials(ticker) 호출
  - 종목 재무정보 반환 (ProcessBuilder, 티커 정규식 검증 포함)
- HerdReliabilityService
  - Python signal_reliability.py 호출
  - 저장된 HERD 히스토리와 yfinance 가격 기반 신호 성능 신뢰도 및 신호 이후 평균 수익/낙폭 반환
- FinnhubService
  - Python finnhub_collector 호출
  - 회사명/티커 기반 심볼 검색 응답 반환
- SignalJournalService
  - HERD 판단 기록 CRUD
  - MVP 단계에서는 `local` 사용자 기준으로 저장하고, 추후 인증 도입 시 userId만 교체한다.

## DB/JPA 원칙
- Python `init_db.py`가 생성한 테이블 스키마를 기준으로 한다.
- `spring.jpa.hibernate.ddl-auto=validate`를 사용한다.
- Spring Boot는 스키마를 생성/변경하지 않는다.
- MVP 사용자 ID는 `AppConstants.DEFAULT_USER_ID`로 고정한다.

## Python 연동
- HERD 데이터가 없을 때 `HerdService`가 Python `calculate_on_demand(ticker)`를 실행한다.
- 포트폴리오 HERD 강제 갱신은 `calculate_many_on_demand(tickers, force=True)`를 한 Python 프로세스에서 실행한다.
- HERD 강제 갱신 실패는 오래된 DB 값을 조용히 반환하지 않고 API 오류로 노출한다.
- `/api/portfolio/realtime` 호출 시 `PortfolioService`가 Python `calculate_current_portfolio('local')`를 실행한다.
- Python 실행은 `ProcessBuilder` 기반이며 기본 타임아웃은 30초다.
- 포트폴리오 HERD 배치 갱신 타임아웃은 120초다.
- Python 실행 경로는 `data/.venv/bin/python3.12`를 사용한다.
- 로컬 백엔드 실행은 루트 `.env`를 로드하는 `./scripts/run-backend.sh`를 우선 사용한다. `./gradlew bootRun`만 직접 실행하면 `DB_PASSWORD`가 주입되지 않아 DB 접속에 실패할 수 있다.

## 예외 처리
- `ResourceNotFoundException` → HTTP 404
- `DuplicateResourceException` → HTTP 409
- `IllegalArgumentException` → HTTP 400
- 기타 예외 → HTTP 500
- 모든 예외 응답은 `ApiResponse` 형태로 통일한다.

## 부분 구현 / 미구현
- 별도 `GET /api/stocks/{ticker}/indicators` 엔드포인트는 없음. 지표 분해값은 `/api/stocks/{ticker}/herd` 응답에 포함된다.
- 200주 MA 위치는 `HerdScoreResponse.ma200Weekly`로 응답한다.
- HERD v4 응답은 `herdScore`/`herdV4`에 최종 점수, `herdBase`에 v3 기본 점수, `epsMultiplier`/`sectorMultiplier`에 보정 승수를 포함한다.
- HERD 응답은 `stocks` 테이블 기준 `companyName`, `sector`, `logoUrl`을 포함한다. 로고가 없으면 frontend가 티커 배지로 fallback한다.
- HERD 신뢰도 응답은 DB 스키마 변경 없이 `HerdService`가 계산한다. `qualityScore`, `qualityLevel`, `qualityLabel`, `qualitySummary`, `qualityFlags`, `qualityReasons`를 포함한다.
- HERD 신뢰도는 `daily_prices` 기간이 아니라 저장된 HERD 산출 결과의 완성도(핵심 지표, 200주 MA, v4 보정 승수, 최신성)를 기준으로 계산한다.
- HERD 신호 성능 신뢰도는 `HerdReliabilityService`가 Python을 호출해 계산한다. `qualityScore`와 달리 Flee/Rush 적중률, 신호 이후 평균 수익/낙폭, MDD 개선, 수익률 보존, 연간 행동 수를 기준으로 한다.
- HERD_v6 Progressive Action Layer 응답은 DB 스키마 변경 없이 `ActionDecisionService`가 계산한다. HERD_v4 점수, 지표 품질, 데이터 품질, 저장된 HERD 히스토리의 최근 변화율을 함께 사용하며 `actionModelVersion`, `actionModelName`, `baseModelVersion`, `actionModelStatus`, `actionScore`, `actionGrade`, `actionLabel`, `actionRatio`, `actionRegime`, `actionRegimeLabel`, `actionReasons`, `actionWarnings`를 포함한다.
- HERD 응답은 저장된 `herd_scores` 히스토리 기준 현재 `signal`/`herdStage`가 언제부터 이어졌는지 계산해 `signalStartedAt`, `signalDurationDays`, `stageStartedAt`, `stageDurationDays`를 포함한다.
- 포트폴리오 종목별 `dailyChangePct`는 KST 22:30 미국장 시작을 하루 경계로 본다. 22:30 전에는 직전 미국장 세션을 오늘로 유지한다.
- 로그인/인증/멀티유저 API는 없음. 현재는 `local` 사용자 고정.
- HERD 판단 기록은 `signal_journal` 테이블에 저장한다. 과거 localStorage 기반 기록장은 제거했고, frontend는 `/api/journal`을 기준으로 조회/저장한다.
- 증권사 API 추상화는 구현되어 있지 않다.
- Action Layer와 `settings.py`는 Rush 75 / Flee 15 행동 신호 기준을 사용한다. Python `calculator.py`와 frontend `utils/herdStage.js`도 같은 기준을 따른다.
- 가격 히스토리, 뉴스, 애널리스트, 내부자 거래 API/DTO/서비스는 MVP 정리 과정에서 제거했다.

## 코드 원칙
- Controller는 요청/응답만 처리, 비즈니스 로직은 Service로
- Repository는 DB 접근만, 쿼리 로직은 여기서
- DTO와 Entity 분리 필수
- 모든 API 예외처리 포함 (@ExceptionHandler)
- CORS 설정 config/에서 관리

## AI 작업 원칙
- 실제 backend 코드 기준으로 판단한다.
- 구현되지 않은 기능은 완료 처리하지 않는다.
- README보다 실제 코드를 우선한다.
- 추측하지 않는다.
- 작업 범위를 벗어난 파일은 수정하지 않는다.
- backend/CLAUDE.md는 backend 개발만을 위한 문서로 유지한다.

## 작업 시 주의
- data/, frontend/ 폴더는 읽지 말 것
- DB 스키마는 Python이 먼저 생성한 테이블 기준으로 맞출 것
- Python 직접 실행은 HerdService/PortfolioService의 ProcessBuilder 경로에 한정할 것

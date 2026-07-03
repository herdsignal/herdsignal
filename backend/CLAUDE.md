# backend/ — Spring Boot REST API

최종 업데이트: 2026-07-03

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
GET    /api/stocks/{ticker}/prices            종목 가격 히스토리 조회
GET    /api/stocks/{ticker}/news              종목 뉴스 조회 (Finnhub)
GET    /api/stocks/{ticker}/analyst           애널리스트 컨센서스 조회 (Finnhub)
GET    /api/stocks/{ticker}/insider           내부자 거래 조회 (Finnhub)
GET    /api/stocks/{ticker}/herd/history      종목 HERD 히스토리 조회
GET    /api/portfolio/herd                    포트폴리오 전체 HERD 조회
POST   /api/portfolio/herd/refresh            포트폴리오 전체 HERD 강제 재계산 후 조회

GET    /api/portfolio                         포트폴리오 목록 조회
POST   /api/portfolio                         포트폴리오 종목 추가
DELETE /api/portfolio/{ticker}                포트폴리오 종목 삭제
GET    /api/portfolio/summary                 포트폴리오 평가 요약 조회
GET    /api/portfolio/history?period=month    포트폴리오 히스토리 조회
PATCH  /api/portfolio/{ticker}/avg-price      평균 매수가·수량 수정
GET    /api/portfolio/realtime                yfinance 실시간 포트폴리오 계산

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
- ActionDecisionService
  - HERD 점수 + 지표 분해값 + 데이터 품질 기반 장기투자 행동 강도 계산
  - DB 저장 없이 API 응답 시점에 actionScore/actionLabel/actionRatio/actionRegime을 산출
- PortfolioService
  - 포트폴리오 CRUD
  - 평가 요약 조회
  - portfolio_history 기반 히스토리 조회
  - 평균 매수가·수량 수정
  - Python 실시간 포트폴리오 계산 실행
- WatchlistService
  - 관심 종목 CRUD
  - HerdService를 재사용한 관심 종목 HERD 조회
- FinancialsService
  - Python stock_info_collector.get_stock_financials(ticker) 호출
  - 종목 재무정보 반환 (ProcessBuilder, 티커 정규식 검증 포함)
- PriceHistoryService
  - daily_prices 기반 종목 가격 히스토리 반환
  - period 파라미터(1M/3M/1Y/5Y) 기준 조회
- FinnhubService
  - Python finnhub_collector 호출
  - 회사명/티커 기반 심볼 검색 응답 반환
  - 뉴스, 애널리스트 컨센서스, 내부자 거래 응답 반환
  - frontend StockDetail에서는 현재 뉴스/애널리스트/내부자 거래 섹션을 표시하지 않음

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

## 예외 처리
- `ResourceNotFoundException` → HTTP 404
- `DuplicateResourceException` → HTTP 409
- 기타 예외 → HTTP 500
- 모든 예외 응답은 `ApiResponse` 형태로 통일한다.

## 부분 구현 / 미구현
- 별도 `GET /api/stocks/{ticker}/indicators` 엔드포인트는 없음. 지표 분해값은 `/api/stocks/{ticker}/herd` 응답에 포함된다.
- 200주 MA 위치는 `HerdScoreResponse.ma200Weekly`로 응답한다.
- HERD v4 응답은 `herdScore`/`herdV4`에 최종 점수, `herdBase`에 v3 기본 점수, `epsMultiplier`/`sectorMultiplier`에 보정 승수를 포함한다.
- HERD 신뢰도 응답은 DB 스키마 변경 없이 `HerdService`가 계산한다. `qualityScore`, `qualityLevel`, `qualityLabel`, `qualitySummary`, `qualityFlags`, `qualityReasons`를 포함한다.
- HERD 신뢰도는 `daily_prices` 기간이 아니라 저장된 HERD 산출 결과의 완성도(핵심 지표, 200주 MA, v4 보정 승수, 최신성)를 기준으로 계산한다.
- HERD_v5 Action Layer 응답은 DB 스키마 변경 없이 `ActionDecisionService`가 계산한다. `actionModelVersion`, `actionModelName`, `baseModelVersion`, `actionModelStatus`, `actionScore`, `actionGrade`, `actionLabel`, `actionRatio`, `actionRegime`, `actionRegimeLabel`, `actionReasons`, `actionWarnings`를 포함한다.
- 뉴스/애널리스트/내부자 거래 API는 backend에 존재하지만 현재 frontend 화면에서는 사용하지 않는다.
- 로그인/인증/멀티유저 API는 없음. 현재는 `local` 사용자 고정.
- 증권사 API 추상화는 구현되어 있지 않다.

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

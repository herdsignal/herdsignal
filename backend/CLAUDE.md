# backend/ — Spring Boot REST API

## 이 폴더의 역할
MariaDB에 저장된 HERD Index 데이터를 React에 서빙.
데이터 계산은 하지 않음. Python이 계산한 결과를 읽어서 반환만 함.

## 패키지 구조
```
src/main/java/com/herdsignal/
├── controller/     REST API 엔드포인트
├── service/        비즈니스 로직
├── repository/     DB 접근 (JPA)
├── domain/         엔티티 클래스
└── config/         설정 (DB, CORS 등)
```

## 주요 API 엔드포인트 (예정)
```
GET /api/stocks/{ticker}/herd       종목 HERD Index 조회
GET /api/portfolio/herd             포트폴리오 전체 HERD 조회
GET /api/stocks/{ticker}/indicators 지표 분해 데이터 조회
POST /api/watchlist                 관심종목 등록
```

## 기술 스택
- Spring Boot 3.x
- Gradle
- Spring Data JPA
- MariaDB
- Lombok

## 코드 원칙
- Controller는 요청/응답만 처리, 비즈니스 로직은 Service로
- Repository는 DB 접근만, 쿼리 로직은 여기서
- DTO와 Entity 분리 필수
- 모든 API 예외처리 포함 (@ExceptionHandler)
- CORS 설정 config/에서 관리

## 증권사 API 추상화
```java
BrokerageService (interface)
├── TossInvestBrokerageService
└── KisBrokerageService
```
나중에 토스 API 나오면 config 한 줄만 변경.

## 작업 시 주의
- data/, frontend/ 폴더는 읽지 말 것
- DB 스키마는 Python이 먼저 생성한 테이블 기준으로 맞출 것
- Python과 Spring Boot는 DB로만 통신

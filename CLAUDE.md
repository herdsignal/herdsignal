# HerdSignal — 프로젝트 공통 지침

## 서비스 개요
미국주식 장기투자자를 위한 데이터 기반 타이밍 도구.
개별 주식마다 HERD Index(0~100)를 산출해 고점 익절 / 저점 추가매수 타이밍을 제안.

## 핵심 개념
- **HERD Index**: 개별주 군중심리 지표 (0~100)
- **5단계**: Flee(0~20) → Scatter(20~40) → Calm(40~60) → Drift(60~80) → Rush(80~100)
- **버핏 철학**: Rush일 때 익절, Flee일 때 매수

## 모노레포 구조
```
herdsignal/
├── data/       Python 데이터 엔진 (yfinance 수집 + HERD 계산)
├── backend/    Spring Boot REST API (DB 서빙)
└── frontend/   React 대시보드
```

## 데이터 흐름
```
yfinance → Python(HERD 계산) → MariaDB → Spring Boot API → React
```
Python은 계산 + 저장만. Spring Boot는 서빙만. 역할 분리 엄수.

## 기술 스택
- Python 3.11+ / yfinance / pandas / ta-lib
- Spring Boot 3.x / Gradle / JPA / MariaDB
- React 18

## 공통 코드 원칙
- 함수/클래스 단위 역할 분리
- 예외처리 필수
- 하드코딩 금지 (설정값은 config 분리)
- 주석 필수
- 한 번에 하나씩 — 파일 구조 먼저 제안 후 코드 작성

## 토큰 절약 규칙
- data/ 작업 시 backend/, frontend/ 파일 읽지 말 것
- backend/ 작업 시 data/, frontend/ 파일 읽지 말 것
- frontend/ 작업 시 data/, backend/ 파일 읽지 말 것
- 각 폴더의 CLAUDE.md만 추가로 참조할 것

## 현재 개발 단계
- [x] 기획 완료
- [x] GitHub 세팅 완료
- [ ] data/ HERD Index 알고리즘 구현 ← 현재
- [ ] backend/ Spring Boot API 구현
- [ ] frontend/ React 대시보드 구현

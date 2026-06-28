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

## 커밋 메시지 규칙
형식:
```
git commit -m "type: 제목" -m "- 세부사항1" -m "- 세부사항2"
```

type 종류:
- `feat`: 새 기능 추가
- `fix`: 버그 수정
- `chore`: 설정, 패키지 등 기타 작업
- `refactor`: 코드 구조 개선 (기능 변경 없음)
- `docs`: 문서 수정

예시:
```
git commit -m "feat: RSI 계산 함수 구현" -m "- 월봉/주봉 RSI 계산 로직 추가" -m "- pandas_ta 라이브러리 활용" -m "- 종목별 역사적 상대값 정규화 적용"
```

규칙:
- 제목은 50자 이내
- 세부사항은 실제 변경된 내용 구체적으로
- 세부사항 2~4개 권장

### 언급 방식
커밋 타이밍이 되면 아래 형식으로 먼저 알려줄 것.

```
✅ 커밋 타이밍입니다.
작업 내용: (완성된 내용 한 줄 요약)
명령어:
git add .
git commit -m "type: 제목" -m "- 세부사항1" -m "- 세부사항2"
```

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

---

## HERD Index 현재 버전 (v1) 확정 파라미터

### 알고리즘
- 정규화 방식: 백분위수 (scipy.stats.percentileofscore)
- 데이터 기간: 10년
- 구성 지표: 월봉RSI(25%), 주봉RSI(20%), 52주위치(20%), MA200이격도(15%), 거래량강도(10%)

### 임계값
- Rush  ≥ 75  → 30% 익절
- Drift 60~75 → 5% 익절
- Calm  40~60 → 보유 유지
- Scatter 15~40 → 10% 추가매수 (1단계 신호)
- Flee  ≤ 15  → 30% 추가매수 (2단계 신호)

### 신호 규칙
- 신호 중복 제거: 20일 이내 재발생 무시
- VIX 추가: 하지 않음 (v2에서 검토)

### 백테스트 검증 결과
- 평균 MDD 8.9%p 개선
- 평균 수익률 59.3% 보존
- Flee 신호 분포 6~10% (이상적)
- Rush 신호 분포 3~9% (종목 특성에 따라 상이)

---

## HERD Index 개선 로드맵

### v1 (현재) — 기술적 지표 기반
- 월봉/주봉 RSI, 52주 고저, MA200 이격도, 거래량
- 백분위수 정규화

### v2 (MVP 완성 후) — 선행 지표 추가
- 옵션 Put/Call 비율
- 공매도 비율 (Short Interest)
- 종목 간 상관관계 반영

### v3 (6개월 후) — 거시경제 연동
- VIX
- 달러 인덱스 (DXY)
- 10년물 국채 수익률

### v4 (1년 후) — ML 기반 최적화
- 가중치 자동 최적화
- 종목 카테고리별 다른 파라미터 적용

---

## 현재 HERD v1의 한계 (인지하고 개발할 것)
- 전부 후행 지표 — 주가 하락 후 신호 발생
- 거시경제 미반영 — 금리/전쟁 등 매크로 이벤트 대응 약함
- V자 반등 포착 불가 — 단기 충격 후 빠른 회복 구간 미감지
- 종목 간 상관관계 미반영
→ MVP에서는 이 한계를 인지한 채로 사용. 개선은 v2부터.

---

## 개발 현황

### 완료
- [x] data/ HERD Index 알고리즘 구현 및 백테스트 검증

### 진행 중
- [ ] data/ DB 저장 로직 ← 현재
- [ ] backend/ Spring Boot API
- [ ] frontend/ React 대시보드

# frontend/ — React 대시보드

## 이 폴더의 역할
Spring Boot API를 호출해서 HERD Index 데이터를 시각화.
데이터 계산 없음. API 호출 + UI 렌더링만.

## 폴더 구조
```
src/
├── components/     재사용 컴포넌트
│   ├── HerdCard/   종목 카드 (HERD 점수 + 미니 애니메이션)
│   ├── HerdDots/   무리 점 애니메이션
│   └── SpectrumBar/ Flee~Rush 스펙트럼 바
├── pages/          화면 단위
│   ├── Home/       포트폴리오 대시보드
│   ├── StockDetail/ 종목 상세
│   └── Search/     종목 검색 & 추가
└── api/            Spring Boot API 호출
    └── herdApi.js
```

## 디자인 원칙
- 클린 미니멀 (토스, 애플 느낌)
- 영어 베이스 브랜드 언어
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
- HerdCard: 종목별 카드 (왼쪽 컬러 스트라이프 + 점수 + 미니 도트)
- HerdDots: 무리 점 애니메이션 (Rush=오른쪽 뭉침, Flee=흩어짐)
- 모달: 종목 상세 (지표 분해 + Timing Signal)

## API 연동
모든 API 호출은 src/api/herdApi.js에서만 관리.
Spring Boot 기본 URL은 환경변수로 관리 (.env).

## 작업 시 주의
- data/, backend/ 폴더는 읽지 말 것
- API 응답 구조는 backend/CLAUDE.md 참고
- 로그인 없이 시작 (MVP는 로컬 스토리지로 포트폴리오 관리)

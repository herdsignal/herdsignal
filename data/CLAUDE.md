# data/ — Python 데이터 엔진

## 이 폴더의 역할
yfinance로 주가 데이터 수집 + HERD Index 계산 + MariaDB 저장.
Spring Boot나 React와 직접 통신하지 않음. DB만 바라봄.

## 폴더 구조
```
data/
├── collectors/     yfinance 데이터 수집
├── indicators/     개별 지표 계산 (RSI, 이격도 등)
├── herd/           HERD Index 합산 알고리즘
├── scheduler/      주기적 수집 스케줄러
├── config/         설정값 (DB 접속정보, 티커 목록 등)
└── requirements.txt
```

## HERD Index 구성 지표 (5개)
| 지표 | 설명 | 계산 방식 |
|------|------|---------|
| 월봉 RSI | 장기 과열/과냉 | pandas_ta |
| 주봉 RSI | 중기 과열/과냉 | pandas_ta |
| 52주 고저 위치 | 현재가의 1년 범위 내 위치 | (현재가 - 52주저) / (52주고 - 52주저) |
| 200일 이동평균 이격도 | 추세 대비 괴리율 | (현재가 - MA200) / MA200 |
| 거래량 강도 | 최근 거래량 vs 평균 거래량 | 20일 거래량 비율 |

## 정규화 원칙
절대값이 아닌 종목별 역사적 상대값으로 정규화.
→ 모든 종목에 동일한 공식 적용 가능.
→ 엔비디아 RSI 75와 코카콜라 RSI 75가 다른 의미임을 자동 반영.

## 코드 원칙
- 지표별로 파일 분리 (indicators/rsi.py, indicators/ma.py 등)
- DB 연결은 config/database.py에서만 관리
- yfinance 호출 실패 시 재시도 로직 포함
- 계산 결과 로깅 필수

## 작업 시 주의
- backend/, frontend/ 폴더는 읽지 말 것
- 이 폴더의 역할은 계산과 저장뿐
- 비즈니스 로직은 Spring Boot에서 처리

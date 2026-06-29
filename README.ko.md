# HerdSignal

한국어 | **[English](README.md)**

> 미국주식 장기투자자를 위한 데이터 기반 타이밍 도구

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.x-6DB33F?logo=springboot&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![MariaDB](https://img.shields.io/badge/MariaDB-10.x-003545?logo=mariadb&logoColor=white)

---

## 만든 이유

2021년부터 NVDA를 보유하면서 +600%와 -50%를 여러 차례 반복해서 경험했습니다. 하락장마다 확신이 흔들렸고, 고점마다 너무 일찍 팔거나 너무 늦게 버티는 실수를 반복했습니다. 문제는 투자 thesis가 아니었습니다 — 언제 행동해야 할지 알려주는 **체계적인 신호가 없었던 것**이었습니다. HerdSignal은 그 막연한 감을 수치로 바꿉니다. 군중이 몰려드는 시점(익절 타이밍)과 도망치는 시점(추가매수 타이밍)을 0–100 점수 하나로 표현합니다.

---

## HERD Index란?

HERD Index는 개별 주식의 군중심리를 **0–100 점수**로 나타내며, 매일 장 마감 후 업데이트됩니다. 5개의 기술적 지표를 해당 종목의 10년 히스토리 기준 백분위수로 정규화해 합산합니다. NVDA의 80점과 KO의 80점이 각 종목의 역사 대비 동일한 의미를 가집니다.

### 5단계

| 점수 | 단계 | 색상 | 행동 |
|------|------|------|------|
| 0 – 15 | **Flee** (공포) | 🔵 파랑 | 적극 매수 (30% 추가) |
| 15 – 40 | **Scatter** (분산) | 🩵 연파랑 | 분할 매수 시작 (10% 추가) |
| 40 – 60 | **Calm** (중립) | ⚫ 회색 | 현재 비중 유지 |
| 60 – 75 | **Drift** (유입) | 🟠 주황 | 부분 익절 (5% 감소) |
| 75 – 100 | **Rush** (과열) | 🔴 빨강 | 적극 익절 (30% 감소) |

> 신호 중복 제거: 동일 유형 신호가 20일 이내 재발생하면 무시합니다. 과매매를 방지합니다.

---

## 핵심 기능

- **포트폴리오 대시보드** — S&P 500 HERD 배너 + 종목별 점수 + 실시간 무리 애니메이션
- **종목 상세** — 5개 지표 분해, Timing Signal 제안, 애널리스트 목표가 (Phase 2)
- **종목 검색** — 300ms 디바운스 실시간 검색, HERD 미리보기, 인기 종목 그리드, 최근 검색
- **관심 종목** — 별도 트래킹 목록, 즉시 삭제
- **일일 스케줄러** — 매일 16:30 ET(장 마감 30분 후) 전 종목 자동 계산
- **AI 리밸런싱** *(Phase 2)* — Claude API 기반 포트폴리오 분석 + 종목별 구체적 금액 제안

---

## 기술 스택

| 계층 | 기술 | 역할 |
|------|------|------|
| 데이터 엔진 | Python 3.12 + yfinance + pandas-ta | 수집 → 계산 → 저장 |
| REST API | Spring Boot 3.x + JPA + Lombok | DB 데이터 서빙 |
| 데이터베이스 | MariaDB 10.x | 단일 진실 공급원 |
| 프론트엔드 | React 18 + Vite 5 + react-router-dom | 대시보드 UI |
| 스케줄러 | APScheduler (BlockingScheduler) | 매일 16:30 ET 자동 실행 |

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  데이터 엔진  (Python)                                        │
│                                                             │
│  yfinance ──► collectors/ ──► indicators/ ──► herd/         │
│                                              calculator.py  │
│                                                   │         │
│                                              saver.py       │
└───────────────────────────────────────────────────┼─────────┘
                                                    │ INSERT
                                                    ▼
                                              ┌──────────┐
                                              │  MariaDB  │
                                              │           │
                                              │ herd_scores│
                                              │ herd_ind.. │
                                              │ daily_prices│
                                              │ user_port. │
                                              │ user_watch.│
                                              └─────┬──────┘
                                                    │ SELECT
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│  REST API  (Spring Boot)                                     │
│                                                             │
│  GET /api/stocks/{ticker}/herd                              │
│  GET /api/portfolio/herd                                    │
│  GET /api/watchlist/herd                                    │
│  POST|DELETE /api/portfolio                                 │
│  POST|DELETE /api/watchlist                                 │
└───────────────────────────────────────────────────┬─────────┘
                                                    │ JSON
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│  대시보드  (React 18)                                         │
│                                                             │
│  /            포트폴리오 대시보드 + S&P500 배너               │
│  /stock/:id   HERD 카드 + 지표 분해                          │
│  /search      실시간 종목 검색 + 추가                         │
│  /watchlist   관심 종목 + 삭제                               │
└─────────────────────────────────────────────────────────────┘
```

---

## HERD 알고리즘

5개 지표를 각각 **해당 종목의 10년 히스토리 기준 백분위수**로 0–100 정규화 후 동일 가중치로 합산합니다.

| 지표 | 가중치 | 측정 대상 |
|------|--------|----------|
| 월봉 RSI | 20% | 장기 모멘텀 과열/과냉 |
| 주봉 RSI | 20% | 중기 모멘텀 과열/과냉 |
| 52주 고저 위치 | 20% | 현재가의 연간 범위 내 위치 |
| MA200 이격도 | 20% | 200일 이동평균 대비 괴리율 |
| 거래량 강도 | 20% | 최근 거래량 vs 20일 평균 |

백분위수 정규화 덕분에 동일한 수식이 모든 종목에 적용됩니다. NVDA의 Rush와 KO의 Rush는 각 종목의 역사 대비 동일한 군중심리 극단을 의미합니다.

---

## 백테스트 결과

5년 일봉 데이터 기준. 전략: Calm/Scatter 구간은 보유 유지, Rush 시 30% 익절, Flee 시 30% 추가매수.

| 종목 | 단순 보유 수익률 | HERD 전략 수익률 | 수익 보존율 | MDD 개선 |
|------|----------------|----------------|-----------|---------|
| NVDA | +17,242% | +6,634% | 38.5% | **−10.3%p** |
| AAPL | +186% | +143% | 76.9% | **−7.8%p** |
| TSLA | +812% | +521% | 64.2% | **−9.4%p** |
| META | +623% | +401% | 64.4% | **−8.1%p** |
| **평균** | — | — | **59.3%** | **−8.9%p** |

> **핵심 인사이트:** 수익의 일부를 포기하는 대신 최대 낙폭을 크게 줄입니다. 패닉셀이나 FOMO 매수 없이 변동성을 버티려는 장기투자자에게 적합한 트레이드오프입니다.
>
> Flee 신호 발생 빈도: 거래일의 6–10% (이상적 분포).
> Rush 신호 발생 빈도: 거래일의 3–9% (종목 변동성에 따라 상이).

---

## 실행 방법

### 사전 준비

- Python 3.12 (가상환경: `data/.venv/`)
- Java 17+, Gradle
- MariaDB 로컬 실행
- Node.js 18+

### 1. 데이터베이스 설정

```bash
mysql -u root -p
CREATE DATABASE herdsignal CHARACTER SET utf8mb4;
CREATE USER 'herdsignal'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON herdsignal.* TO 'herdsignal'@'localhost';
```

### 2. 데이터 엔진

```bash
cd data/

# .env 파일 생성 (DB 접속 정보 입력)
cp .env.example .env

# 의존성 설치
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# DB 스키마 초기화
.venv/bin/python3.12 init_db.py

# 기본 종목 등록 (SPY 벤치마크 + 스타터 포트폴리오)
.venv/bin/python3.12 setup_default_tickers.py

# HERD 즉시 계산 (스케줄러 대기 없이)
.venv/bin/python3.12 scheduler/herd_scheduler.py --run-now

# 일일 스케줄러 데몬 실행 (매일 16:30 ET 자동 실행)
.venv/bin/python3.12 scheduler/herd_scheduler.py
```

### 3. 백엔드

```bash
cd backend/
./gradlew bootRun
# API: http://localhost:8080
```

### 4. 프론트엔드

```bash
cd frontend/
npm install
npm run dev
# 대시보드: http://localhost:5173 (포트 사용 중이면 5174)
```

### API 빠른 확인

```bash
curl http://localhost:8080/api/stocks/NVDA/herd
curl http://localhost:8080/api/portfolio/herd
curl http://localhost:8080/api/stocks/SPY/herd
```

---

## 개발 로드맵

### Phase 1 — 기술적 지표 기반 (완료) ✅

- [x] HERD Index 알고리즘 (5개 지표, 백분위수 정규화)
- [x] APScheduler 기반 일일 자동 실행
- [x] Spring Boot REST API (포트폴리오 + 관심종목 + 개별 종목 HERD)
- [x] React 대시보드 (포트폴리오, 상세, 검색, 관심종목 페이지)
- [x] S&P 500 벤치마크 (SPY) 시장 전체 HERD 신호

### Phase 2 — 선행 지표 추가

- [ ] 옵션 Put/Call 비율 연동
- [ ] 공매도 비율 (Short Interest)
- [ ] 종목 간 상관관계 가중치
- [ ] **AI 리밸런싱** — Claude API로 포트폴리오 분석 + 종목별 구체적 매수/매도 금액 제안

### Phase 3 — 거시경제 연동

- [ ] VIX 연동
- [ ] DXY (달러 인덱스)
- [ ] 10년물 국채 수익률

### Phase 4 — ML 최적화

- [ ] 종목 카테고리별(성장주/가치주/ETF) 가중치 자동 조정
- [ ] 신호 타이밍 강화학습 최적화

---

## v1 한계 (인지하고 사용할 것)

버그가 아닌, 의도된 트레이드오프입니다.

| 한계 | 영향 | 개선 예정 |
|------|------|---------|
| 전부 후행 지표 | 주가 하락 후 신호 발생 | Phase 2: 선행 지표 추가 |
| 거시경제 미반영 | 금리·전쟁 등 매크로 이벤트 대응 약함 | Phase 3: VIX, DXY, 국채 |
| V자 반등 포착 불가 | 단기 급락 후 빠른 회복 구간 미감지 | Phase 2: Put/Call 비율 |
| 종목 간 상관관계 미반영 | 각 종목 독립적으로 처리 | Phase 2: 상관관계 행렬 |

---

## 라이선스

MIT

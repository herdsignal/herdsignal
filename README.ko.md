# HerdSignal

한국어 | **[English](README.md)**

> 미국주식 장기투자자를 위한 데이터 기반 타이밍 도구

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.x-6DB33F?logo=springboot&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![MariaDB](https://img.shields.io/badge/MariaDB-10.x-003545?logo=mariadb&logoColor=white)

---

## 만든 이유

HerdSignal은 장기투자자가 보유 종목의 매수, 보유, 일부 익절 타이밍을 감이 아니라 데이터로 판단하도록 돕는 프로젝트입니다.

개별 종목의 HERD Index와 포트폴리오 맥락을 함께 보여주고, 점수를 실제 행동 문장으로 번역합니다.
단순 포트폴리오 트래커보다 “지금 더 살지, 유지할지, 일부 줄일지”를 정리하는 판단 도구를 지향합니다.

---

## HERD Index란?

HERD Index는 개별 주식의 군중심리를 **0-100 점수**로 나타내는 지표입니다. 절대값이 아니라 해당 종목의 과거 흐름 대비 백분위수로 정규화하기 때문에, 성장주와 방어주를 같은 공식으로 비교할 수 있습니다.

운영 계산은 기본 5년 가격 데이터를 사용합니다. v3 기본 점수에 EPS 서프라이즈와 섹터 상대 강도 보정 승수를 적용해 최종 v4 점수를 저장합니다.

### 5단계

| 점수 | 단계 | 의미 | 행동 |
| --- | --- | --- | --- |
| 0-15 | Flee | 군중 이탈 | 적극 매수 검토 |
| 15-40 | Scatter | 군중 흩어짐 | 분할 매수 검토 |
| 40-60 | Calm | 군중 균형 | 보유 유지 |
| 60-75 | Drift | 군중 쏠림 | 일부 익절 고려 |
| 75-100 | Rush | 군중 밀집 | 적극 익절 고려 |

`Herd Flow` 애니메이션은 이 단계를 점의 분포로 표현합니다. Flee는 전 영역에 듬성듬성 흩어지고, Rush는 좁은 영역에 촘촘하게 밀집합니다.

---

## 핵심 기능

- **Dashboard**: S&P 500 Herd Flow 배너, 포트폴리오 평가 요약, KRW/USD 토글, 목표 비중 기반 리밸런싱 추천, HERD 변화 요약, 자산 진단
- **StockDetail**: HERD v4 점수, 장기투자 판단, 지표 분해, EPS/섹터 보정 승수, 가격 차트, 재무정보, 판단 요약
- **Search**: 대표 종목 검색, HERD 미리보기, 타이밍 후보, 최근 검색
- **Watchlist**: 관심 종목 HERD 카드, 기회 대기열, 매수/중립/익절 후보 요약, 정렬, 삭제
- **History**: portfolio_history 기반 자산 차트, 시작 대비/고점 대비/점검 포인트
- **Rebalance Plan**: Claude API 연결 전 규칙 기반 리밸런싱 플랜, 목표 비중/현금 목표/예산/강도 설정
- **Herd Flow Preview**: `/herd-flow`에서 5단계 애니메이션 비교

---

## 기술 스택

| 계층 | 기술 | 역할 |
| --- | --- | --- |
| data | Python 3.12, yfinance, pandas-ta, APScheduler, Finnhub | 수집, 계산, 저장 |
| backend | Spring Boot 3.x, JPA, MariaDB, Gradle | DB 조회, REST API, Python on-demand 실행 |
| frontend | React 18, Vite 5, Recharts, Axios | 대시보드 UI |
| database | MariaDB | HERD, 포트폴리오, 관심종목, 자산 히스토리 저장 |

---

## 아키텍처

```text
yfinance / Finnhub
        |
        v
Python data engine
        |
        v
MariaDB
        |
        v
Spring Boot REST API
        |
        v
React frontend
```

Python은 계산과 저장을 담당하고, Spring Boot는 DB 데이터를 API로 서빙합니다. React는 API를 호출해 화면만 구성합니다.

---

## 주요 API

- `GET /api/stocks/{ticker}/herd`
- `POST /api/stocks/{ticker}/herd/refresh`
- `GET /api/stocks/{ticker}/prices?period=1M|3M|1Y|5Y`
- `GET /api/stocks/{ticker}/financials`
- `GET /api/stocks/{ticker}/herd/history?period=1y|3y`
- `GET /api/portfolio`
- `GET /api/portfolio/herd`
- `POST /api/portfolio/herd/refresh`
- `GET /api/portfolio/summary`
- `GET /api/portfolio/history?period=month|year`
- `GET /api/portfolio/realtime`
- `GET /api/watchlist`
- `GET /api/watchlist/herd`

backend에는 뉴스, 애널리스트, 내부자 거래 API도 존재하지만 현재 frontend StockDetail에서는 표시하지 않습니다.

---

## HERD 알고리즘

기본 점수는 아래 지표들의 백분위수 정규화 가중합입니다.

| 지표 | 가중치 | 설명 |
| --- | ---: | --- |
| 월봉 RSI | 24% | 장기 모멘텀 |
| 200주 MA 위치 | 20% | 장기 추세 위치 |
| 주봉 RSI | 19% | 중기 모멘텀 |
| 52주 위치 | 19% | 연간 가격 범위 내 위치 |
| MA200 이격도 | 18% | 200일 추세 대비 거리 |
| 거래량 강도 | 0% | 계산은 유지, 운영 점수 미반영 |

v4는 기본 점수에 두 가지 보정 승수를 곱합니다.

- EPS 서프라이즈: 최근 4분기 beat/miss 흐름
- 섹터 상대 강도: 종목 90일 수익률과 섹터 ETF 90일 수익률 비교

최종 점수는 `herd_scores.herd_score`에 저장되며, API는 `herdV4`, `herdBase`, `epsMultiplier`, `sectorMultiplier`를 함께 제공합니다.

---

## 실행 방법

### 사전 준비

- Python 3.12
- Java 17+
- MariaDB
- Node.js 18+

### 1. 데이터베이스

```bash
mysql -u root -p
CREATE DATABASE herdsignal CHARACTER SET utf8mb4;
CREATE USER 'herdsignal'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON herdsignal.* TO 'herdsignal'@'localhost';
```

### 2. 데이터 엔진

```bash
cd data
cp .env.example .env
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3.12 init_db.py
.venv/bin/python3.12 setup_default_tickers.py
.venv/bin/python3.12 scheduler/herd_scheduler.py --run-now
.venv/bin/python3.12 scheduler/herd_scheduler.py
```

### 3. 백엔드

```bash
cd backend
./gradlew bootRun
```

API 서버는 `http://localhost:8080`에서 실행됩니다.

### 4. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

프론트엔드는 기본적으로 `http://localhost:5173`에서 실행됩니다.

---

## 현재 한계

- 리밸런싱 플랜은 아직 Claude API를 호출하지 않는 규칙 기반 MVP입니다.
- 목표 비중과 리밸런싱 설정은 localStorage에 저장되며 DB 저장은 아직 없습니다.
- Dashboard의 자산 진단은 실제 HERD 전략 백테스트가 아니라 portfolio_history 기반 수익률/MDD 요약입니다.
- 로그인, 멀티유저, 증권사 연동, 배포는 아직 구현되지 않았습니다.
- 공식 증권사 API 연동 전까지는 수동 입력과 CSV/엑셀 import UX를 우선합니다.
- v5 변동성 레이어는 백테스트 후보이며 운영 HERD 점수에는 반영되지 않았습니다.

---

## 로드맵

제품 방향과 우선순위는 [ROADMAP.md](./ROADMAP.md)에 정리되어 있습니다.

---

## 라이선스

MIT

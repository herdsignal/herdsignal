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

- **Dashboard**: S&P 500 Herd Flow 배너, HERD 강도 변화, 현금 포함 포트폴리오 평가 요약, 입출금 착시를 줄인 자산 히스토리, 핵심 리밸런싱 체크, 리스크/알림 조건, 보유 종목 HERD 행동 카드
- **Watchlist**: 장기 추가매수/익절 우선순위와 신호 준비도 기반 매수 대기열
- **Search**: 티커/회사명 검색, HERD 미리보기, 최근 검색, 포트폴리오/관심종목 추가
- **StockDetail**: HERD v4 점수, HERD_v6.1 Validated Progressive Action Layer 판단, 신호 신뢰도 보드, 신호 이후 실제 성과 지표, HERD Index 히스토리, Fundamental Guard, 지표 분해
- **Journal**: 매수/보류/익절 판단을 가격, 수량, 금액, 수익률, HERD 점수, 신호 지속일, 메모와 함께 DB에 저장하는 판단 기록장
- **HERD Lab**: 모델 버전, 백테스트 요약, 신뢰 체크, Action Matrix, HERD 방법론 검증 데이터
- **Responsive UI**: 데스크톱 사이드바와 모바일 하단 탭을 함께 지원하는 반응형 화면

---

## 기술 스택

| 계층 | 기술 | 역할 |
| --- | --- | --- |
| data | Python 3.12, yfinance, pandas-ta, APScheduler, Finnhub | 수집, 계산, 저장 |
| backend | Spring Boot 3.x, JPA, MariaDB, Gradle | DB 조회, REST API, Python on-demand 실행 |
| frontend | React 18, Vite 5, Recharts, Axios | 반응형 대시보드 UI |
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
- `GET /api/stocks/search?q=apple`
- `GET /api/stocks/{ticker}/financials`
- `GET /api/stocks/{ticker}/herd/history?period=1m|3m|1y|3y`
- `GET /api/stocks/{ticker}/herd/reliability?years=3`
- `GET /api/portfolio`
- `GET /api/portfolio/herd`
- `POST /api/portfolio/herd/refresh`
- `GET /api/portfolio/summary`
- `GET /api/portfolio/history?period=month|year|all`
- `GET /api/portfolio/cash`
- `PUT /api/portfolio/cash`
- `GET /api/portfolio/realtime`
- `GET /api/journal`
- `POST /api/journal`
- `GET /api/watchlist`
- `GET /api/watchlist/herd`

현재 MVP backend API는 HERD, 검색, 재무정보, 포트폴리오, 관심종목 중심으로만 노출합니다.

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

HERD_v6.1 행동 모델은 v4 상태 점수 위에 5일·20일 변화 속도와 가속도, 단계 경계 ±2pt 안정화, 신호 생애주기, 데이터·이력 신뢰도 보정을 적용합니다. 섹터 편향 검증용 55종목 히스토리는 `cd data && python herd/history_backfill.py --validation-universe --years 10 --freq weekly`로 누적하고, `python herd/backtest_action_layer.py --full`로 전체 유니버스를 검사합니다. 새 모델의 정확도는 확장 백테스트와 실사용 표본이 통과하기 전까지 확정 성과로 표시하지 않습니다.

### Phase A · Validation v2

현실적인 검증은 `cd data && .venv/bin/python herd/backtest_validation_v2.py --full`로 실행합니다. 신호일 종가로 판단하고 다음 거래일 시가에 수수료 0.1%와 기본 슬리피지 10bp를 적용하며, JSON/CSV 결과를 `data/reports/validation_v2/`에 저장합니다. 리포트에는 평균 외에 보존율 중앙값, 하위 10%, 개선 종목 비율, MDD 개선 중앙값, anchored/rolling Walk-forward 결과, 운영 저장 점수 재계산 일치 검사가 포함됩니다.

2026-07-12 기준 55종목 실행 결과는 전체기간 중앙 보존율 63.8%, 기존 Fixed HERD 대비 개선 종목 74.5%, MDD 개선 중앙값 8.1%p였습니다. 과거 섹터 ETF 상대강도는 각 날짜까지의 90거래일 데이터만으로 복원했습니다. 학습구간에서만 제한 후보를 선택한 440개 Walk-forward OOS 구간에서는 개선 비율 36.4%, MDD 개선 중앙값 1.3%p로 낮아져 현재 v6.1은 미래구간 채택 기준 미달입니다. 최초 실행 후 잠근 최근 12개월 Blind Holdout은 중앙 보존율 91.1%, 개선 비율 56.4%, MDD 개선 중앙값 2.5%p였습니다. Blind 결과는 `--unlock-blind`를 명시하지 않는 한 다시 계산하지 않습니다. 이 결과는 현재 생존 대형주 중심 유니버스이며, 과거 EPS는 발표일 원천 데이터가 없어 명시적으로 제외했습니다.

OOS 실패 진단은 `cd data && .venv/bin/python herd/diagnose_validation_v2.py`로 실행합니다. `data/reports/validation_v2/oos_diagnostics.json`과 `oos_failures.csv`에는 섹터·연도·시장 국면·선택 파라미터별 결과, 반복 실패 종목, 심각 실패 구간이 기록됩니다. 0.05%p 이내 차이는 동등으로 처리합니다. 현재 440구간 중 수익 악화 37.3%, MDD 악화 53.4%, 두 지표 모두 Fixed 이상인 구간은 35.9%입니다. 가장 취약한 영역은 에너지 섹터(MDD 악화 82.5%)와 상승장 MDD 방어(MDD 악화 65.3%), 횡보장 수익 악화(51.2%)입니다.

횡보장 행동 억제 단독 실험은 `.venv/bin/python herd/experiment_sideways_filter.py --full`로 재현합니다. 63거래일 절대수익률 5% 이하·추세 품질 35~65를 횡보로 보고 행동 비율을 0/0.5/0.75/1.0 중 학습구간에서만 선택했습니다. 220개 rolling OOS에서 수익 개선 10.5%, 악화 9.1%, MDD 개선 2.7%, 악화 8.2%, 거래 감소 중앙값 0회로 효과가 불충분해 운영 모델에는 채택하지 않았습니다. 결과는 `data/reports/validation_v2/sideways_experiment.json`에 보존합니다.

Risk Cap 단독 실험은 `.venv/bin/python herd/experiment_risk_cap.py --full`로 재현합니다. 기존 신호 방향은 유지하고 약한 추세의 추가매수와 강한 추세의 익절 비율에만 balanced/strict 상한을 적용했습니다. 220개 rolling OOS 중 학습단계에서 미적용을 선택한 구간이 171개였고, 실제 결과가 달라진 OOS는 8개뿐이었습니다. 수익 개선 0%, 악화 1.8%, MDD 개선 0.9%, 악화 0.5%로 효과가 없어 운영 모델에 채택하지 않았습니다. v6.1 비율이 이미 작고 OOS MDD 대부분이 초기 전액 보유 노출에서 발생해 행동 비율 상한만으로는 해결되지 않았습니다. 결과는 `data/reports/validation_v2/risk_cap_experiment.json`에 보존합니다.

검증 리포트는 투자자 상황을 기존 보유자, 신규 진입자, 월 정기 적립식, 주식 70%·현금 30% 목표 비중형으로 분리합니다. 신규 진입자는 HERD 매수 신호 전까지 현금을 유지하며, 적립식 성과는 외부 납입금을 수익으로 오인하지 않도록 납입금 조정 성과지수로 수익률과 MDD를 계산합니다. 따라서 초기 전액 보유 이전의 시장 하락을 모든 사용자에게 동일한 Action Layer 손실로 귀속하지 않습니다.

각 v6.1 행동은 포트폴리오 총수익과 별도로 평가합니다. BUY/SELL 이후 1·3·6개월 수익률과 낙폭, 해당 비율만큼 행동하지 않았을 때 대비한 반사실 효과를 기록하고, 행동 비율·신호 초입/진행/성숙/장기 지속·HERD 단계·시장 국면별 3개월 적중률을 `action_accuracy`에 제공합니다. 아직 평가 기간이 지나지 않은 행동은 적중률 분모에서 제외합니다.

신호 신뢰도는 데이터 품질과 별도로 계산합니다. 저장된 HERD 히스토리와 이후 가격 흐름을 비교해 Flee 적중률, Rush 적중률, 매수 신호 이후 1/3/6개월 평균 수익률, 익절 신호 이후 1/3개월 평균 낙폭, MDD 개선, 수익률 보존, 연간 행동 수, 표본 품질, 매수/익절 edge를 보여줍니다.

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
cp .env.example .env
cd data
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ..
./scripts/run-data.sh init_db.py
./scripts/run-data.sh setup_default_tickers.py
./scripts/run-data.sh scheduler/herd_scheduler.py --run-now
./scripts/run-data.sh scheduler/herd_scheduler.py
```

### 3. 백엔드

```bash
./scripts/run-backend.sh
```

API 서버는 `http://localhost:8080`에서 실행됩니다.

### 4. 프론트엔드

```bash
cd frontend
npm install
cd ..
./scripts/run-frontend.sh
```

프론트엔드는 기본적으로 `http://localhost:5173`에서 실행됩니다.

---

## 현재 한계

- MVP는 전체 포트폴리오 관리가 아니라 HERD 기반 추가매수/보유/익절 타이밍 판단에 집중합니다.
- 자산 히스토리는 입출금 포함 총자산 흐름과 주식 평가액 변화를 분리해서 보여주지만, 완전한 시간가중 수익률 계산은 별도 입출금 이벤트 기록이 필요합니다.
- 리밸런싱 플랜, 기존 자산 기록, Herd Flow Preview 라우트는 존재하지만 메인 사이드바에서는 숨겨져 있습니다.
- 목표 비중은 Dashboard 카드 편집에서 수정하며 localStorage에 저장됩니다. DB 저장은 아직 없습니다.
- 로그인, 멀티유저, 증권사 연동, 배포는 아직 구현되지 않았습니다.
- 포트폴리오 입력은 현재 수동 입력 기준입니다. 공식 증권사 API나 더 간단한 import 흐름은 이후 검토합니다.
- v5 변동성 레이어는 백테스트 후보이며 운영 HERD 점수에는 반영되지 않았습니다.

---

## 로드맵

제품 방향과 우선순위는 [ROADMAP.md](./ROADMAP.md)에 정리되어 있습니다.

---

## 라이선스

MIT

# HerdSignal

미국 주식의 과열과 이탈 정도를 `Flee`부터 `Rush`까지 다섯 단계로 보여주는
개인 투자 관찰 서비스입니다.

가격, 추세, 상대강도, 동종 종목의 움직임을 종합한 HERD 상태를 기록하고,
보유 종목과 관심 종목의 변화를 한곳에서 확인할 수 있습니다.

현재는 매수·매도 추천보다 **상태 관찰과 기록**에 초점을 두고 있습니다.

## 기능

- SPY와 개별 종목의 HERD 상태 확인
- 종목 검색과 상세 분석
- 포트폴리오 및 관심 종목 관리
- HERD 변화 이력과 이후 가격 흐름 확인
- 근거 출처·시점·데이터 공백을 구분한 장기 운용 검토
- 판단 당시 근거 해시 기록과 1·3·6개월 가격 경로 복기
- 투자 판단 기록
- 장 마감 후 가격 수집과 상태 계산

HERD 상태는 다음 범위를 사용합니다.

| 점수 | 상태 | 의미 |
| --- | --- | --- |
| 0–15 | Flee | 이탈 |
| 16–40 | Scatter | 분산 |
| 41–59 | Calm | 중립 |
| 60–74 | Drift | 밀집 시작 |
| 75–100 | Rush | 밀집 |

## 현재 상태

- `State S1`: 서비스 화면에서 사용하는 관찰 모델
- 매수·부분 익절 모델: 연구 중
- 기본 행동 출력: `HOLD`
- 운영 환경: 로컬

백테스트 결과가 좋아 보인다는 이유만으로 매매 신호를 적용하지 않습니다.
검증을 통과하지 않은 모델은 연구 결과로만 남깁니다.

## 기술 스택

- Frontend: React, Vite
- Backend: Java 17, Spring Boot, JPA
- Data: Python, pandas, yfinance, APScheduler
- Database: MariaDB

```text
Python data engine → MariaDB → Spring Boot API → React
```

## 로컬 실행

필요한 환경:

- Python 3.12
- Java 17+
- Node.js 18+
- MariaDB

### 1. 환경변수

```bash
cp .env.example .env
```

`.env`에 DB 접속 정보와 필요한 API 키를 입력합니다.

### 2. 데이터 엔진

```bash
cd data
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
cd ..

./scripts/run-data.sh setup_default_tickers.py
./scripts/run-scheduler-once.sh
```

### 3. 서비스 실행

```bash
./scripts/start-local.sh
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8080`

예약 스케줄러도 함께 실행하려면:

```bash
./scripts/start-local.sh --with-scheduler
```

스케줄러는 기본적으로 미국 동부시간 오후 4시 30분에 실행됩니다. 월–목에는
가격·Daily D1과 기존 전향 관측 결과를 갱신하고, 금요일에는 확정 State S1
관측을 추가합니다. 최신 주간 상태가 Rush인 종목의 SEC 실적 공시도 별도
append-only 원장에 수집하지만, 현재는 매매 신호로 사용하지 않습니다.
로컬 자동 실행을 계속 유지하려면 `./scripts/install-launchd.sh`로 등록합니다.
화면의 데이터 상태 패널에서 가격·일별 상태·주간 상태의 기준일과 스케줄러
heartbeat를 각각 확인할 수 있습니다.

## 테스트

```bash
./scripts/verify.sh
```

백엔드, 프론트엔드, 데이터 엔진 테스트를 한 번에 실행합니다.

## 프로젝트 구조

```text
backend/    Spring Boot API
data/       데이터 수집, 모델 연구, 스케줄러
frontend/   React 웹 앱
docs/       설계와 연구 기록
scripts/    실행, 검증, 백업 도구
```

모델 목표와 현재 연구 결과는 아래 문서에서 확인할 수 있습니다.

- [현재 상태](docs/CURRENT_STATE.md)
- [장기 운용 판단 체계](docs/HERD_LONG_TERM_OPERATING_SYSTEM.md)
- [문서 안내](docs/README.md)
- [모델 목표](docs/HERD_MODEL_CHARTER.md)
- [현재 연구 상태](docs/HERD_RESEARCH_STATUS.md)
- [코드 구조](docs/ARCHITECTURE.md)

## 한계

- 증권사 계좌와 연동되지 않아 포트폴리오는 직접 입력해야 합니다.
- 현재 모델은 매수·매도 추천을 제공하지 않습니다.
- 과거 구성 종목과 상장폐지 종목 데이터가 충분하지 않아 연구 범위에 제한이 있습니다.
- 로컬 환경에서는 컴퓨터가 꺼져 있으면 자동 수집도 중단됩니다.

## License

MIT

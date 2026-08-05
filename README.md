# HerdSignal

HerdSignal은 사용자가 직접 고른 미국 주식을 장기 보유할 때 시장·기업·기대·
정보·포트폴리오 근거를 분리해서 확인하고, 근거의 충돌과 데이터 공백까지
종합하도록 돕는 개인 투자 판단 서비스입니다.

빈번한 매매 신호나 종목 추천이 목적이 아닙니다. 장기 보유 논리가 유지되는지,
새 정보가 기존 판단을 바꾸는지, 아무 행동도 하지 않는 편이 나은지를 반복해서
점검하는 것이 목적입니다.

현재 운영 범위는 관찰과 기록입니다. 검증된 행동 모델이 없으므로 기본 행동은
`HOLD`, 운영 행동 비율은 `0%`입니다.

## 핵심 흐름

```text
독립 원천 데이터
    ↓
시점·품질 검증
    ↓
기업 체력 | 기대·가격 | 시장·섹터 | 차트·군중 | 정보 변화
    ↓
증거 입장 게이트와 종합 판단
    ↓
개인 포트폴리오 번역 + 독립 위험 veto
    ↓
판단 기록과 사후 복기
```

각 영역은 자신에게 허용된 근거만 사용합니다. 같은 가격 정보를 여러 표로
중복 집계하거나, 자료가 없는 영역을 다른 점수로 메우지 않습니다. 생성형 AI는
출처가 있는 근거를 설명할 수 있지만 새로운 사실·목표가·매매 비율을 만들거나
행동을 승인하지 않습니다.

## 제공 기능

- SPY와 개별 종목의 `HERD_STATE_S1` 및 `HERD_TRANSITION_S1` 관찰
- 종목 검색, 가격·HERD 이력, 보유 종목과 관심 종목 관리
- 기업 체력, 기대·가격, 시장·섹터, 차트·군중, 정보 변화의 분리된 근거 표시
- 데이터 기준일, coverage, `NO_VIEW`, 근거 충돌과 veto 표시
- 현재 주식·현금 비중과 사용자가 정한 전체 주식 목표 비교
- 판단 당시 근거와 모델 버전의 append-only 기록
- 기록 이후 1·3·6개월 가격 경로 복기와 원장 무결성 검증
- 장 마감 후 가격 수집과 상태 계산

HERD State는 가격 확장, 추세, 상대강도와 참여를 이용해 `Flee`부터 `Rush`까지
시장·군중 상태를 표현합니다. 상태가 높다는 이유만으로 매도하거나 낮다는
이유만으로 매수하지 않습니다.

| 점수 | 상태 | 의미 |
| --- | --- | --- |
| 0–15 | Flee | 이탈 |
| 16–40 | Scatter | 분산 |
| 41–59 | Calm | 중립 |
| 60–74 | Drift | 밀집 시작 |
| 75–100 | Rush | 밀집 |

## 현재 경계

- 종목 추천, 단기 가격 예측과 자동 주문을 제공하지 않습니다.
- 검증되지 않은 연구 결과를 운영 매수·익절 신호로 표시하지 않습니다.
- 현재 ticker를 과거 SEC 사건에 소급하거나 미래 정보를 백테스트에 사용하지
  않습니다.
- 행동 후보는 사전등록, point-in-time 데이터, 독립 OOS, 거래비용과
  Buy & Hold 비교를 통과해야 합니다.
- 행동 근거가 없으면 서비스는 정직하게 `HOLD·0%`를 유지합니다.

최신 coverage, 연구 판정과 다음 구현 단계는 [현재 상태](docs/CURRENT_STATE.md)를
참고하세요.

## 기술 스택

- Frontend: React 18, Vite 6, Vitest
- Backend: Java 17, Spring Boot 3.5, JPA, Flyway
- Data: Python 3.12, pandas, APScheduler
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

### 1. 환경 설정

```bash
cp .env.example .env
```

`.env`에 데이터베이스 접속 정보와 필요한 API 설정을 입력합니다.

### 2. 데이터 엔진 준비

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

예약 수집까지 함께 실행하려면:

```bash
./scripts/start-local.sh --with-scheduler
```

로컬 자동 실행은 `./scripts/install-launchd.sh`로 등록할 수 있습니다. 화면의
데이터 상태 패널에서 가격·일별 상태·주간 상태의 기준일과 스케줄러 heartbeat를
각각 확인할 수 있습니다.

## 검증

일상적인 변경은 핵심 제품·권한·연구 경계를 빠르게 확인합니다.

```bash
./scripts/verify-fast.sh
```

배포 전이나 여러 영역을 수정한 뒤에는 전체 검증을 실행합니다.

```bash
./scripts/verify.sh
```

현재 기계 판독 상태만 확인하려면:

```bash
./scripts/audit-current-state.sh
```

## 프로젝트 구조

```text
backend/    Spring Boot API와 운영 권한 게이트
data/       데이터 수집, PIT 원장, 연구와 스케줄러
frontend/   React 웹 앱
docs/       목적, 현재 상태, 계약과 역사 기록
scripts/    실행, 검증, 수집과 운영 도구
```

문서는 다음 순서로 읽으면 됩니다.

1. [장기 운용 판단 체계](docs/HERD_LONG_TERM_OPERATING_SYSTEM.md)
2. [현재 상태](docs/CURRENT_STATE.md)
3. [제품 범위](docs/PRODUCT_SCOPE.md)
4. [채택 정책](docs/HERD_ADOPTION_POLICY.md)
5. [코드 구조](docs/ARCHITECTURE.md)

과거 연구 판정과 상세 재현 계약은 [문서 안내](docs/README.md)에서 분리해
관리합니다.

## 한계

- 증권사 계좌와 연동되지 않아 포트폴리오는 직접 입력해야 합니다.
- 현재 채택된 매수·익절 방향 모델은 없습니다.
- 일부 기업·기대·정보 데이터는 coverage가 제한되며 `NO_VIEW`가 정상 결과일
  수 있습니다.
- 과거 구성 종목, 상장폐지와 기업행위 식별은 계속 보강 중입니다.
- 로컬 컴퓨터가 꺼져 있으면 예약 수집이 중단됩니다.

## License

MIT

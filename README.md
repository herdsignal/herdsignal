# HerdSignal

> 미국 주식 장기투자자를 위한 데이터 기반 타이밍 도구

HerdSignal은 보유하거나 관심 있는 종목에서 군중이 흩어지고 밀집되는 상태를
0~100점으로 보여주는 장기투자 관찰 도구입니다.

주가를 예측하거나 정답을 알려주는 서비스가 아니라, 여러 지표를 한 화면에 모아
감정적인 매매를 줄이고 판단 근거를 기록하는 것을 목표로 만들었습니다.

> 현재 검증된 매수·익절 모델은 없습니다. 기본 사용자 출력은 `HOLD·0%`이며,
> 행동 권고가 아니라 상태 관찰과 사용자 판단 기록만 제공합니다.

## 주요 기능

- **Dashboard**: 포트폴리오 현황과 S&P 500 군중 상태 확인
- **Watchlist**: 관심 종목의 상태 변화와 밀집도 관찰
- **Stock Detail**: State S1 점수, 전환, 가족 점수와 과거 흐름 확인
- **Search**: 티커와 회사명 검색, 포트폴리오·관심 종목 추가
- **Journal**: 매수·보유·익절 판단과 당시 근거 기록
- **HERD Lab**: 모델 상태와 백테스트 결과, 검증 한계 공개
- **판단 기록**: 사용자가 직접 내린 매수·보유·익절 판단과 당시 상태 저장

## HERD Index

현재 기본 모델인 HERD State S1은 가격 확장, 추세 위치, 시장·섹터 대비
상대 위치, 동종 기업 참여를 각각 과거 흐름과 비교해 군중의 이탈과 밀집
정도를 0~100점으로 표현합니다. 하방 위험은 점수에 섞지 않고 별도 맥락으로
보존합니다.

| 점수   | 단계    | 해석        |
| ------ | ------- | ----------- |
| 0~15   | Flee    | 군중 이탈   |
| 16~40  | Scatter | 군중 분산   |
| 41~59  | Calm    | 균형        |
| 60~74  | Drift   | 밀집 시작   |
| 75~100 | Rush    | 군중 밀집   |

`Herd Flow`는 이 다섯 단계를 점의 움직임으로 시각화합니다. Flee에서는 점들이 넓게
흩어지고 Rush로 갈수록 한곳에 밀집되어, 점수의 의미를 숫자보다 직관적으로 확인할 수 있습니다.

## 모델 상태

HerdSignal은 상태 점수와 행동 모델을 구분합니다.

- **HERD State S1**: 현재 기본 화면의 관찰 상태
- **HERD Transition S1**: 상태 변화 관찰
- **HERD v4**: HERD Lab에 격리된 레거시 상태 기준
- **HERD v6.1 Action Layer**: 채택되지 않은 레거시 연구 기준
- **개인 MVP**: `STATE_OBSERVATION_MVP_READY`
- **행동 모델**: `NO_ADOPTABLE_ACTION_CANDIDATE`

가격·추세·상대강도·위험·기업 상태 가설을 독립 OOS로 검증했지만 현재까지
운영 가능한 익절·추가매수 방향 증거는 0개입니다. State S1과 Transition
S1은 관찰용으로 사용할 수 있지만, 5% 익절·재진입 완결 사이클은 고정
OOS 게이트에서 탈락했습니다. Blind holdout은 열지 않았고 행동 비율도
활성화하지 않았습니다.

검증 과정에서는 다음 항목을 함께 확인합니다.

- 기존 보유자, 신규 진입자, 정기 적립식, 목표 비중형 시나리오
- BUY·SELL 이후 1·3·6개월 성과와 시장 국면별 적중률
- 파라미터 선택 안정성, CSCV/PBO, Deflated Sharpe Ratio
- 거래 수수료, 슬리피지, 다음 거래일 시가 체결
- SEC PIT 가이던스 원문 정확도와 수정쌍 커버리지

연구 정의, 채택 기준, 최신 결과와 재현 규칙은 다음 문서에 정리했습니다.

- [모델 헌장](docs/HERD_MODEL_CHARTER.md)
- [채택 정책](docs/HERD_ADOPTION_POLICY.md)
- [최신 연구 현황](docs/HERD_RESEARCH_STATUS.md)
- [데이터 스냅샷·Walk-forward 계약](docs/HERD_REPRODUCIBLE_RESEARCH.md)
- [코드 구조와 변경 원칙](docs/ARCHITECTURE.md)

## 기술 스택

| 영역     | 기술                                                |
| -------- | --------------------------------------------------- |
| Frontend | React 18, Vite 6, Recharts, Axios                   |
| Backend  | Java 17, Spring Boot 3, Spring Data JPA, Gradle     |
| Data     | Python 3.12, pandas, yfinance, Finnhub, APScheduler |
| Database | MariaDB                                             |

## 구조

```text
yfinance / Finnhub
        │
        ▼
Python Data Engine ── 수집·지표 계산·스케줄링
        │
        ▼
MariaDB
        │
        ▼
Spring Boot API
        │
        ▼
React Web App
```

- Python은 주가 수집, HERD 계산과 정기 작업을 담당합니다.
- Spring Boot는 저장된 데이터와 포트폴리오 기능을 REST API로 제공합니다.
- React는 Dashboard, Watchlist와 종목 상세 화면을 구성합니다.

## 로컬 실행

### 준비물

- Python 3.12
- Java 17 이상
- Node.js 18 이상
- MariaDB 10 이상

전체 변경 사항은 아래 한 명령으로 백엔드·프론트엔드·데이터 엔진까지 검증할 수 있습니다.

```bash
./scripts/verify.sh
```

### 1. 환경변수

```bash
cp .env.example .env
```

`.env`에 MariaDB 접속 정보와 필요한 API 키를 입력합니다. 실제 키가 들어간 `.env`는
Git에 커밋하지 않습니다.

Google 로그인을 사용할 때는 Google Cloud에서 OAuth 웹 클라이언트를 만들고 승인된
리디렉션 URI에 아래 주소를 등록합니다.

```text
http://localhost:8080/login/oauth2/code/google
```

이후 `.env`에 값을 입력합니다.

```env
AUTH_ENABLED=true
GOOGLE_CLIENT_ID=발급받은_클라이언트_ID
GOOGLE_CLIENT_SECRET=발급받은_클라이언트_보안키
FRONTEND_URL=http://localhost:5173
HERDSIGNAL_OWNER_EMAIL=내_구글_이메일
```

`HERDSIGNAL_OWNER_EMAIL`과 로그인한 Google 이메일이 같으면 기존 `local` 포트폴리오와
관심종목, 투자 기록을 첫 로그인 때 해당 계정에 한 번 연결합니다.

로그인 세션은 MariaDB에 저장되어 백엔드를 재시작해도 유지됩니다. 기본값은 마지막 사용 후
30일 만료, 브라우저 쿠키 최대 180일이며 배포 환경에서는 `SESSION_COOKIE_SECURE=true`로
설정해야 합니다.

### 2. 데이터베이스

```sql
CREATE DATABASE herdsignal CHARACTER SET utf8mb4;
CREATE USER 'herdsignal'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON herdsignal.* TO 'herdsignal'@'localhost';
```

테이블은 백엔드 시작 시 Flyway가 자동으로 생성하고 변경 이력을 관리합니다. 기존 DB는
첫 실행 때 현재 스키마를 기준으로 등록되므로 데이터가 삭제되지 않습니다.

### 3. 데이터 엔진

```bash
cd data
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
cd ..

./scripts/run-data.sh setup_default_tickers.py
./scripts/run-scheduler-once.sh  # 즉시 1회 갱신
./scripts/run-scheduler.sh       # 매일 예약 실행하는 데몬
```

### 4. 백엔드

```bash
./scripts/run-backend.sh
```

백엔드 API는 `http://localhost:8080`에서 실행됩니다.

### 5. 프론트엔드

```bash
cd frontend
npm install
cd ..

./scripts/run-frontend.sh
```

웹 서비스는 `http://localhost:5173`에서 확인할 수 있습니다.

백엔드와 프론트엔드를 한 터미널에서 함께 실행하려면 다음 명령을 사용합니다.

```bash
./scripts/start-local.sh
```

맥이 켜져 있는 동안 예약 스케줄러까지 계속 실행하려면 다음 옵션을 사용합니다.

```bash
./scripts/start-local.sh --with-scheduler
```

스케줄러는 기본적으로 미국 동부시간 장 마감 후 실행됩니다. 맥이 종료되거나 절전 상태이면
예약 작업도 멈추므로, 필요한 날 직접 갱신하려면 `./scripts/run-scheduler-once.sh`를 실행합니다.
대시보드에서는 최신 가격일, HERD 기준일, 마지막 실행 결과와 실패 종목을 확인할 수 있습니다.

운영 상태와 DB 백업은 아래 명령으로 확인합니다.

```bash
./scripts/check-health.sh
./scripts/smoke-local.sh
./scripts/audit-scheduler-run.sh
./scripts/backup-db.sh
./scripts/verify-backup.sh backups/herdsignal-YYYYMMDD-HHMMSS.sql.gz
```

`audit-scheduler-run.sh`는 최신 실행의 성공·실패 수, 고정 reference universe,
State S1 번들 생성 시각과 DB 저장 완결성을 함께 검사합니다. 실행 중이면
`RUNNING`, 모든 조건을 통과한 완료 실행만 `PASS`를 반환합니다. 모델의 최소
가격 이력을 채우지 못한 신규 상장 종목은 임계값을 완화하지 않고 `skipped`로
분리하며, 실제 수집·저장 오류와 혼동하지 않습니다.

백업은 압축 후 체크섬을 함께 만들며 기본 14일 보관합니다. 보관 기간과 경로는 `.env`의
`BACKUP_RETENTION_DAYS`, `BACKUP_DIR`로 바꿀 수 있습니다.

`ALERT_WEBHOOK_URL`을 설정하면 스케줄러 실패·부분 실패를 Slack 또는 Discord 웹훅으로
받을 수 있습니다. 성공 알림은 기본적으로 보내지 않습니다.

## 테스트

```bash
# Python
data/.venv/bin/python -m pytest -q

# Backend
(cd backend && ./gradlew test)

# Frontend
(cd frontend && npm run lint)
(cd frontend && npm test -- --run)
(cd frontend && npm run build)
(cd frontend && npm run test:visual)
```

로컬 연구 원문·보고서·생성 캐시의 사용량은 파일을 삭제하지 않는 읽기 전용 감사로
확인할 수 있습니다.

```bash
./scripts/audit-storage.sh
```

Python 테스트는 기본적으로 로컬 불변 SEC·FINRA 원문과 가격 스냅샷까지 검사하는
`full` 프로필입니다. GitHub Actions와 같은 깨끗한 체크아웃에서는 Git에 추적된
파일만 사용하는 프로필을 실행합니다.

```bash
HERD_TEST_PROFILE=repository data/.venv/bin/python -m pytest -q
```

제외되는 테스트 모듈과 이유는
[`data/tests/test_profiles.json`](data/tests/test_profiles.json)에 명시합니다.
로컬 원문이 있는 개발 환경에서는 `./scripts/verify.sh`가 계속 전체 프로필을
검증합니다.

## 주요 API

| Method | URL                                     | 설명                       |
| ------ | --------------------------------------- | -------------------------- |
| GET    | `/api/observations/{ticker}`             | 최신 State S1 관찰값       |
| GET    | `/api/observations/{ticker}/history`     | State S1 관찰 히스토리     |
| GET    | `/api/observations?tickers=...`           | State S1 일괄 조회         |
| GET    | `/api/stocks/{ticker}/herd`              | 레거시 v4 호환 조회        |
| POST   | `/api/stocks/{ticker}/herd/refresh`     | 종목 데이터 갱신           |
| GET    | `/api/stocks/{ticker}/herd/history`     | HERD 점수 히스토리         |
| GET    | `/api/stocks/{ticker}/herd/reliability` | 과거 신호 신뢰도           |
| GET    | `/api/stocks/search?q=apple`            | 종목 검색                  |
| GET    | `/api/portfolio`                        | 포트폴리오 조회            |
| GET    | `/api/portfolio/summary`                | 포트폴리오 요약            |
| GET    | `/api/watchlist`                        | 관심 종목 조회             |
| GET    | `/api/journal`                          | 판단 기록 조회             |
| GET    | `/api/model/validation`                 | 최신 전체 검증 리포트 요약  |
| GET    | `/api/system/data-status`               | 스케줄러·데이터 신선도 상태 |
| GET    | `/api/investor-profile`                 | 개인 행동 기준 조회         |
| PUT    | `/api/investor-profile`                 | 개인 행동 기준 수정         |
| POST   | `/api/journal`                          | 판단 기록 저장             |
| GET    | `/api/auth/me`                          | 현재 로그인 사용자          |
| POST   | `/api/auth/logout`                      | 로그아웃                    |

## 현재 한계

- Google 로그인은 지원하지만 계정 연결·탈퇴 같은 회원 관리 기능은 아직 없습니다.
- 포트폴리오는 직접 입력해야 하며 증권사 계좌와 연동되지 않습니다.
- 차세대 HERD 후보는 Buy & Hold 초과 기준을 통과하지 못한 연구 단계입니다.
- 사용자 행동은 승인된 별도 모델이 생기기 전까지 항상 `HOLD·0%`입니다.
- 과거 EPS는 신뢰할 수 있는 실제 발표일 데이터가 없어 백테스트에서 중립 처리합니다.
- 과거 편출·합병·상장폐지 종목 데이터가 부족해 생존자 편향이 남아 있습니다.
- SEC 가이던스 구조 파서 V7은 새 7,171개 공시에서 잠근 독립 표본 80건·24개 기업 기준 정확도 85.0%, Wilson 95% 하한 75.59%로 90% 게이트를 통과하지 못했습니다. 수정쌍과 방향성 연구는 차단 상태입니다.

## 프로젝트에서 중요하게 생각한 것

- 결과가 좋아 보이는 백테스트보다 미래 데이터 누수를 막는 것
- 평균 수익률 하나보다 실패한 종목과 시장 구간을 함께 공개하는 것
- 모델이 확실하지 않을 때 연구 상태라고 명확히 표시하는 것
- 복잡한 금융 지표를 실제로 이해할 수 있는 화면과 문장으로 바꾸는 것

## License

MIT

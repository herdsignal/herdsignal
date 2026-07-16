# HerdSignal

> 미국 주식 장기투자자를 위한 데이터 기반 타이밍 도구

HerdSignal은 보유하거나 관심 있는 종목의 시장 과열도를 0~100점으로 보여주고,
장기투자자가 **추가매수·보유·일부 익절** 중 어떤 행동을 검토할지 정리해 주는 서비스입니다.

주가를 예측하거나 정답을 알려주는 서비스가 아니라, 여러 지표를 한 화면에 모아
감정적인 매매를 줄이고 판단 근거를 기록하는 것을 목표로 만들었습니다.

> 현재 개인 프로젝트이자 연구용 서비스입니다. 화면의 행동 정보는 투자 권유가 아닙니다.

## 주요 기능

- **Dashboard**: 포트폴리오 현황, SPY Herd Flow, 행동 대기열과 리스크 확인
- **Watchlist**: 관심 종목의 추가매수·익절 우선순위 비교
- **Stock Detail**: HERD 점수, 행동 근거, 신뢰도, 과거 흐름과 재무정보 확인
- **Search**: 티커와 회사명 검색, 포트폴리오·관심 종목 추가
- **Journal**: 매수·보유·익절 판단과 당시 근거 기록
- **HERD Lab**: 모델 상태와 백테스트 결과, 검증 한계 공개
- **개인 행동 기준**: 기존 보유·신규 진입·적립식·목표 비중에 맞춰 행동 비율 조정

## HERD Index

HERD Index는 RSI, 장기 이동평균, 연중 가격 위치 등을 종목의 과거 흐름과 비교해
군중의 이탈과 밀집 정도를 0~100점으로 표현합니다.

| 점수   | 단계    | 해석        | 검토 행동              |
| ------ | ------- | ----------- | ---------------------- |
| 0~15   | Flee    | 군중 이탈   | 적극적인 추가매수 검토 |
| 15~40  | Scatter | 군중 흩어짐 | 분할매수 검토          |
| 40~60  | Calm    | 균형 구간   | 현재 비중 유지         |
| 60~75  | Drift   | 군중 쏠림   | 일부 익절 검토         |
| 75~100 | Rush    | 군중 밀집   | 적극적인 익절 검토     |

`Herd Flow`는 이 다섯 단계를 점의 움직임으로 시각화합니다. Flee에서는 점들이 넓게
흩어지고 Rush로 갈수록 한곳에 밀집되어, 점수의 의미를 숫자보다 직관적으로 확인할 수 있습니다.

## 모델 상태

HerdSignal은 상태 점수와 행동 모델을 구분합니다.

- **HERD v4**: 현재 서비스에서 사용하는 종목 상태 점수
- **HERD v6.1 Action Layer**: 점수를 행동 비율로 바꾸는 연구 모델
- **현재 상태**: `RESEARCH_VALIDATION`

v6.1은 55종목과 Walk-forward OOS 검증을 진행했지만 아직 운영 채택 기준에는 미달했습니다.
따라서 화면에서도 확정 매매 추천이 아닌 참고용 행동 정보로 표시합니다.

검증 과정에서는 다음 항목을 함께 확인합니다.

- 기존 보유자, 신규 진입자, 정기 적립식, 목표 비중형 시나리오
- BUY·SELL 이후 1·3·6개월 성과와 시장 국면별 적중률
- 파라미터 선택 안정성, CSCV/PBO, Deflated Sharpe Ratio
- 거래 수수료, 슬리피지, 다음 거래일 시가 체결
- Healthy Rush와 에너지·소재 비율 보정 연구 후보

상세 결과는 `data/reports/validation_v2/`에 저장됩니다.

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
.venv/bin/pip install -r requirements.txt
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
./scripts/backup-db.sh
./scripts/verify-backup.sh backups/herdsignal-YYYYMMDD-HHMMSS.sql.gz
```

백업은 압축 후 체크섬을 함께 만들며 기본 14일 보관합니다. 보관 기간과 경로는 `.env`의
`BACKUP_RETENTION_DAYS`, `BACKUP_DIR`로 바꿀 수 있습니다.

`ALERT_WEBHOOK_URL`을 설정하면 스케줄러 실패·부분 실패를 Slack 또는 Discord 웹훅으로
받을 수 있습니다. 성공 알림은 기본적으로 보내지 않습니다.

## 테스트

```bash
# Python
cd data
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'

# Backend
cd ../backend
./gradlew test

# Frontend
cd ../frontend
npm run lint
npm test -- --run
npm run build
```

## 주요 API

| Method | URL                                     | 설명                       |
| ------ | --------------------------------------- | -------------------------- |
| GET    | `/api/stocks/{ticker}/herd`             | 종목 HERD 점수와 행동 정보 |
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
- HERD v6.1은 연구 검증 중이며 실제 수익을 보장하지 않습니다.
- 과거 EPS는 신뢰할 수 있는 실제 발표일 데이터가 없어 백테스트에서 중립 처리합니다.
- 과거 편출·합병·상장폐지 종목 데이터가 부족해 생존자 편향이 남아 있습니다.
- 목표 비중 일부는 브라우저 `localStorage`에 저장되며 DB 동기화가 아직 없습니다.

## 프로젝트에서 중요하게 생각한 것

- 결과가 좋아 보이는 백테스트보다 미래 데이터 누수를 막는 것
- 평균 수익률 하나보다 실패한 종목과 시장 구간을 함께 공개하는 것
- 모델이 확실하지 않을 때 연구 상태라고 명확히 표시하는 것
- 복잡한 금융 지표를 실제로 이해할 수 있는 화면과 문장으로 바꾸는 것

## License

MIT

# HerdSignal 프로젝트 지침

최종 업데이트: 2026-07-27

## 제품 목적

HerdSignal은 미국 주식을 장기 보유하는 사용자가 군중의 분산·밀집 상태와
그 변화를 관찰하고 자신의 판단을 기록하는 개인 투자 도구다.

- 기본 모델은 `HERD State S1`과 `Transition S1`이다.
- HERD는 0~100의 순서형 상태이며 Flee → Scatter → Calm → Drift → Rush로 표현한다.
- 낮은 점수는 자동 매수, 높은 점수는 자동 매도를 의미하지 않는다.
- 검증된 행동 모델이 생기기 전 사용자 출력은 `HOLD·0%`다.
- v4와 v6.1은 레거시 비교·재현 자료이며 새 모델의 운영 근거가 아니다.

제품·모델 경계는 `docs/HERD_MODEL_CHARTER.md`, 채택 조건은
`docs/HERD_ADOPTION_POLICY.md`, 최신 연구 판정은
`docs/HERD_RESEARCH_STATUS.md`를 따른다.

## 저장소 구조

```text
data/       Python 수집·상태 계산·연구·스케줄러
backend/    Spring Boot API·인증·사용자 데이터·운영 경계
frontend/   React 대시보드·관찰 목록·상세·연구 화면
docs/       현재 계약과 재현 가능한 연구 기록
scripts/    루트 .env를 사용하는 실행·검증 스크립트
```

기본 데이터 흐름은 `외부 원천 → Python → MariaDB → Spring Boot → React`다.
Python은 계산과 저장, backend는 API와 사용자 경계, frontend는 표현을 담당한다.
루트 `.env`가 유일한 로컬 환경변수 기준이며 비밀값은 커밋하지 않는다.

## 현재 제품 구조

- `/app`: SPY Herd Flow, 통합 종목 검색, 선택형 자산 패널, 보유 현황
- `/watchlist`: 관심 종목과 상태 변화 관찰
- `/stock/:ticker`: State S1·과거 흐름·근거·판단 기록
- `/changes`: 새 상태 전환 확인
- `/herd-lab`: 모델 상태와 검증 한계
- `/settings`, `/history`, `/journal`: 사용자 설정과 기록
- `/portfolio`, `/search`: 이전 주소 호환용 `/app` 리다이렉트

별도 시장 홈과 검색 페이지는 없다. 대시보드가 핵심 진입점이다.

## 변경 원칙

1. 문서보다 실제 코드와 테스트를 먼저 확인한다.
2. 상태 관찰과 행동 권고를 혼합하지 않는다.
3. 연구 후보는 사전등록·OOS·채택 게이트를 통과하기 전 운영에 연결하지 않는다.
4. 누락 데이터와 승인 실패는 통과가 아니라 차단으로 처리한다.
5. Controller·Service·Repository, 화면·훅·모델의 역할을 분리한다.
6. 공통 로직은 재사용하되 단순한 코드에 불필요한 추상화를 추가하지 않는다.
7. 기존 사용자 변경과 재현용 `*_vN.py`·고정 산출물을 임의 삭제하지 않는다.
8. 설명 주석은 이유와 경계에 집중하고 코드 내용을 반복하지 않는다.
9. 작업 범위의 테스트, 정적 검사, 빌드와 참조 검사를 끝낸 뒤 완료로 판단한다.

## 문서 권위

- 공개 실행·기능 안내: `README.md`
- 코드 구조: `docs/ARCHITECTURE.md`
- 문서 분류와 읽는 순서: `docs/README.md`
- 모델 정의: `docs/HERD_MODEL_CHARTER.md`
- 채택 기준: `docs/HERD_ADOPTION_POLICY.md`
- 최신 연구 판정: `docs/HERD_RESEARCH_STATUS.md` 상단
- 재현·PIT 계약: `docs/HERD_REPRODUCIBLE_RESEARCH.md`,
  `docs/HERD_POINT_IN_TIME_DATA.md`

`HERD_RESEARCH_STATUS.md`의 날짜별 하단 항목과 버전별 연구 스크립트는
과거 판단을 재현하기 위한 기록이다. 최신 운영 상태로 해석하지 않는다.

## 검증

전체 검증은 루트에서 다음 명령을 우선 사용한다.

```bash
./scripts/verify-all.sh
```

부분 작업은 해당 폴더의 `CLAUDE.md`와 테스트 명령을 따른다. 외부 API·DB가
필요한 런타임 점검과 순수 단위·회귀 테스트는 구분해 결과를 보고한다.

## 커밋

사용자가 커밋을 요청한 경우에만 수행한다. 기능적으로 완결된 단위마다
`feat`, `fix`, `refactor`, `test`, `docs`, `chore` 중 하나를 사용해
간결한 한국어 메시지를 작성한다. 푸시는 사용자의 명시적 요청 없이 하지 않는다.

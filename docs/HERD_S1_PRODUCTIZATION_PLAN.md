# HERD S1 제품화 계획

기준일: 2026-07-25

목표는 연구 산출물 `HERD_STATE_S1`과 `HERD_TRANSITION_S1`을 개인용
HerdSignal의 기본 관찰 모델로 연결하는 것이다. 이 작업은 매수·익절 모델을
승격하지 않는다. 모든 단계에서 운영 행동은 `HOLD`, 비율은 `0%`다.

## 구현 상태

| 단계 | 상태 | 구현 기준 |
|---|---|---|
| 1. 정기 관찰 번들 | 완료 | `6fd65b1` |
| 2. 관찰 스냅샷 저장 | 완료 | `f9746fe` |
| 3. S1 조회 API | 완료 | `9a66bd0` |
| 4. SPY 홈과 종목 상세 | 완료 | v4 fallback 제거·S1 이력·화면 회귀 |
| 5. 레거시 모델 격리 | 완료 | 기본 화면 S1 일괄 조회·Lab 비교군 이동 |
| 6. 행동 경계 통일 | 완료 | 사용자 출력·저널·캐시를 HOLD·0%로 fail-closed |
| 7. 승격 포트와 최종 회귀 | 완료 | 해시·holdout·사람 승인·감사 저장 포트 |

## 1. 정기 관찰 번들

- 고정된 439개 종목을 참여도 peer universe로 사용한다.
- 포트폴리오 구성에 따라 참여도 기준이 달라지지 않게 출력 대상과 peer
  universe를 분리한다.
- 개별주는 네 가족 점수를 동일 비중으로 계산한다.
- SPY 화면은 SPY를 자기 자신과 상대 비교하지 않는다. 고정 종목군의
  가족별 중앙값을 집계한 `S&P 500 군중 상태`로 제공한다.
- 가격 수집 일부 실패 시 기준 종목 coverage 90% 미만이면 번들을 생성하지
  않는다. 미지원 종목은 SPY로 대체하지 않고 사유를 남긴다.
- JSON은 임시 파일에 쓴 뒤 원자적으로 교체한다.

완료 조건:

- 미래 수익 입력 없음
- 개별주와 시장 집계의 scope 구분
- `HOLD·0%` 경계 테스트
- 스케줄러 일부 실패와 S1 실패가 실행 이력에 반영됨

## 2. 관찰 스냅샷 저장

- `herd_observations` 테이블을 별도로 만든다. v4 `herd_scores`를 덮어쓰지
  않는다.
- 기본키는 `ticker + model_version + observed_date`다.
- 상태·전환·네 가족·위험 맥락·scope·생성시각·원자료 기준일을 저장한다.
- Python ORM과 Flyway 스키마를 같은 계약 테스트로 고정한다.
- 한 번들의 UPSERT는 단일 트랜잭션이며 일부 행만 저장하지 않는다.

완료 조건:

- 재실행 멱등성
- v4 테이블 무변경
- 모델 버전과 기준일 누락 불가
- 시장 집계와 개별주 구분

## 3. S1 조회 API

- `/api/observations/{ticker}`와 history API를 추가한다.
- 응답에 상태 점수, 단계, 전환, 가족 점수, 기준일, scope와 제한을
  포함한다.
- v4 응답과 DTO를 섞지 않는다.
- 데이터가 없거나 오래됐으면 명시적인 unavailable/stale 상태를 반환한다.
- 인증·티커 검증·조회 상한을 기존 API 정책과 맞춘다.

완료 조건:

- repository/service/controller 테스트
- 최신·히스토리 정렬 보장
- 행동 필드가 항상 `HOLD·0%`
- v4 API 하위 호환

## 4. SPY 홈과 종목 상세

- 메인 SPY는 `S&P 500 군중 상태`임을 화면 구조로 표시한다.
- 종목 상세는 S1이 있으면 S1을 기본 관찰값으로 사용한다.
- S1이 없으면 v4 값을 S1처럼 표시하지 않고 `관찰값 준비 중`으로 둔다.
- 상태, 전환, 네 가족, 기준일만 우선 노출하고 행동 문구는 만들지 않는다.
- 기존 HerdDots와 SpectrumBar는 점수 표현 컴포넌트로 재사용한다.

완료 조건:

- loading/error/unavailable/stale 상태 테스트
- 데스크톱·모바일 화면 회귀
- SPY 집계와 개별주 scope 오표시 없음

## 5. 레거시 모델 격리

- v4와 v6.1은 메인 화면에서 제거하고 HERD Lab의 비교·연구 기록으로
  이동한다.
- v4는 `LEGACY_STATE_BASELINE`, v6.1은
  `LEGACY_RESEARCH_ACTION_BASELINE`으로만 표시한다.
- 레거시 계산·DB는 히스토리 호환을 위해 삭제하지 않는다.
- 프론트 정렬·알림·카드가 레거시 signal을 운영 행동으로 해석하지 못하게
  한다.

완료 조건:

- 메인 화면에 v6.1 행동 비율 없음
- Lab에서 버전·상태·탈락 이유 확인 가능
- 레거시 API와 기존 기록은 보존

구현 결과:

- S1 API가 회사 메타데이터와 최대 100종목 일괄 조회를 제공한다.
- 포트폴리오·관심종목·검색·알림·종목 상세는 v4 조회 없이 S1을 사용한다.
- 종목 상세의 v6.1 Action Layer, v4 지표 분해, v4 신뢰도 UI를 제거했다.
- HERD Lab에 `LEGACY_STATE_BASELINE`과
  `LEGACY_RESEARCH_ACTION_BASELINE`의 상태·제외 이유를 표시한다.
- v4/v6.1 API와 저장 데이터는 과거 기록 재현을 위해 유지한다.

## 6. 행동 경계 통일

- 공개 응답의 `operationalAction=HOLD`,
  `operationalActionRatio=0`을 단일 정책으로 강제한다.
- 연구 비율은 기본 사용자 API에서 제거하거나 Lab 전용 응답으로 격리한다.
- 알림·대기열·Journal 기본값이 BUY/SELL로 승격되지 않게 한다.
- 환경변수만으로 행동을 열 수 없고, 고정 보고서·blind holdout·사람 승인을
  모두 요구하는 기존 승격 경계를 유지한다.

완료 조건:

- 백엔드·프론트 계약 테스트
- `live-enabled=true` 단독 설정으로 행동 활성화 불가
- 빈 값·레거시 signal·캐시 응답에서도 HOLD 유지

구현 결과:

- `UserActionBoundary`를 사용자 행동 출력의 단일 fail-closed 정책으로
  추가했다. S1 관찰 API, 레거시 HERD 응답, 판단 저널이 모두 이 경계의
  `HOLD·0%`를 사용한다.
- v6.1의 연구 비율·국면·행동 근거는 기본 HERD 응답에서 더 이상 노출하지
  않는다. 모델 버전과 연구 상태만 호환 정보로 남긴다.
- 사용자가 직접 남긴 BUY/HOLD/SELL 기록은 실제 판단 이력으로 보존하되,
  그 기록에 붙는 모델 신호와 비율은 저장·조회 모두 `HOLD·0%`로 정규화한다.
- 프론트는 `actionAuthorized=true`, 양수의 승인 비율, 허용된 행동 코드가
  모두 있을 때만 행동을 해석한다. 오래된 캐시와 레거시 signal은
  `HOLD`로 닫힌다.
- 기본 목록을 `매수 대기열`에서 `관찰 대기열`로 바꾸고, 낮거나 높은
  HERD 구간을 매수·익절 후보처럼 표현하던 문구를 상태 관찰 언어로
  교체했다.
- `live-enabled=true`만 켠 경우, blind holdout이 통과하지 않으면 행동
  비율이 0%인지 계약 테스트로 고정했다.

## 7. 승격 포트와 최종 회귀

- 향후 통과한 방향 증거는 `OperationalPromotionGate` 뒤의 별도 포트로만
  연결한다.
- S1 상태 계산과 개인 행동 번역은 서로 import하지 않는다.
- 연구 산출물 해시·모델 버전·승인 이력을 저장한다.
- Python 전체, Backend Gradle, Frontend lint/test/build/visual 회귀를
  수행한다.
- 문서·API 목록·스토리지 감사를 최신화하고 중복·우회 경로를 제거한다.

완료 조건:

- 전체 회귀 통과
- Git 작업 트리 정리
- 운영 범위와 남은 한계를 최종 리뷰에 기록

구현 결과:

- `OperationalActionPromotionPort`와 sealed
  `GrantedOperationalAction`을 추가했다. 일반 서비스는 승인 권한 객체를
  직접 만들 수 없다.
- 승인 파일은 candidate ID뿐 아니라 model version, 연구 산출물 SHA-256,
  방향 증거, 완결 사이클, survivorship-safe, 단일 Blind holdout과 사람
  승인까지 검증한다.
- 승인·거절 요청은 `model_promotion_audits`에 모델·산출물·승인 파일
  해시와 사유를 저장한다. 감사 저장 실패 시에도 권한을 발급하지 않는다.
- 허용 행동은 `ADD`·`REDUCE`, 1회 최대 5%로 제한했다. 레거시
  `ActionDecisionService`의 운영 환경변수 경로는 제거하고 연구 재현
  전용으로 고정했다.
- 현재 S1 API와 기본 화면은 승격 포트를 호출하지 않는다. 실제 사용자
  출력은 계속 `HOLD·0%`다.

최종 검증:

- Python 전체 `933 passed`
- Backend Gradle `117 tests` 및 Flyway V1~V6
- Frontend Vitest `56 passed`, lint, production build
- Playwright 데스크톱·모바일 화면 회귀 `6 passed`
- 로컬 연구 원문은 `data/reference` 29.6GiB로 Git 비추적 상태다.
  재현성 입력이므로 파일 수만 보고 삭제하지 않으며 스토리지 감사는
  `REVIEW` 상태를 유지한다.

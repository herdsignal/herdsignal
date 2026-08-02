# data 개발 지침

최종 업데이트: 2026-07-27

## 역할

Python 영역은 시장·SEC 공개 데이터 수집, State S1 계산, 스케줄링,
포트폴리오 평가와 재현 가능한 모델 연구를 담당한다. 결과는 MariaDB 또는
해시가 고정된 연구 산출물로 남기며 React와 직접 통신하지 않는다.

## 현재 경계

- `HERD State S1`: 제품의 기본 관찰 상태
- `HERD Transition S1`: 상태 변화 관찰
- v4·v6.1: 레거시 비교·재현용
- 차세대 행동 후보: 없음
- 운영 행동: `HOLD·0%`
- 과거 구성 데이터: `survivorship_safe=false`
- Blind holdout: 미개방

낮은 점수나 높은 점수를 매수·익절로 직접 변환하지 않는다. 새로운 방향
증거는 사전등록, 독립 OOS, 비용·완결 사이클, 채택 정책을 모두 통과해야 한다.
새 연구의 계층과 순서는 `herd/decision_architecture_v1.json`을 따른다.
일반 경로 분류 대신 결과 확인 전에 고정한 정책의 HOLD 대비 순경제가치를
기본 표적으로 사용한다.

## 영역

```text
collectors/   가격·기업·검색 원천 수집
indicators/   운영·레거시 지표 계산
herd/         State S1, 레거시 계산, 연구 프로토콜과 버전별 실험
scheduler/    정기 수집·on-demand·실시간 평가
config/       환경변수와 DB 설정
reference/    Git 비추적 원문·고정 입력
snapshots/    불변 입력 manifest
walk_forward/ 시간 분할 계약
runtime/      운영 중 생성되는 상태·리포트
tests/        운영 및 연구 계약 회귀
```

## 운영 데이터 흐름

1. 가격과 필요한 공개 원천을 수집한다.
2. State S1과 레거시 호환 데이터를 계산한다.
3. MariaDB에 날짜·출처와 함께 저장한다.
4. Tier 1 스케줄러가 포트폴리오·관심종목·SPY를 갱신한다.
5. Tier 2 on-demand와 Tier 3 실시간 평가는 전용 runner를 통해 실행한다.

설정은 루트 `.env`만 사용한다. DB 연결은 `config/database.py`, 계산
상수는 `config/settings.py`에서 관리한다.

## 연구 원칙

- 결과를 보기 전에 가설, 입력, 시간 분할, 비용, 판정 기준을 고정한다.
- 발표·접수 시각 이후에만 기업 데이터를 사용할 수 있다.
- 같은 데이터로 임계값을 반복 조정한 결과를 독립 증거라 부르지 않는다.
- 후보가 실패하면 결과와 원인을 원장에 남기고 운영에 연결하지 않는다.
- 누락값은 통과로 간주하지 않는다.
- `*_vN.py`, 고정 JSON·CSV, 원문 해시는 재현 이력이다. 단순 중복처럼
  보여도 후속 버전이 완전히 대체한다는 증거 없이 삭제하거나 덮어쓰지 않는다.
- 현재 판정은 `herd/research_decision_v3.json`과
  `docs/HERD_RESEARCH_STATUS.md` 상단을 기준으로 한다.
- Form 8-K 2.04·2.05·2.06·4.02는 source coverage만 통과한 기업 훼손
  veto 후보다. corpus·원문 검수·독립 OOS 전에는 행동 근거로 사용하지 않는다.

상세 계약:

- 모델 목표: `docs/HERD_MODEL_CHARTER.md`
- 채택 기준: `docs/HERD_ADOPTION_POLICY.md`
- PIT 데이터: `docs/HERD_POINT_IN_TIME_DATA.md`
- 재현·fold: `docs/HERD_REPRODUCIBLE_RESEARCH.md`
- 산출물 분류: `docs/HERD_ARTIFACT_CATALOG.md`

## 레거시 호환

`calculator.py`, `saver.py`, `backtest_v4.py`,
`backtest_action_layer.py`의 v4·v6.1 로직은 기존 데이터와 비교 재현을
위해 남아 있다. 이를 현재 채택 모델이나 행동 근거로 문서화하지 않는다.
과거 백필에서 복원할 수 없는 EPS·섹터 정보는 미래 누수를 만들지 않도록
중립값을 사용한다.

## 데이터·저장 원칙

- 원천 수집 시 출처, 접수 시각, 요청 옵션과 해시를 보존한다.
- 조정 가격, 분할·배당, ticker–CIK 기간과 기업행동을 구분한다.
- 재수집 가능한 캐시와 재현성 원문을 구분한다.
- `reference/`의 대용량 원문은 Git 비추적이지만 연구 입력이므로 용량만
  보고 삭제하지 않는다.
- DB 쓰기는 트랜잭션과 idempotent UPSERT를 사용한다.
- 스키마 변경은 Flyway·backend 엔티티와 함께 검증한다.

## 코드 원칙

- 지표·수집·정책·평가 역할을 분리한다.
- 네트워크 실패에는 제한된 재시도와 명확한 실패 결과를 둔다.
- 임의 폴백으로 성공처럼 보이게 하지 않는다.
- 경로는 저장소 루트 기준으로 해석하고 현재 작업 디렉터리에 의존하지 않는다.
- 새 버전은 기존 고정 산출물을 변경하지 않고 새 파일로 생성한다.

## 검증

저장소 루트에서 실행한다.

```bash
data/.venv/bin/python -m pytest data/tests
```

연구 파이프라인 변경은 관련 단위 테스트뿐 아니라 manifest 해시,
미래정보 누수, fold 격리, fail-closed 판정을 함께 확인한다.

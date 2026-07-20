# HERD 재현 가능한 연구 계약

HERD 후보는 같은 데이터와 같은 시간 분할로 다시 실행했을 때 같은 결과가
나와야 비교 대상이 된다. 이 문서는 데이터 스냅샷과 Walk-forward 산출물의
고정 규칙이다.

## 1. 가격 데이터 스냅샷

### 목적

- 실행할 때마다 외부 API에서 달라지는 가격을 다시 받지 않는다.
- 어떤 종목, 기간, 조정 방식으로 검증했는지 파일 단위로 추적한다.
- 파일 누락이나 사후 수정을 검증 전에 차단한다.

### 저장 구조

```text
data/snapshots/<snapshot-id>/
├── manifest.json
└── prices/
    ├── AAPL.csv.gz
    └── ...
```

`manifest.json`에는 다음을 기록한다.

- 스냅샷 형식 버전과 생성 시각
- 데이터 공급자와 수집 옵션
- 유니버스 버전과 요청·완료 종목
- 종목별 행 수, 시작일, 종료일, 파일 크기, SHA-256
- 전체 manifest의 SHA-256

가격 파일은 `Date, Open, High, Low, Close, Volume` 순서의 gzip CSV로
고정한다. 날짜 오름차순, 중복 날짜 없음, 유한한 양수 OHLC, 음수가 아닌
거래량을 강제한다. 생성은 임시 디렉터리에서 완료한 뒤 한 번에 이동하며,
이미 존재하는 스냅샷은 덮어쓰지 않는다.

검증 코드는 manifest와 모든 파일의 해시를 확인한 스냅샷만 읽는다.
외부 API와 스냅샷을 한 실행에서 섞지 않는다.

## 2. 시간축 Walk-forward

### 분할 규칙

- 폴드는 시간 순서만 사용한다.
- 기본 학습 최소 길이: 4년
- 기본 테스트 길이: 1년
- 기본 이동 간격: 1년
- 학습 구간은 누적 anchored 방식이다.
- 최초 학습 구간 4년을 확보한 뒤 경계 간격을 별도로 둔다.
- 학습 말단에서 `purge_days`만큼 제거한다.
- purge 뒤에 `embargo_days`만큼 추가 간격을 둔다.
- 테스트 구간은 서로 겹치지 않는다.

`purge_days`는 학습 라벨의 미래 참조 길이 이상이어야 한다. 일별 전략
수익률 검증 기본값은 1거래일이다. 12개월 선행수익률을 학습 라벨로 쓰는
연구는 별도 실행에서 252거래일 이상으로 올려야 한다.

### 저장 구조

```text
data/walk_forward/<run-id>/
├── manifest.json
├── folds.csv
├── fold_metrics.csv
└── daily_returns.csv.gz
```

- `folds.csv`: 실제 학습·간격·테스트 경계와 관측 수
- `fold_metrics.csv`: 폴드·종목·후보별 CAGR, MDD, Sortino, Calmar,
  상승·하락 포착률, 회전율
- `daily_returns.csv.gz`: 날짜별 전략 수익률, Buy & Hold 수익률, 자산,
  노출 비중
- `manifest.json`: 입력 스냅샷 해시, 실행 설정, 후보 목록, 각 산출물 해시

산출물은 임시 디렉터리에서 작성하고 검증한 뒤 원자적으로 확정한다.
동일한 `run-id`를 덮어쓰지 않는다. 이 실행기는 holdout 기간을 임의로
정하지 않는다. Blind holdout을 잠근 뒤에는 `research_end`를 그 시작일
이전으로 지정해 연구 산출물에서 제외해야 한다.

## 3. S&P 500 구성 연구 파이프라인

구성 사건은 개별 스크립트를 수동으로 이어 실행하지 않는다. 다음 명령 하나로
공식 문서 대조, 기업 동일성, 기업행동 승계, 사건 원장, 일별 구성 재생과 잔여
차단 목록을 같은 입력 스냅샷에서 생성한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.constituent_research_pipeline \
  data/herd/constituent_research_pipeline.json \
  data/reference/point_in_time/<새로운-run-id>
```

파이프라인은 입력 파일·원문 corpus의 SHA-256을 manifest에 기록하고 모든
산출물을 임시 디렉터리에 작성한 뒤 한 번에 확정한다. 다음 조건 중 하나라도
발생하면 결과를 남기지 않는다.

- 과거에 해결한 후보가 다시 미해결 상태로 바뀜
- 검증 사건 수 감소 또는 차단 사건 수 증가
- 사건 원장과 일별 재생의 검증 사건 수 불일치
- 중복 후보, 원문 누락 또는 일별 재생 오류

기존 결과 디렉터리는 덮어쓰지 않는다. 새 증거를 추가할 때마다 새 run ID를
사용하고 직전 승인 결과를 회귀 기준으로 고정한다.

## 4. PIT 진단 스냅샷

공식 사건이 모두 해결되지 않았더라도 재생 오류가 0건이고 차단 사건이
명시적으로 격리된 실행은 `PIT_DIAGNOSTIC_V1`으로 동결할 수 있다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.pit_diagnostic_snapshot create \
  pit-diagnostic-v1-YYYYMMDD \
  data/reference/point_in_time/<pipeline-run-id> \
  --root data/reference/point_in_time
```

스냅샷은 통합 사건 원장, 차단 목록, 재생 결과와 원본 pipeline manifest를
그대로 복사하고 각 파일의 SHA-256을 기록한다. 기존 스냅샷은 덮어쓰지
않으며, 검증 명령은 파일 변조와 정책 변경을 모두 차단한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.pit_diagnostic_snapshot verify \
  data/reference/point_in_time/pit-diagnostic-v1-YYYYMMDD
```

허용 범위:

- 모델 후보의 조기 탈락
- 미해결 사건 불확실성 민감도 분석
- 연구 파이프라인 회귀 검증

금지 범위:

- 최종 모델 채택
- 운영 신호 생성
- 생존자 편향 해결 선언

2026-07-20 기준 스냅샷은 최종 구성 500종목, 재생 오류 0건이며
LIN·VTRS·SW·PSKY 네 사건을 차단 목록으로 고정한다.

## 5. PIT 불확실성 시나리오

동결 스냅샷의 모든 차단 사건은
`herd/pit_uncertainty_assumptions.csv`에서 정확히 한 번씩 다룬다.
가정은 `RESEARCH_SCENARIO_ONLY`, `promotion_allowed=false`여야 한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.pit_uncertainty_scenarios \
  data/reference/point_in_time/pit-diagnostic-v1.1-YYYYMMDD \
  data/herd/pit_uncertainty_assumptions.csv \
  data/reference/point_in_time/<scenario-run-id>
```

생성 경계:

- `CURRENT_DIAGNOSTIC`: 현재 진단 승계 포함
- `VERIFIED_ONLY`: 검증 사건만 포함
- `ASSUME_CONTINUITY`: 차단된 승계를 모두 연속으로 가정
- `CONSERVATIVE_EXCLUSION`: 사건 전후 63개 관측치를 제외하는 성과 오버레이

OOS 후보 민감도는 다음 명령으로 계산한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.pit_sensitivity_evaluation \
  data/reference/point_in_time/<scenario-run-id> \
  data/walk_forward/<run-id> \
  data/reports/pit_uncertainty_sensitivity_v1.json
```

후보 순위 변경, 초과 CAGR 부호 반전, 후보별 초과 CAGR 범위 0.50%p 초과
중 하나가 발생하면 구성 불확실성이 중요한 것으로 판정하고 원문 해결 또는
가격 coverage 확장으로 돌아간다. 모두 발생하지 않으면 기존 모델
재평가로 진행한다.

## 6. 기존 모델 재평가

실행 시점의 외부 시세를 다시 받지 않고 불변 가격 스냅샷으로 v4와
Python v6.1을 비교한다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.legacy_model_evaluation \
  --snapshot snapshots/yf-10y-20260719 \
  --output reports/legacy_model_evaluation_v2.json
```

보고서에는 가격 스냅샷 ID와 manifest SHA-256, 조정 가격 여부, 입력
coverage를 기록한다. 이 결과는 55개 현존 대형주의 가격 기반 재평가이며
전체 과거 S&P 500의 생존자 편향 해소 결과가 아니다.

## 7. 증거군 단독 스크리닝

기존 참여·추세/상대강도·위험 프록시를 같은 가격 스냅샷에서 분리해
실행한다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.evidence_family_validation \
  --snapshot snapshots/yf-10y-20260719 \
  --output reports/evidence_family_validation_v2.json
```

이 실행은 사전 고정 프록시를 빠르게 탈락시키는 진단이다. 전체 기간
결과이므로 OOS 채택 근거로 사용하지 않으며, 결과를 본 뒤 임계값을
조정하지 않는다. 통과 가설만 별도 사전 등록 후 walk-forward로 보낸다.

## 8. 판정 원칙

스냅샷과 시간 분할은 모델 성능을 본 뒤 바꾸지 않는다. 후보가 탈락해도
실행 manifest와 일별 수익률을 보존한다. 집계 결과만 저장한 과거 보고서는
참고 기록일 뿐 차세대 HERD 채택 근거로 사용하지 않는다.

## 근거

- scikit-learn `TimeSeriesSplit`: 시간 순서를 보존하고 train과 test 사이
  `gap`을 지원한다.
- López de Prado의 purged/embargoed cross-validation: 라벨 구간 중첩과
  시계열 의존성에 의한 누출을 줄인다.
- pandas gzip의 고정 `mtime`: 동일 입력 파일을 재현 가능한 바이트로
  저장할 수 있다.
- SHA-256: 파일 무결성과 실행 입력 식별에 사용한다.

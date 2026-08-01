# HERD 재현 가능한 연구 계약

HERD 후보는 같은 데이터와 같은 시간 분할로 다시 실행했을 때 같은 결과가
나와야 비교 대상이 된다. 이 문서는 데이터 스냅샷과 Walk-forward 산출물의
고정 규칙이다.

## SEC 13F 군중 맥락 계약 검증

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.sec_13f_crowding_protocol_v1
PYTHONPATH=data data/.venv/bin/pytest -q data/tests/test_sec_13f_crowding_protocol_v1.py
```

## SEC 13F 공식 원본 수집·검증

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.sec_13f_bulk_v1
PYTHONPATH=data data/.venv/bin/python -m herd.sec_13f_bulk_v1 --verify-only
PYTHONPATH=data data/.venv/bin/pytest -q data/tests/test_sec_13f_bulk_v1.py
```

원본 ZIP과 manifest는
`data/reference/sec/sec-13f-bulk-2013q2-2026m05-v1`에 로컬 보관한다.

## SEC 13F 종목 식별 원장

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.sec_13f_security_ledger_v1
PYTHONPATH=data data/.venv/bin/python -m herd.sec_13f_security_ledger_v1 --verify-only
PYTHONPATH=data data/.venv/bin/pytest -q data/tests/test_sec_13f_security_ledger_v1.py
```

공식 SEC submissions 회사명·former name과 13F issuer name을 결과 데이터
없이 연결한다. fuzzy match는 금지한다. 보통주·주식 클래스·REIT 지분만
남기고 ETF·펀드·채권·우선주·워런트는 제외한다. 같은 분기에는 고유
accession 수가 가장 많은 보통주 CUSIP를 대표 식별자로 선택한다. 충돌
CUSIP는 한 CIK가 95% 이상이면서 차순위의 10배 이상일 때만 채택한다.

로컬 전체 스캔 캐시는 원본 snapshot의 `derived/`에 gzip JSON으로 저장한다.
cache key가 공식 manifest, 종목 universe, SEC identity, scan rule 중 하나와
달라지면 전체 원본을 다시 읽는다.

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

## 9. 실험 판정 원장

완료한 사전등록 연구는 `herd/experiment_ledger.json`에 순서대로 기록한다.
각 행은 사전등록 원문과 결과 파일의 SHA-256, 선언한 시험 수, 최종 판정,
직전 행 해시를 포함한다. 연구 결과는 스스로 운영 승격을 허용할 수 없다.

```bash
cd data
PYTHONPATH=. python -m herd.experiment_ledger
```

원문·결과·과거 판정 중 하나가 바뀌거나 행이 재정렬되면 검증은 실패한다.
탈락 가설을 다시 검증하려면 기존 행을 수정하지 않고, 경제적 가설 또는
측정식이 무엇이 달라졌는지 명시한 새 사전등록과 새 행을 추가한다.

## 10. 연구 입력 계약

가격, S&P 구성, ticker–CIK 유효기간, SEC corpus와 fold 연결 결과는
`herd/research_input_contract.json`에서 함께 고정한다. SEC 사실은
`filed` 날짜가 아니라 EDGAR `ACCEPTANCE-DATETIME` 이후에만 사용할 수
있다. 접수 시각·CIK·구성 사건이 불명확하면 보정하거나 추정하지 않고
제외한다.

```bash
cd data
PYTHONPATH=. python -m herd.research_input_contract --deep
```

## 11. Form 4 원문·atomic 거래 corpus

Form 4는 submissions 컨테이너 CIK를 issuer로 가정하지 않는다. 먼저
거래 내용과 가격 결과를 보지 않고 issuer·연도별 accession 표본을 해시로
잠근 뒤 SEC Archive의 `primaryDocument`를 내려받는다. 원문 XML의
`issuerCik`가 기대 issuer와 일치한 문서만 atomic 원장에 포함하며,
불일치는 삭제하지 않고 rejection 원장에 보존한다.

atomic 거래는 EDGAR 접수시각, P/S 및 기타 거래코드, 가격·수량·거래 후
보유량, 직접·간접 소유, 모든 각주를 보존한다. SEC 공식 정의에 따라
P/S는 공개시장 또는 사적 거래로 기록하고, A/D/I와 파생상품 코드도
코드별 의미를 보존한다. 연구 편의를 위한 상위 `economicGroup`은
`economicClass`와 별도로 둔다. code F를 시장 매도로 취급하지 않고
10b5-1 미표시 역사 문서는 `UNKNOWN`으로 둔다. 원문 검수 267건, 40개
이상 issuer, 거래코드 coverage 98%, 필드 정확도 95%, Wilson 95% 하한
90%를 모두 통과하기 전에는 방향 가설이나 HERD 입력을 만들지 않는다.
각주에 10b5-1이라는 단어가 있다는 이유만으로 `TRUE`를 만들지 않는다.
일반 거래정책·예외 설명은 `UNKNOWN`이며, 문서 체크박스나 해당 거래가
계획에 따라 실행됐다는 transaction-specific 문장만 명시적 근거다.

검수 워크벤치는 다음 명령으로 재생한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.sec_form4_review_workbench_v1 \
  data/reports/sec_form4_source_review_v1.csv \
  data/reference/sec/sec-form4-source-v1-20260723 \
  --protocol data/herd/sec_form4_review_protocol_v1.json \
  --output data/reports/sec_form4_review_workbench_v1.html \
  --manifest-output data/reports/sec_form4_review_workbench_v1.json
```

워크벤치의 `HIGH`는 오류 판정이 아니다. 희소·서술형 거래코드, 가격
미보고, 간접 소유, 다중 보고자, transaction 각주에서 확인한 10b5-1처럼
의미를 먼저 확인할 대상을 뜻한다. `STANDARD`도 생략하지 않으며, 두
집단 모두 판정이 끝나야 accuracy gate를 계산한다.

원문 검수 판정과 자동 구조 검증은 합치지 않는다. 자동 검증만으로
`VALID`를 생성하거나 검수 CSV를 덮어쓰면 정확도 게이트 입력으로 인정하지
않는다. 완료 판정에는 검수자 ID, UTC 시각, 검수 방식이 모두 필요하다.
현재 판정은 `AI_ASSISTED_PRIMARY_SOURCE_DIRECT`로 명시하며 독립 사람
검수라고 표현하지 않는다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.sec_form4_structural_audit_v1 \
  data/reports/sec_form4_source_review_v1.csv \
  data/reference/sec/sec-form4-source-v1-20260723 \
  --protocol data/herd/sec_form4_review_protocol_v1.json \
  --detail-output data/reports/sec_form4_structural_audit_v1.csv \
  --report-output data/reports/sec_form4_structural_audit_v1.json

PYTHONPATH=data data/.venv/bin/python -m herd.sec_form4_source_review_gate_v1 \
  data/reports/sec_form4_review_adjudicated_v1.csv \
  data/reports/sec_form4_atomic_transactions_v1.csv \
  --protocol data/herd/sec_form4_review_protocol_v1.json \
  --structural-audit data/reports/sec_form4_structural_audit_v1.json \
  --output data/reports/sec_form4_source_review_gate_v1.json
```

워크벤치에서 내보낸 판정은 곧바로 게이트에 넣지 않는다. 다음 병합기가
atomic ID, 검수 해시, issuer, accession, 거래코드, 경제 분류와 원문
SHA-256이 잠긴 queue와 완전히 같은지 확인한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.sec_form4_review_ledger_v1 \
  data/reports/sec_form4_source_review_v1.csv \
  data/reports/sec_form4_review_decisions_v1.csv \
  --output data/reports/sec_form4_review_adjudicated_v1.csv \
  --report-output data/reports/sec_form4_review_ledger_v1.json
```

원문 정확도 게이트를 통과한 뒤에는 다음 coverage 감사를 반드시 실행한다.
`source corpus == 검수 표본`만 확인해서는 연구 모집단이 되지 않는다.
다운로드 accession, issuer 불일치 격리, atomic 거래 생성, 미해결 문서를
기업·연도별로 각각 센다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_form4_coverage_audit_v1 \
  data/reports/sec_form4_accession_catalog_v1.csv \
  data/reports/sec_form4_source_sample_v1.csv \
  data/reference/sec/sec-form4-source-v1-20260723/index.csv \
  data/reference/sec/sec-form4-source-v1-20260723/manifest.json \
  data/reports/sec_form4_atomic_transactions_v1.csv \
  data/reports/sec_form4_issuer_rejections_v1.csv \
  --source-gate data/reports/sec_form4_source_review_gate_v1.json \
  --protocol data/herd/sec_form4_corpus_v1.json \
  --detail-output data/reports/sec_form4_issuer_year_coverage_v1.csv \
  --report-output data/reports/sec_form4_coverage_audit_v1.json
```

현재 V1은 `PARSER_AND_SOURCE_REVIEW_DEVELOPMENT_ONLY`이며 68,478개 catalog
accession 중 1,485개만 내려받은 축소 표본이다. 따라서 parser 정확도
게이트가 통과해도 `RESEARCH_CENSUS_COVERAGE_PASSED`가 될 수 없다.
미해결 원문이 1건이라도 있거나 manifest 계보가 다르면 fail-closed한다.
V1 산출물을 덮어써 연구용으로 재해석하지 않고 별도 V2 census와 manifest를
만든 뒤 이 감사를 다시 실행한다.

V2는 SEC `Insider Transactions Data Sets`의 2012Q1~2026Q2 공식 분기 ZIP
58개를 사용한다. ZIP은 분기별 SHA-256으로 고정하며 수집이 중단돼도 완료된
분기부터 재개한다. 공식 벌크는 acceptance timestamp를 제공하지 않으므로
신고일 당일에는 사용할 수 없고, 신고일보다 엄격히 뒤의 가격 세션에서만
사용한다. 벌크 숫자는 SEC `NUMBER(16,2)` 정밀도이므로 원문 XML과의
동등성은 반올림 후 비교하며, 버려진 소수 정밀도는 feature로 사용하지 않는다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.sec_form4_bulk_v2 download \
  sec-form4-bulk-v2-2012q1-2026q2-20260723

PYTHONPATH=data data/.venv/bin/python -m herd.sec_form4_bulk_v2 normalize \
  data/reference/sec/sec-form4-bulk-v2-2012q1-2026q2-20260723

PYTHONPATH=data data/.venv/bin/python -m herd.sec_form4_census_gate_v2 \
  data/reference/sec/sec-form4-bulk-v2-2012q1-2026q2-20260723
```

coverage 게이트 통과 뒤에도 여러 내부자 지표를 탐색하지 않는다. 잠근
`NON_ROUTINE_CODE_P_PURCHASE_SUPPORT_90D` 가설 하나만 다음 명령으로
실행한다. 결과가 탈락하면 기간·routine 기준·대상 경로를 조정해 같은
표본을 재시험하지 않는다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_form4_insider_purchase_oos_v1 \
  data/reference/sec/sec-form4-bulk-v2-2012q1-2026q2-20260723
```

Form 4 가설 탈락 뒤에는 같은 표본의 기간이나 거래 분류를 조정하지 않는다.
경제적으로 독립된 경영진 전망 변화는 SEC 가이던스 atomic fact로만
확장한다. V10 자동 파서 후보는 사실로 승격하지 않고, 가격 결과를 열기 전에
원문 검수 모집단과 해시를 먼저 잠근다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_guidance_atomic_census_v2 \
  --review data/reports/sec_guidance_atomic_census_v2_review.csv \
  --report data/reports/sec_guidance_atomic_census_v2.json \
  --workbench data/reports/sec_guidance_atomic_census_v2_workbench.html

PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_guidance_atomic_census_v2_review \
  --reviewed data/reports/sec_guidance_atomic_census_v2_reviewed.csv \
  --report data/reports/sec_guidance_atomic_census_v2_source_review.json
```

워크벤치 159행은 모두 `PENDING`으로 시작하며 지표·전망기간·회계기준·
subtype·단위·현재 범위가 SEC 원문에서 모두 확인된 행만 `VALID`로
판정한다. 판정 결과는 VALID 143, INVALID 3, AMBIGUOUS 13이며 Wilson
95% 하한 94.13%로 원문 정확도 게이트를 통과했다. 다음 단계에서도
`VALID` 행만 atomic binding으로 승격하며 방향 라벨과 가격은 아직 열지
않는다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_guidance_atomic_bindings_v2 \
  --bindings data/reports/sec_guidance_atomic_bindings_v2.csv \
  --report data/reports/sec_guidance_atomic_bindings_v2.json

PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_guidance_atomic_pairs_v2 \
  --pairs data/reports/sec_guidance_atomic_pairs_v2.csv \
  --report data/reports/sec_guidance_atomic_pairs_v2.json
```

수정쌍은 176개·31기업·15개 접수연도로 coverage 게이트를 통과한다.
MCO가 23.86%를 차지하므로 이후 방향 OOS는 기업 균형 집계와 ticker
cluster 불확실성 없이 실행할 수 없다.

가격 결과를 열기 전에 `sec_guidance_lower_oos_v2.json`의 단일 하향
가설·입력 해시·4개 시대·채택 기준을 먼저 커밋한다. 그 뒤 아래 명령으로
issuer 균형 OOS를 재현한다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_guidance_lower_oos_v2 \
  --panel data/reports/sec_guidance_lower_oos_panel_v2.csv \
  --issuer-effects data/reports/sec_guidance_lower_oos_issuer_effects_v2.csv \
  --report data/reports/sec_guidance_lower_oos_v2.json
```

170쌍·27기업을 평가했지만 섹터 잔차수익과 최대낙폭 효과가 모두 예상과
반대이고 4개 시대 중 1개만 방향이 일치해 가설은 탈락했다. 같은 표본에서
하향 임계값이나 기간을 조정하지 않는다.

탈락한 Form 4와 가이던스를 같은 표본에서 재조정하지 않고, 다음 공개
정보원의 실제 연구 가능성을 아래 명령으로 판정한다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.public_leading_data_feasibility_v1 \
  --output data/reports/public_leading_data_feasibility_v1.json
```

FINRA는 약 5.14년이라 최근 민감도·prospective shadow만 허용하고, 13F는
최대 45일 지연 때문에 느린 context로 제한한다. 전체 옵션 surface는 유료,
무료 Cboe 거래량은 IV·skew 대체가 아니므로 1차 OOS 준비 정보원은 0개다.

FINRA 최근 lane은 먼저 공식 원본을 append-only SHA corpus로 고정한다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  data/herd/finra_short_interest_census_v1.py

PYTHONPATH=data data/.venv/bin/python \
  data/herd/finra_short_interest_coverage_audit_v1.py

PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_time_valid_ticker_cik_ledger_v4

PYTHONPATH=data data/.venv/bin/python \
  -m herd.finra_short_interest_coverage_audit_v4
```

대용량 CSV와 receipt는 `data/reference/finra`에 로컬 보관하고, 전체 URL·
결제기준일·유도 공개일·HTTP 정정 메타데이터·SHA-256은 추적 manifest에
커밋한다. 같은 결제기준일의 새 SHA는 기존 원본을 덮어쓰지 않는다.

coverage 감사는 short position 값과 가격을 결합하지 않는다. 현재 ticker
표기 관측률과 날짜 유효 CIK 연결률을 분리하며, 검증된 SEC alias interval이
없는 symbol은 `CURRENT_SYMBOL_OBSERVED_PIT_CIK_UNVERIFIED`로 남긴다.
V4는 표적 SEC 표지 396건의 원문 SHA와 ticker 앵커 536개를 검증한 뒤
기존 51개 97.12%, 독립 388개 95.51%로 식별자 게이트를 통과했다. 이
결과는 방향성 OOS를 허용하지 않으며 FINRA는 prospective shadow 관측에만
사용한다.

야간 PIT 확장과 prospective seed snapshot은 아래 순서로 재현한다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.overnight_pit_shadow_runner_v1 --preflight

PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_identifier_gap_queue_v1

PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_targeted_cover_corpus_v2

PYTHONPATH=data data/.venv/bin/python \
  -m herd.sec_time_valid_ticker_cik_ledger_v5

PYTHONPATH=data data/.venv/bin/python \
  -m herd.finra_short_interest_lifecycle_coverage_v5

PYTHONPATH=data data/.venv/bin/python \
  -m herd.finra_short_interest_incremental_v2

PYTHONPATH=data data/.venv/bin/python \
  -m herd.unified_pit_shadow_panel_v1
```

SEC 표지 corpus V2의 원본은 append-only 로컬 디렉터리에 저장하고 추적
저장소에는 accession·source SHA·추출 앵커·요약만 둔다. 예상 filing 수는
중단 기준이 아니다. 적격 source가 모두 수집됐거나 항목별 blocker가
기록됐을 때만 다음 단계로 이동한다.

FINRA 증분 수집기는 미국 동부시간의 공식 공개시각 전에는 새 파일을
요청하지 않는다. 공개 당일 파일을 받더라도 보수적인 PIT 사용 시각은 다음
달력일 00:00 ET다. 통합 패널의 현재-reference CIK fallback은 최신
prospective snapshot에만 허용하고 과거 결제기준일에는 사용할 수 없다.

전체 회귀 영수증은 아래 명령으로 생성한다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.overnight_pit_shadow_regression_v1
```

Python 전체, backend test, frontend lint·test·build, `git diff --check` 중
하나라도 실패하면 보고서는 `FULL_REGRESSION_FAIL`이고 완료 감사는
승인되지 않는다.

회귀 영수증과 Part 1~6의 보고서, artifact catalog, 현황 문서를 고정한 뒤
최종 완료 감사를 실행한다.

```bash
PYTHONPATH=data data/.venv/bin/python \
  -m herd.overnight_pit_shadow_completion_v1
```

`OVERNIGHT_PIPELINE_COMPLETE_RESEARCH_BLOCKED`는 수집·식별자·증분 갱신·
통합 snapshot·회귀가 완료됐다는 뜻이다. 방향 증거 0개, 개별 식별자
blocker, FINRA 장기 OOS 불가 상태는 그대로이므로 모델 채택이나 운영
행동 승인을 의미하지 않는다.

`--deep`은 manifest뿐 아니라 가격 55종목과 SEC 원본의 개별 SHA-256까지
대조한다. 현재 구성 스냅샷은 차단 사건 4건이 남은 진단본이므로 모델
탈락과 민감도 연구에만 사용하며 최종 채택·운영 신호에는 사용할 수 없다.

## HERD State S1

새 상태 지수는 미래 경로·수익률·행동 라벨을 읽지 않는다. 고정한 14년
주 표본과 독립 현재 구성 표본의 가격 파일을 개별 SHA-256까지 확인하고
완료 주봉 상태를 생성한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.herd_state_s1
```

전체 주간 패널은 재현 가능한 로컬 산출물인
`data/walk_forward/herd-state-s1`에 저장한다. 추적 저장소에는 계약,
입력·패널 hash와 안정성 게이트 결과, 최신 종목 상태만 보존한다.
`STATE_DISPLAY_READY`는 상태 측정 안정성만 승인하며 방향 예측이나 행동
권한을 승인하지 않는다.

상태 패널이 준비된 뒤 전환 패널은 다음 명령으로 재현한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.herd_transition_s1
```

전환 계산은 raw 분류와 안정화 결과를 모두 보존한다. 방향 전환은 완료
주봉 두 번 연속 확인되어야 하며 최근 4주 안의 반대 방향은 `NEUTRAL`로
억제한다. 억제 규칙은 예측력을 높이기 위한 사후 임계값이 아니라 표시
상태의 주간 진동을 막는 outcome-blind 계약이다.

신규 현금이 없는 기존 보유자 코호트의 수익 반납 정책 사건은 다음 명령으로
생성한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.profit_giveback_policy_v1
```

완결 사이클 경제성 평가는 고정 사건, transition, SEC PIT 기업 상태,
가격·fold manifest의 해시를 다시 확인한 뒤 실행한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.profit_giveback_economic_v1
```

계약은 외부 입금 없음, 조정 시가, 다음 거래일 체결, 10·25·50bp 비용과
통과 기준을 결과 전에 고정한다. 결과 파일의
`operational_action_ratio=0.0`과 `blind_holdout_access=false`는
pre-holdout 통과 전까지 변경할 수 없다.

현재 증거에서 개인 MVP에 허용되는 범위는 다음 판정으로 고정한다.

```bash
PYTHONPATH=data data/.venv/bin/python -m herd.personal_action_review_gate_v2
```

State S1과 Transition S1은 관찰 기능으로 승격할 수 있지만, 경제성
pre-holdout과 Blind holdout을 통과하지 않은 매수·익절·재진입 비율은
항상 차단한다.

사건 생성 단계는 fold 종료 이후 가격을 정책 조건에 사용하지 않는다.
`POLICY_EVENTS_READY`는 사전등록한 사건 수와 종목·fold coverage가
충분하다는 뜻이며 경제성이나 매매 권한을 의미하지 않는다.

## 12. 장기 라벨 OOS 분할

라벨 길이가 다른 가격 타이밍과 기업 상태를 같은 fold로 평가하지 않는다.
`herd/oos_fold_protocol.json`은 다음 두 lane을 고정한다.

- `PRICE_TIMING_6M`: 126거래일 purge, 20거래일 embargo, 1년 test
- `BUSINESS_STATE_12M`: 252거래일 purge, 20거래일 embargo, 2년 test

test 구간은 서로 겹치지 않으며 미래 결과가 test 종료일을 넘는 사건은
제외한다. 현재 10년 스냅샷은 가격 lane 5개로 기준을 충족하지만 기업
상태 lane은 2개뿐이라 채택 검증에 사용할 수 없다. 이 부족을 해결하려고
purge나 라벨을 사후 축소하지 않는다.

## 13. Buy & Hold 비교 불변조건

전략과 Buy & Hold는 같은 날짜, 초기 자본, 외부 입출금, 다음 시가 체결,
수수료와 슬리피지를 사용해야 한다. 하나라도 다르면 비교 엔진이 실행을
거부한다. CAGR뿐 아니라 최종 자산 차이와 최종 보유 주식 수 차이를 함께
저장한다. 부분 익절 뒤 재진입하지 못한 전략은 현금이 남아 있더라도
`terminal_share_delta`에서 드러난다.

주식 수는 동일한 자동조정 가격 계열 안에서 후보와 Buy & Hold를 상대
비교하는 연구값이다. 실제 브로커 계좌의 원주 수량으로 해석하지 않는다.

## 14. 완결 행동 사이클

부분 익절은 단독 성공으로 집계하지 않는다. 매도 순현금을 이후 매수
총비용에 FIFO로 연결하고 전액이 재투입된 경우에만 사이클을 닫는다.
완결 사이클은 매도 주식 수, 재진입 주식 수, 증감 수량과 대기일을 저장한다.
재진입하지 못한 매도는 `open_sale_count`와 `open_sale_cash`로 남긴다.

초기 100% 보유를 만들기 위한 공통 매수는 재진입으로 집계하지 않는다.
익절 방향 증거가 통과하기 전에는 이 평가기를 가상 후보 분석에만 사용하며
운영 매도 신호를 만들지 않는다.

익절 목표·빈도·비용 계약의 일관성은 다음으로 확인한다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.profit_take_contract_gate_v1
```

이 게이트는 5% 익절 목표와 건강한 상승 지속의 기회비용 라벨이
서로 어긋나지 않았는지만 검증한다. 통과해도 다음 단계는 독립 OOS
방향 증거이며 행동 비율은 0%다.

## 15. SEC PIT 가격·fold 연결

가격 ticker를 current CIK 하나로 전체 과거에 소급하지 않는다. 먼저
가격 스냅샷과 현재 CIK를 감사하고, corpus가 없는 CIK만 별도 수집한다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.sec_price_fold_link \
  snapshots/yf-10y-20260719/manifest.json \
  reference/sec/sec-current-20260719/ticker_cik_current.csv \
  reference/sec/sec-pit-price51-20160718-20260717-20260721 \
  walk_forward/fixed-b0-b3-20260719/folds.csv \
  reports/sec_price_fold_link_v2.csv \
  --additional-corpus \
  reference/sec/sec-pit-157cik-20160718-20260717-20260719 \
  --additional-corpus \
  reference/sec/sec-pit-xom34088-20160718-20260717-20260721 \
  --cik-periods herd/price_universe_cik_periods.csv
```

ETF는 `NOT_APPLICABLE_ETF`, SEC 접수시각 미연결과 CIK 유효기간 오류는
fail-closed로 처리한다. 기업 승계가 발생한 ticker는 현재 CIK를 과거에
소급하지 않고 `price_universe_cik_periods.csv`의 유효기간으로 연결한다.
접수 시각이 fold 경계보다 늦은 관측은 해당 fold에 노출하지 않는다.

2026년 Exxon Mobil 지주회사 재편 전 연구 fold에는 옛 CIK
`0000034088`을, 재편 이후에만 `0002115436`을 사용한다. 이 보정 후 최신
fold의 엄격 PIT 연결은 51개 기업 중 50개다. CRM은 CompanyFacts의 한
제출번호에 SEC 접수시각이 없어 별도 제외 영향 감사를 통과하기 전까지
엄격 PIT 준비 상태로 승격하지 않는다.

## 16. S1 과거 설명 재생

State S1과 Transition S1의 고정 패널을 다시 계산하지 않고, 고정 가격
스냅샷에 연결해 사건별 다중 만기 결과를 만든다.

```bash
cd data
.venv/bin/python -m herd.historical_s1_replay_v1
```

입력 패널과 가격 manifest는 기존 보고서의 SHA-256과 대조한다. 결과는
`reports/historical_s1_replay_v1.csv.gz`와 동명의 JSON 영수증에 저장한다.
같은 episode와 horizon 조합이 중복되면 실행을 중단한다.
5·10·20·40·60·130거래일은 설명용 경로이며, prospective evidence
원장과 직접 비교할 때는 계약이 같은 21·63·126거래일만 사용한다.

이 재생은 현재 구성 종목의 과거 가격을 사용한 진단이며 공식 과거
S&P 500 구성 백테스트가 아니다. `survivorship_safe=false`,
`operational_action=HOLD`, `operational_action_ratio=0.0`은 변경할 수 없다.

재생 행을 독립 표본으로 과장하지 않도록 다음 의존성 감사를 실행한다.

```bash
cd data
.venv/bin/python -m herd.historical_s1_dependency_audit_v1
```

감사는 전체 439종목의 주간 중앙값으로 시장 HERD 국면을, 고정 섹터
peer의 중앙값으로 섹터 국면을 계산한다. episode·ticker·signal week·
sector-signal week·era의 고유 개수와 관측 주 집중도를 기록한다.
이 결과는 이후 군집 검정의 단위를 고정할 뿐 통계적 독립성이나 방향
예측력을 승인하지 않는다.

과거 설명 맥락과 전향 관측의 준비 상태는 다음으로 감사한다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.historical_prospective_bridge_v1
```

과거와 전향 원장은 정확히 같은 21·63·126거래일에서만 비교한다.
전향 관측일이 2개 미만이거나 만기별 결과가 30건 미만이면 비교를
`PENDING`으로 유지한다. 이 기준은 상태 관찰과 과거 설명 통계 사용을
막지 않지만 방향 예측과 행동 비율은 승인하지 않는다.

종목 상세에 제공할 설명 전용 축약 자료는 다음 명령으로 재생한다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.historical_s1_product_context_v1
```

다섯 단계의 ENTRY 사건을 42일 간격으로 접고 21·63·126거래일만
집계한다. 종목별 5건 미만이면 현재 구성 종목 참조군으로 대체한다.
생성된 classpath JSON은 Spring이 시작할 때 행동 차단 계약과 버전을
검증한다. 이 자료는 설명 전용이며 `survivorship_safe=false`,
`direction_prediction=false`, `HOLD·0%`를 유지한다.

## 17. SEC 실적발표 문구 연구 준비

해시가 고정된 SEC 8-K corpus에서 Item 2.02 실적발표 첨부문서를 고르고,
같은 CIK의 직전 발표와 연결한 가격 비노출 비교 원장을 만든다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.sec_earnings_soft_information_feasibility_v1
```

실행기는 계약에 고정된 corpus manifest와 index, 행동 사이클 계약, 탈락
가설 원장과 성공 라벨 보고서의 SHA-256을 먼저 확인한다. accession마다
가장 큰 `TEXT_ATTACHMENT` 하나만 선택하고 원문 파일 경로가 실제 SHA-256
주소와 일치하는지 검증한다. 같은 CIK 안에서 30~550일 사이의 직전 발표만
비교쌍으로 허용한다.

산출물은 `reports/sec_earnings_soft_information_pairs_v1.csv`와
`reports/sec_earnings_soft_information_feasibility_v1.json`이다. 비교 원장에
가격·수익률·라벨·HERD·행동 열이 들어오거나 원격 모델, 비상업용 사전,
고정되지 않은 LLM 호출이 설정되면 fail-closed 한다. 이 단계는 원문
coverage만 판정하며 문구 방향 점수와 매수·익절 신호를 만들지 않는다.

원문 검수용 원자 사실과 잠긴 표본은 다음으로 만든다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.sec_earnings_soft_information_measurement_v1
PYTHONPATH=. .venv/bin/python -m herd.sec_earnings_soft_information_source_review_v1
```

첫 명령은 issuer·3년 구간을 먼저 층화한 720개 문서만 처리한다. 생성하는
candidate와 review CSV에는 원문 문장을 저장하지 않는다. 두 번째 명령은
240건이 모두 `PENDING`인지 확인하고 미완료 게이트 영수증을 만든다.

원문 검수 화면은 커밋 대상이 아닌 로컬 임시 파일로 생성한다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.sec_earnings_soft_information_review_workbench_v1 \
  reports/sec_earnings_soft_information_source_review_v1.csv \
  --output /tmp/herdsignal-sec-soft-info-review.html
```

워크벤치에서 내보낸 판정은 잠긴 queue와 동일성 검증 후에만 병합한다.

```bash
cd data
PYTHONPATH=. .venv/bin/python -m herd.sec_earnings_soft_information_source_review_v1 \
  --queue reports/sec_earnings_soft_information_source_review_v1.csv \
  --decisions /path/to/sec_earnings_soft_information_decisions_v1.csv \
  --output reports/sec_earnings_soft_information_source_review_adjudicated_v1.csv \
  --report reports/sec_earnings_soft_information_source_review_gate_v1.json
```

검수 화면에만 원문 문장이 포함되고 저장소에는 문장 해시와 파생 사실만
남는다. 원문 정확도 게이트 통과 전에는 현재·직전 발표 비교, 방향 점수,
가격 결과와 HERD 행동을 계산하지 않는다.

## 근거

- scikit-learn `TimeSeriesSplit`: 시간 순서를 보존하고 train과 test 사이
  `gap`을 지원한다.
- López de Prado의 purged/embargoed cross-validation: 라벨 구간 중첩과
  시계열 의존성에 의한 누출을 줄인다.
- pandas gzip의 고정 `mtime`: 동일 입력 파일을 재현 가능한 바이트로
  저장할 수 있다.
- SHA-256: 파일 무결성과 실행 입력 식별에 사용한다.

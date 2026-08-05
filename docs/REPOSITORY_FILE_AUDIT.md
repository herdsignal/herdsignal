# HerdSignal 저장소 파일 감사

기준일은 2026-08-05다. 이 문서는 파일을 “지금 실행에 쓰임”, “연구 재현성에
필요”, “재생성 가능”, “분류 필요”로 나눈다. 오래됐다는 이유만으로 연구 파일을
삭제하지 않는다.

## 현재 과정

현재 진행 중인 일은 매수·매도 모델 개발이 아니라 SEC 8-K 중요 사건을 과거
ticker와 시점 유효하게 연결하기 위한 데이터 품질 과정이다.

1. 중요 사건 947건에서 식별 공백 762건을 찾았다.
2. 우선순위 P0·P1 원문 275건을 해시 snapshot으로 고정했다.
3. 기존 추출 후보 110건을 사람이 검수했지만 Wilson 95% 하한 0.8407로 승격
   기준 0.90에 실패했다.
4. 실패 10건이 모두 HTML `TD`·`DIV` 태그명 오탐임을 확인했다.
5. 구조적 표지 파서 V2가 기존 110건 개발 회귀를 통과하고 무후보 165건에서
   새 후보 5건을 찾았다.
6. 새 5건은 별도 원장으로 검수한다. 표본이 최소 100건보다 작아 모두 맞더라도
   ticker 승격이나 투자 행동을 열지 않는다.

## 관련 파일

- 실행 계약과 구현: `data/herd/sec_8k_identity_*`,
  `data/herd/sec_8k_structural_*`
- 원문·수집 인덱스: `data/reference/sec/sec-8k-identity-primary-*`,
  `data/reports/sec_8k_identity_primary_document_collection_v1.*`
- 사람 판정 정본: `data/reports/sec_8k_identity_source_review_v1.csv`,
  `data/reports/sec_8k_structural_candidate_review_v1.csv`
- 상태 연결: `data/tools/current_state_audit.py`, `data/tools/research_status.py`
- 재현 명령: `scripts/refresh-sec-review-state.sh`,
  `scripts/audit-sec-identity-failures.sh`,
  `scripts/build-sec-structural-cover-v2.sh`,
  `scripts/review-sec-structural-candidates.sh`

`sec_8k_guidance_*`는 경영진 가이던스 문장 연구이고, 현재의 ticker 식별 과정과
이름만 비슷한 별도 흐름이다. `former_constituent_sec_identity_corrections_v1`과
`sec_identity_evidence_merge.py`는 편출 종목·기존 PIT 식별 흐름이므로 현재
5건 원장에 섞지 않는다.

## 보존해야 하는 파일

- `data/reference` 약 30GB: Git에는 없지만 공식 원문과 PIT 재현성의 근거다.
- `data/reports`의 잠긴 CSV·JSON: 현재 모델에서 탈락했어도 결과 재사용과
  임계값 재조정을 막는 영수증이다.
- `research_artifact_catalog.json` V1: 현행 카탈로그는 아니지만
  `overnight_pit_shadow_completion_v1.json`의 해시 입력이라 삭제할 수 없다.
- `backups/herdsignal-20260726-230035.sql.gz`: 코드에는 불필요하지만 복구용
  백업이다. 삭제 여부는 보존 기간 정책을 먼저 정해야 한다.

## 재생성 가능하거나 정리 가능한 파일

- `.DS_Store`, `.pytest_cache`, `__pycache__`
- `backend/build`, `backend/bin`, `backend/.gradle`
- `frontend/node_modules`

이들은 현재 모두 Git ignore 대상이다. 디스크가 필요할 때 안전하게 재생성할 수
있지만 이번 감사에서는 삭제하지 않았다.

## 아직 쓸모없다고 단정할 수 없는 기술부채

연구 inventory 734개 중 495개가 `REVIEW_REQUIRED`다. 이 가운데 `data/herd`
142개, `data/reports` 344개, 문서 9개가 아직 ACTIVE·DATA_PIPELINE·REJECTED·
LEGACY_REFERENCE·DIAGNOSTIC 중 하나로 분류되지 않았다. 이는 즉시 삭제 목록이
아니라 보존 등급을 확인해야 하는 backlog다.

다음 저장소 정리 작업은 파일을 지우는 것이 아니라 495개를 생성자·잠긴 입력
참조·현재 코드 참조 기준으로 묶어 분류하는 것이다. 참조가 없고 재생성 가능하며
잠긴 해시 입력도 아닌 파일만 별도 삭제 후보 원장에 올린다.

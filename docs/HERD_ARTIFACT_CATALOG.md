# HERD 연구 산출물 분류

기준일: 2026-07-23

연구 파일이 많다는 이유만으로 삭제하지 않는다. 탈락 실험도 임계값을 바꿔
다시 시도하는 일을 막고 과거 판정을 재현하는 근거다. 기계 판독 원장은
`data/herd/research_artifact_catalog.json`이다.

| 상태 | 의미 | 현재 대표 묶음 |
| --- | --- | --- |
| `ACTIVE` | 다음 연구 판정에 직접 사용 | SEC 가이던스 구조 파서 V7 독립 원문 판정 |
| `DATA_PIPELINE` | 재현 입력 생성 | SEC PIT, 가격 스냅샷, S&P 구성, CIK·기업행동 |
| `REJECTED` | 사전 기준에서 탈락 | Rush, RSI, 재진입, 완결 사이클 실험 |
| `LEGACY` | 현행 판단에 미사용 | 과거 v3~v6.1 백테스트와 이전 검증 경로 |

현재 연구 사슬은 SEC 8-K 구조 파서와 별개로 Form 4 원문 1,485건 →
issuer 검증 1,455건 → atomic 거래 3,661건까지 구축됐다. Form 4 검수
표본 267건은 AI 보조 원문 판정과 독립 구조 감사에서 267건 모두
`VALID`였고 Wilson 95% 하한은 98.58%다. 이는 parser 정확도 게이트만
통과한 결과다. coverage 감사에서는 잠긴 68,478개 accession 중
1,485개(2.17%)만 내려받은 parser 검수 표본이며, issuer 확인 후 atomic
거래가 없는 원문 9건과 manifest 계보 불일치가 확인됐다. 판정은
`REVIEW_SAMPLE_NOT_RESEARCH_CENSUS`다. 별도 연구 census V2를 완성하기
전에는 방향 가설, 가격 OOS, HERD 가중치로 진행하지 않는다.

차세대 연구의 최상위 계약은
`data/herd/herd_vnext_model_charter_v1.json`이다. 이 계약은 v4·v6.1을
레거시 기준선으로 동결하고 HERD 상태, 전환, 기업 veto, 행동 edge, 개인
포트폴리오 번역과 운영 승격 권한을 분리한다. 이후 후보와 MVP 코드는 이
계약을 완화할 수 없다.

삭제는 import·문서 참조, 고정 hash 입력, 실험 재현 필요성을 모두 확인하고
회귀 테스트를 통과한 파일에만 허용한다. 분류되지 않은 새 파일은 자동 삭제
대상이 아니라 `REVIEW_REQUIRED`다.

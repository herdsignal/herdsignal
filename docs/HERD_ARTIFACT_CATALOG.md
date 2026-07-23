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

Form 4 V1은 원문 parser 검수 역할로 유지한다. V2는 SEC 공식 분기 벌크
2012Q1~2026Q2 58개를 해시 고정하고 438개 issuer의 Form 4/4-A
464,619건과 원자 거래 1,133,161건을 정규화했다. 기존 원문 판정 중 벌크
기간에 포함된 265건은 SEC 2자리 정밀도 기준으로 265건 모두 일치했고
Wilson 95% 하한은 98.57%다. 독립 issuer 387개·issuer-year 5,805칸을
관측해 census coverage 게이트는 통과했다.

그 뒤 하나만 잠근 비정기 P 매수 지지 가설은 독립 Rush 2,626건에서
방향은 예상과 같았지만 feature 양성 51건·31개 종목뿐이었다. 4개 fold 중
양성 10건 이상은 2개뿐이고 ticker-cluster bootstrap 95% 신뢰구간 상단이
+1.18%p로 0을 넘었다. 판정은 `REJECTED`다. 내부자 정보는 HERD나 행동
비율에 들어가지 않으며 같은 표본에서 기간·routine 기준을 다시 조정하지
않는다.

차세대 연구의 최상위 계약은
`data/herd/herd_vnext_model_charter_v1.json`이다. 이 계약은 v4·v6.1을
레거시 기준선으로 동결하고 HERD 상태, 전환, 기업 veto, 행동 edge, 개인
포트폴리오 번역과 운영 승격 권한을 분리한다. 이후 후보와 MVP 코드는 이
계약을 완화할 수 없다.

개인 저축이 모델 성과로 오인되지 않도록
`data/herd/personal_cashflow_benchmark_v1.json`에서 추가 입금 없음·고정
월 적립·실제 현금흐름을 분리했다. 후보와 Buy & Hold에는 같은 입금과
비용을 강제하고, TWR은 모델 성과, MWR은 실제 계좌 경험으로 나눠 기록한다.

`data/herd/vnext_competing_path_economic_label_v1.json`은 미래 경로와 행동
경제성을 분리한다. 첫 상승·하락 경계와 최종 경로를 함께 보존하고, 관측
가능한 재진입 신호가 없는 익절은 성공으로 세지 않는다.

`data/herd/vnext_joint_hypothesis_v1.json`으로 시장·섹터, 종목 전환,
peer 참여, SEC PIT 기업 상태를 한 번만 결합해 검사했다. 고정 L2 모델은
pre-holdout OOS에서 단순 양성률 기준선보다 나빠 `REJECTED`로 이동했다.
현재 판정은 `data/reports/vnext_preholdout_evaluation_v1.json`이며,
prospective shadow는 시작하지 않았다.

삭제는 import·문서 참조, 고정 hash 입력, 실험 재현 필요성을 모두 확인하고
회귀 테스트를 통과한 파일에만 허용한다. 분류되지 않은 새 파일은 자동 삭제
대상이 아니라 `REVIEW_REQUIRED`다.

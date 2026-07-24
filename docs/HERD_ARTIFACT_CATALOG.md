# HERD 연구 산출물 분류

기준일: 2026-07-25

연구 파일이 많다는 이유만으로 삭제하지 않는다. 탈락 실험도 임계값을 바꿔
다시 시도하는 일을 막고 과거 판정을 재현하는 근거다. 기계 판독 원장은
현행 원장은 `data/herd/research_artifact_catalog_v2.json`이다. 기존
`research_artifact_catalog.json`은 2026-07-24 야간 PIT 완료 감사가 해시로
참조하는 V1 영수증이므로 수정하지 않는다.

| 상태 | 의미 | 현재 대표 묶음 |
| --- | --- | --- |
| `ACTIVE` | 다음 연구 판정에 직접 사용 | 모델 헌장·현금흐름 계약·입력 manifest |
| `DATA_PIPELINE` | 재현 입력 생성 | SEC PIT, 가격 스냅샷, S&P 구성, CIK·기업행동 |
| `REJECTED` | 사전 기준에서 탈락 | Rush, RSI, Form 4·가이던스 방향, 완결 사이클 실험 |
| `LEGACY_REFERENCE` | 비교에만 사용 | HERD v4·v6.1 공식과 재평가 |
| `DIAGNOSTIC` | 승격 권한 없는 감사 | 지표 인벤토리·실패 정보 감사·parser V10 종료 판정 |

V2는 파일을 상태별 명시적 chain에 한 번만 넣는다. 같은 파일이 두 상태에
들어가거나 v4·v6.1이 `LEGACY_REFERENCE_ONLY`가 아니면 검증이 실패한다.
신규 모델은 레거시 공식이나 탈락 가설을 import할 수 없다.

`research_artifact_inventory_v1.json`은 `data/herd`의 JSON,
`data/reports`의 JSON·CSV·Markdown, `docs`의 Markdown 파일명을 고정한다.
새 산출물·삭제·상태 변경이 생기면 기본 검증은 실패한다. 내용을 검토하고
카탈로그 분류를 갱신한 뒤에만
`python -m herd.research_artifact_catalog --refresh-inventory`로 원장을
갱신한다. 기존 미분류 파일은 삭제 후보가 아니라 `REVIEW_REQUIRED`로 남는다.

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

FINRA 공매도 잔고는 공식 원본 122개를 해시 고정했지만 장기 OOS 기간이
부족하다. 표적 25개 기업의 SEC 표지 3,569건을 추가 고정했고, lifecycle
분모로 기존 51개 98.22%, 독립 388개 97.55%, 현재 참고군 503개
97.67%를 연결했다. 다만 APO·CRH·DHI·DOV·DOW 5개는 개별 95%에
미달하므로 명시적 blocker로 남는다.

최신 FINRA snapshot은 현재 reference CIK로 503개를 연결하지만 이 경로는
prospective 현재 시점에만 허용한다. 과거 날짜에 소급할 수 없다. Form 4,
SEC guidance, FINRA 최신 source fact를 합친 통합 패널도 가격·수익률·
방향 라벨 없이 shadow 관측만 수행한다. 이들은 예측력이나 HERD 반영을
증명하지 않는다.

SEC 13F는 공식 bulk 53개와 대표 보통주 식별 원장을 거쳐 PIT 보유
원장으로 정규화했다. 로컬 SQLite에는 269,600개 filing, 원시 보유
22,870,933행, amendment 적용 후 유효 상태 22,993,808행이 있다.
Git에는 DB를 넣지 않고 `sec_13f_pit_holdings_v1.json`과
`sec_13f_amendment_audit_v1.csv`만 고정한다. 이어서 결과 비사용 층화
표본 224건을 SEC complete submission 원문과 대조해 224건 모두
일치했고 Wilson 95% 하한 98.31%, 원문 해시 불일치 0건으로 검수
게이트를 통과했다. 13F는 검증된 `DATA_PIPELINE` 입력이지만 아직
행동 증거가 아니다.

13F 느린 맥락은 불완전한 2013년 1분기를 제외한 52개 분기를 공통 공개
wave로 집계했다. 438개 중 435개 ticker가 70% coverage를 충족한다.
reporting-manager breadth·신규·이탈·집중도·HHI만 허용하며 분할 보정
없는 총 주식 수 변화는 차단한다. 이 산출물도 `DATA_PIPELINE`이고,
가격 결과를 사용한 방향성 증거는 다음 독립 OOS 단계에서만 판정한다.

삭제는 import·문서 참조, 고정 hash 입력, 실험 재현 필요성을 모두 확인하고
회귀 테스트를 통과한 파일에만 허용한다. 분류되지 않은 새 파일은 자동 삭제
대상이 아니라 `REVIEW_REQUIRED`다.

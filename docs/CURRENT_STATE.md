# HerdSignal 현재 상태

갱신일: 2026-08-05

판정: `STATE_OBSERVATION_MVP_READY` / `NO_ADOPTABLE_ACTION_CANDIDATE`

이 문서는 사람이 읽는 현재 상태의 유일한 정본이다. 상세 수치는
`data/tools/current_state_audit.py`가 검증한 JSON 산출물을 따르고, 과거 연구
과정은 `HERD_RESEARCH_STATUS.md`에서만 보존한다.

## 서비스 목적

HerdSignal은 사용자가 직접 고른 미국 주식을 장기 보유할 때 독립적인
시장·기업·기대·정보·포트폴리오 근거를 분리해 보여주고, 마지막에 수석
트레이더처럼 충돌·공백·위험까지 종합하는 개인 판단 보조 서비스다.

목표는 매매 신호를 많이 만드는 것이 아니다. 다음 질문에 정직하게 답한다.

1. 장기 보유 논리가 지금도 유지되는가?
2. 새로운 정보가 기존 판단을 실제로 바꾸는가?
3. 행동하지 않는 편이 더 나은가?
4. 검증된 근거가 있을 때만 소규모 추가매수·부분 익절을 검토할 수 있는가?

추천 종목 선정, 단기 가격 예측, AI가 만든 목표가, 자동 주문은 범위 밖이다.

## 현재 사용할 수 있는 기능

- SPY와 개별 종목의 `HERD_STATE_S1`, `HERD_TRANSITION_S1` 관찰
- 대시보드 검색, 보유·관심 종목, 가격·HERD 이력
- 기업 정보, 개인 판단 기록, 판단 원장 무결성 확인
- SEC PIT 원시 기업 사실과 검수된 경영진 가이던스의 제한적 표시
- SPY·섹터·종목 고유 가격 경로의 동시점 설명
- 현재 주식·현금 비중과 사용자가 정한 전체 주식 목표 차이
- 데이터 부족, `NO_VIEW`, 근거 충돌과 veto의 명시적 표시

HERD State는 시장·군중 상태이지 매수·매도 방향 점수가 아니다.

## 현재 권한

| 항목 | 상태 |
| --- | --- |
| 기본 행동 | `HOLD` |
| 운영 행동 비율 | `0%` |
| 채택된 매수·익절 후보 | 0개 |
| 독립 OOS 방향 증거 | 0개 |
| Blind holdout 접근 | 0회 |
| 자동 주문 | 비활성화 |

검증되지 않은 영역을 합산 점수나 다수결로 바꾸지 않는다. 개인 포트폴리오는
객관적 종목 판단 뒤에만 결합하며 AI에 전송하지 않는다.

## 최종 판단 구조

```text
독립 원천 데이터
    ↓
시점·품질 검증
    ↓
기업 체력 | 기대·가격 | 시장·섹터 | 차트·군중 | 정보 변화
    ↓                         (각 영역은 자기 근거만 사용)
증거 입장 게이트
    ↓
수석 트레이더 종합 판단
    ↓
개인 포트폴리오 번역 + 독립 위험 veto
    ↓
판단 원장과 사후 결과 귀속
```

현재는 이 구조의 데이터 신뢰성과 증거 입장 게이트를 구축하는 단계다. 수석
트레이더 계층은 검증되지 않은 입력을 평균 내거나 새로운 사실을 만들 수 없다.

## 현재 구현 단계

SEC 8-K 중요 사건 947건 가운데 filing 시점 식별이 연결된 사건은 301건,
미연결은 646건이다.

- 독립 구조적 표지 평가: 182/182 원문 검수 `VALID`
- Wilson 95% 정밀도 하한: 0.9793, 사전 기준 0.90 통과
- exact filing date 식별 승격: 116건
- 현재 ticker 소급 입력과 열린 ticker 기간 추론: 금지
- 2019년 이전 미연결: 646건·198 issuer·20개 배치
- B001: 10 issuer·70개 사건의 SEC submissions metadata 수집 완료
- B001 periodic filing 후보: 769건

SEC metadata는 원문 선택용 인덱스일 뿐 ticker 식별 증거가 아니다. 다음 단계는
`SELECT_B001_PERIODIC_PRIMARY_DOCUMENTS_FOR_IDENTITY_REVIEW`다.

이 작업은 중요 공시의 기업 식별 신뢰성을 높이지만 그 자체로 가격 방향이나
매매 권한을 만들지 않는다.

## 문서와 데이터 정본

- 서비스 목적·최종 구조: `HERD_LONG_TERM_OPERATING_SYSTEM.md`
- 현재 상태·다음 단계: 이 문서
- 제품 제공 범위: `PRODUCT_SCOPE.md`
- 승격 기준: `HERD_ADOPTION_POLICY.md`
- 재현 명령·입력 계약: `HERD_REPRODUCIBLE_RESEARCH.md`
- 과거 연구 판정: `HERD_RESEARCH_STATUS.md` — 현재 상태로 사용 금지
- 기계 판독 상태: `data/tools/current_state_audit.py`와 `data/reports/*.json`

## 확인 명령

```bash
./scripts/audit-current-state.sh
./scripts/verify-fast.sh
```

세부 연구 단계의 재현 명령은 이 문서에 반복하지 않는다.

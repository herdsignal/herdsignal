# 차세대 HERD Blind Holdout 판정

상태: `NOT_OPENED_PREREQUISITES_FAILED`  
평가 횟수: `0`  
봉인 데이터 접근: `없음`

Blind holdout은 모델을 개선하는 구간이 아니라 모든 결정을 끝낸 후보를 단
한 번 판정하는 구간이다. 현재는 다음 세 전제조건이 모두 실패했다.

1. B0~B4 중 사전 채택 기준을 통과한 후보가 없다.
2. PIT 재무·과거 유니버스·상장폐지 데이터가 준비되지 않았다.
3. 차세대 후보의 시간축 Walk-forward와 시대별 검증이 완료되지 않았다.

따라서 holdout을 열어 우연히 좋은 후보를 찾지 않는다. 기존 v6.1에 사용한
`data/reports/validation_v2/blind_holdout.json`도 차세대 후보에 재사용할
수 없다.

차세대 holdout ID는 아직 배정하지 않았고 평가 횟수는 0회로 유지한다.
후보가 모든 pre-holdout 기준을 통과한 뒤 별도 데이터 구간을 지정해야
`READY_TO_OPEN`이 될 수 있다. 이 상태도 자동 평가나 운영 승격을 뜻하지
않는다.

기계 판독 결과는
`data/reports/blind_holdout_decision_vnext.json`에 저장한다.

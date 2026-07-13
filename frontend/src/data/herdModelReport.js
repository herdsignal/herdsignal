/**
 * herdModelReport.js — HERD Lab 표시용 모델 검증 리포트 데이터
 */

const herdModelReport = {
  model: {
    version: 'HERD_v6.1',
    name: 'Validated Progressive Action Layer',
    base: 'HERD_v4 score + v5 validation',
    status: 'RESEARCH_VALIDATION',
    release: 'Phase 3',
    source: 'data/herd/backtest_action_layer.py · ActionDecisionService',
    period: '10년',
  },
  metrics: [
    { label: 'OOS 수익 개선', value: '36.4%', sub: '440개 Walk-forward 구간', tone: 'blue' },
    { label: 'OOS MDD 개선', value: '+1.3%p', sub: '중앙값', tone: 'green' },
    { label: '운영 점수', value: 'v4', sub: '상태 점수', tone: 'slate' },
    { label: '행동 레이어', value: 'v6.1', sub: '연구 검증 중', tone: 'orange' },
  ],
  trustChecks: [
    { label: '검증 유니버스', value: '55종목', sub: '11개 섹터·지수' },
    { label: '통과 기준', value: '60%+', sub: '수익률 보존 하한' },
    { label: '행동 범위', value: '2-12회', sub: '연간 과매매 방지' },
    { label: '현재 상태', value: '연구', sub: '채택 기준 미달' },
  ],
  modelNotes: [
    'HERD v4는 운영 상태 점수이고 v6.1 Action Layer는 아직 연구 검증 중입니다.',
    'Walk-forward OOS 440구간에서 기존 모델 대비 수익 개선 비율 36.4%, MDD 개선 중앙값 1.3%p로 채택 기준에 미달했습니다.',
    '신규 종목은 종목별 신뢰도 표본이 쌓이기 전까지 참고용으로 봅니다.',
    '표시되는 행동은 확정 매매 추천이 아니라 장기투자 판단을 돕는 연구 정보입니다.',
  ],
  rows: [
    { ticker: 'NVDA', buyHold: '+16,667.5%', action: '+6,196.5%', capture: '37.2%', mdd: '+10.3%p', actions: '9.0/년', verdict: '방어 우선', tone: 'watch' },
    { ticker: 'MSFT', buyHold: '+762.3%', action: '+709.5%', capture: '93.1%', mdd: '+3.8%p', actions: '8.7/년', verdict: '우수', tone: 'pass' },
    { ticker: 'AAPL', buyHold: '+1,325.8%', action: '+1,088.6%', capture: '82.1%', mdd: '+0.6%p', actions: '8.2/년', verdict: '수익 보존', tone: 'pass' },
    { ticker: 'JPM', buyHold: '+626.5%', action: '+422.2%', capture: '67.4%', mdd: '+6.8%p', actions: '8.4/년', verdict: '방어 개선', tone: 'pass' },
    { ticker: 'SPY', buyHold: '+319.1%', action: '+227.5%', capture: '71.3%', mdd: '+5.8%p', actions: '8.3/년', verdict: '기준 통과', tone: 'pass' },
  ],
  stages: [
    { stage: 'Flee', range: '0-15', action: '추가매수', ratio: '8-22%', tone: 'flee' },
    { stage: 'Scatter', range: '15-40', action: '분할매수', ratio: '0-4%', tone: 'scatter' },
    { stage: 'Calm', range: '40-60', action: '보유', ratio: '0%', tone: 'calm' },
    { stage: 'Drift', range: '60-75', action: '소폭 익절', ratio: '2-6%', tone: 'drift' },
    { stage: 'Rush', range: '75-100', action: '일부 익절', ratio: '5-30%', tone: 'rush' },
  ],
  weights: [
    { label: '월봉 RSI', value: 24 },
    { label: '200주 MA 위치', value: 20 },
    { label: '주봉 RSI', value: 19 },
    { label: '52주 위치', value: 19 },
    { label: 'MA200 이격도', value: 18 },
  ],
}

export default herdModelReport

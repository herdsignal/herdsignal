/**
 * herdModelReport.js — HERD Lab 표시용 모델 검증 리포트 데이터
 */

const herdModelReport = {
  model: {
    version: 'HERD_v5',
    name: 'Balanced Action Layer',
    base: 'HERD_v4 score',
    status: 'MVP 검증 중',
    release: 'Phase 3',
    source: 'data/herd/backtest_action_layer.py',
    period: '10년',
  },
  metrics: [
    { label: '수익률 보존', value: '70.2%', sub: 'HERD_v5 기준', tone: 'blue' },
    { label: 'MDD 개선', value: '+5.5%p', sub: 'B&H 대비', tone: 'green' },
    { label: '연평균 행동', value: '8.5회', sub: '10년 평균', tone: 'slate' },
    { label: '표본', value: '5종목', sub: 'NVDA/MSFT/AAPL/JPM/SPY', tone: 'orange' },
  ],
  rows: [
    { ticker: 'NVDA', buyHold: '+16,667.5%', action: '+6,196.5%', capture: '37.2%', mdd: '+10.3%p', actions: '9.0/년' },
    { ticker: 'MSFT', buyHold: '+762.3%', action: '+709.5%', capture: '93.1%', mdd: '+3.8%p', actions: '8.7/년' },
    { ticker: 'AAPL', buyHold: '+1,325.8%', action: '+1,088.6%', capture: '82.1%', mdd: '+0.6%p', actions: '8.2/년' },
    { ticker: 'JPM', buyHold: '+626.5%', action: '+422.2%', capture: '67.4%', mdd: '+6.8%p', actions: '8.4/년' },
    { ticker: 'SPY', buyHold: '+319.1%', action: '+227.5%', capture: '71.3%', mdd: '+5.8%p', actions: '8.3/년' },
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

herdModelReport.checks = [
  ['현재 모델', `${herdModelReport.model.version} · ${herdModelReport.model.name}`],
  ['기반 점수', herdModelReport.model.base],
  ['목표', '수익률 70%+ 보존 / MDD 5%p+ 개선'],
  ['상태', herdModelReport.model.status],
]

export default herdModelReport

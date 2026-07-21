/**
 * herdModelReport.js — HERD Lab 표시용 모델 검증 리포트 데이터
 */

const herdModelReport = {
  model: {
    name: 'Validated Progressive Action Layer',
    base: 'HERD_v4 score + v5 validation',
  },
  stages: [
    { stage: 'Flee', range: '0-15', action: '추가매수', ratio: '8-22%', tone: 'flee' },
    { stage: 'Scatter', range: '15-40', action: '분할매수', ratio: '0-4%', tone: 'scatter' },
    { stage: 'Calm', range: '40-60', action: '보유', ratio: '0%', tone: 'calm' },
    { stage: 'Drift', range: '60-75', action: '쏠림 관찰', ratio: '행동 미채택', tone: 'drift' },
    { stage: 'Rush', range: '75-100', action: '밀집 관찰', ratio: '행동 미채택', tone: 'rush' },
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

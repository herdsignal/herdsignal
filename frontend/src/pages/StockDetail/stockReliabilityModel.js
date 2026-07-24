export function fmtReliabilityScore(value) {
  if (value == null) return '—'
  const number = Number(value)
  return Number.isFinite(number) ? `${Math.round(number)}/100` : '—'
}

export function sampleQualityLabel(value) {
  switch (value) {
    case 'HIGH': return '충분'
    case 'MEDIUM': return '보통'
    case 'LOW': return '부족'
    default: return '—'
  }
}

export function signalEdgeLabel(value) {
  switch (value) {
    case 'POSITIVE': return '우위'
    case 'NEUTRAL': return '중립'
    case 'NEGATIVE': return '약함'
    case 'INSUFFICIENT': return '표본 부족'
    default: return '—'
  }
}

export function signalEdgeTone(value) {
  switch (value) {
    case 'POSITIVE': return 'buy'
    case 'NEGATIVE': return 'sell'
    default: return 'neutral'
  }
}

export function actionTone(grade, signal) {
  if (grade === 'STRONG_ACTION') return signal === 'SELL' ? 'var(--rush)' : 'var(--flee)'
  if (grade === 'ACTION') return signal === 'SELL' ? 'var(--drift)' : 'var(--scatter)'
  if (grade === 'WATCH') return 'var(--calm)'
  return 'var(--text-3)'
}

export function reliabilityTone(grade) {
  switch (grade) {
    case 'STRONG': return 'var(--flee)'
    case 'GOOD': return 'var(--scatter)'
    case 'WATCH': return 'var(--drift)'
    case 'DATA_LIMITED': return 'var(--text-3)'
    default: return 'var(--calm)'
  }
}

export function fmtReliabilityPct(value, suffix = '%') {
  if (value == null) return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number >= 0 ? '+' : ''}${number.toFixed(1)}${suffix}`
}

export function fmtReliabilityPlainPct(value) {
  if (value == null) return '—'
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(0)}%` : '—'
}

export function fmtAnnualActions(value) {
  if (value == null) return '—'
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(1)}회` : '—'
}

export function currentSignalReliability(herdData, reliability) {
  if (!reliability) return null
  const signal = herdData?.signal
  if (signal === 'BUY' || signal === 'ADD') {
    return {
      label: '현재 매수 신호',
      value: reliability.fleeHitRate,
      sample: reliability.fleeSampleSize,
      caption: `매수 edge ${signalEdgeLabel(reliability.buySignalEdge)}`,
    }
  }
  if (signal === 'SELL' || signal === 'REDUCE') {
    return {
      label: '현재 익절 신호',
      value: reliability.rushHitRate,
      sample: reliability.rushSampleSize,
      caption: `익절 edge ${signalEdgeLabel(reliability.sellSignalEdge)}`,
    }
  }
  return {
    label: '종목별 모델 적합도',
    value: reliability.fitScore,
    sample: reliability.totalSignalSamples,
    caption: `표본 품질 ${sampleQualityLabel(reliability.sampleQuality)}`,
    scoreValue: true,
  }
}

export function reliabilityEvidenceItems(reliability) {
  if (!reliability) return []
  return [
    ['매수 후 1M', reliability.buyReturn1m, 'Flee/Scatter 평균', 'return'],
    ['매수 후 3M', reliability.buyReturn3m, 'Flee/Scatter 평균', 'return'],
    ['매수 후 6M', reliability.buyReturn6m, 'Flee/Scatter 평균', 'return'],
    ['익절 후 1M', reliability.sellDrawdown1m, 'Drift/Rush 평균 저점', 'drawdown'],
    ['익절 후 3M', reliability.sellDrawdown3m, 'Drift/Rush 평균 저점', 'drawdown'],
  ].map(([label, value, caption, kind]) => ({
    label,
    value: fmtReliabilityPct(value),
    caption,
    tone: kind === 'return'
      ? (Number(value) >= 0 ? 'buy' : 'sell')
      : (Number(value) <= 0 ? 'sell' : 'neutral'),
  })).concat([
    {
      label: '매수 edge',
      value: signalEdgeLabel(reliability.buySignalEdge),
      caption: `${reliability.fleeSampleSize ?? 0}회 표본`,
      tone: signalEdgeTone(reliability.buySignalEdge),
    },
    {
      label: '익절 edge',
      value: signalEdgeLabel(reliability.sellSignalEdge),
      caption: `${reliability.rushSampleSize ?? 0}회 표본`,
      tone: signalEdgeTone(reliability.sellSignalEdge),
    },
  ])
}

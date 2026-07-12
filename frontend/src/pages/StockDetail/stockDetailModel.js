/* 환경변수에서 API 호스트 추출 — 에러 메시지 표시용 */
export const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

/*
 * ── HERD v3 지표 정의 (가중치 순) ─────────────
 *
 * weight: HERD 점수 산출 시 반영 비율 (%)
 * min/max: 바 너비 정규화 기준. ma200Deviation은 ±50% 기준
 */
export const INDICATORS = [
  { key: 'monthlyRsi',     label: '월봉 RSI',       weight: 24, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'ma200Weekly',    label: '200주 MA 위치',  weight: 20, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'weeklyRsi',      label: '주봉 RSI',       weight: 19, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'position52w',    label: '52주 위치',      weight: 19, min: 0,   max: 100, unit: '%', signed: false },
  { key: 'ma200Deviation', label: 'MA200 이격도',   weight: 18, min: -50, max: 50,  unit: '%', signed: true  },
]

export const HISTORY_PERIODS = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '1y', label: '1Y' },
  { value: '3y', label: '3Y' },
]

/* ── 유틸 ─────────────────────────────────── */

/** herdStage 정규화: "Herd Scatter" → "scatter" */
export function normalizeStage(stage) {
  const s = (stage || '').toLowerCase()
  return s.startsWith('herd ') ? s.slice(5) : s
}

/** 단계 → CSS 변수 색상 */
export function stageColor(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return 'var(--rush)'
    case 'drift':   return 'var(--drift)'
    case 'scatter': return 'var(--scatter)'
    case 'flee':    return 'var(--flee)'
    default:        return 'var(--calm)'
  }
}

/** signal → 배지 배경/텍스트 색 */
export function signalStyle(signal) {
  switch (signal) {
    case 'SELL':   return { bg: 'rgba(239,68,68,0.1)',   color: 'var(--rush)' }
    case 'REDUCE': return { bg: 'rgba(249,115,22,0.1)',  color: 'var(--drift)' }
    case 'HOLD':   return { bg: 'rgba(113,113,122,0.1)', color: 'var(--calm)' }
    case 'ADD':    return { bg: 'rgba(96,165,250,0.1)',  color: 'var(--scatter)' }
    case 'BUY':    return { bg: 'rgba(59,130,246,0.12)', color: 'var(--flee)' }
    default:       return { bg: 'rgba(113,113,122,0.1)', color: 'var(--calm)' }
  }
}

/** stage → 티커 배지 배경/텍스트 색 */
export function badgeColors(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return { background: 'rgba(239,68,68,0.12)',   color: 'var(--rush)' }
    case 'drift':   return { background: 'rgba(249,115,22,0.12)',  color: 'var(--drift)' }
    case 'scatter': return { background: 'rgba(96,165,250,0.12)',  color: 'var(--scatter)' }
    case 'flee':    return { background: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:        return { background: 'rgba(113,113,122,0.12)', color: 'var(--calm)' }
  }
}

/** score → Timing Signal 텍스트 */
export function getTimingSignal(score) {
  if (score >= 75) return '보유량의 30% 익절을 고려하세요'
  if (score >= 60) return '보유량의 5% 부분 익절 구간입니다'
  if (score >= 40) return '현재 비중을 유지하세요'
  if (score >= 15) return '분할 매수를 시작할 수 있는 구간입니다'
  return '적극적 추가매수 구간입니다'
}

/** 지표 값 → 바 너비 % (0~100, min~max 범위 정규화) */
export function normalizeBar(value, min, max) {
  return Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
}

/** 지표 값 → 표시 문자열 */
export function formatIndicator(value, unit, signed) {
  const fixed = value.toFixed(1)
  return signed && value > 0 ? `+${fixed}${unit}` : `${fixed}${unit}`
}

export function formatMultiplier(value) {
  if (value == null) return '×1.00'
  return `×${Number(value).toFixed(2)}`
}

export function epsMultiplierDesc(value) {
  const n = Number(value ?? 1)
  if (n <= 0.85) return '4연속 beat'
  if (n <= 0.90) return '3연속 beat'
  if (n <= 0.95) return '2연속 beat'
  if (n >= 1.15) return '4연속 miss'
  if (n >= 1.10) return '3연속 miss'
  if (n >= 1.05) return '2연속 miss'
  return '중립'
}

export function sectorMultiplierDesc(value) {
  const n = Number(value ?? 1)
  if (n <= 0.90) return '섹터 대비 강한 우위'
  if (n <= 0.95) return '섹터 대비 우위'
  if (n >= 1.10) return '섹터 대비 뚜렷한 약세'
  if (n >= 1.05) return '섹터 약세'
  return '중립'
}

export function formatActionScore(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `강도 ${Math.round(n)}`
}

export function formatActionRatio(value) {
  const n = Number(value ?? 0)
  if (n <= 0) return '관찰'
  return `${Math.round(n * 100)}%`
}

export function formatActionBasis(data) {
  const ratio = Number(data?.actionRatio ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return '현재 비중 유지'

  const pct = Math.round(ratio * 100)
  if (data?.signal === 'BUY' || data?.signal === 'ADD') {
    return `목표 투자금 기준 ${pct}% 분할 투입`
  }
  if (data?.signal === 'SELL' || data?.signal === 'REDUCE') {
    return `보유 평가금액 기준 ${pct}% 축소`
  }
  return '현재 비중 유지'
}

export function formatActionMeta(data) {
  return [
    data?.actionModelVersion ?? 'HERD_v6.1',
    formatActionScore(data?.actionScore),
  ].filter(Boolean).join(' · ')
}

export function fmtReliabilityScore(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${Math.round(n)}/100`
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

export function evidenceTone(type) {
  switch (type) {
    case 'buy': return 'var(--flee)'
    case 'sell': return 'var(--rush)'
    case 'warning': return 'var(--drift)'
    default: return 'var(--calm)'
  }
}

export function buildSignalEvidence(data) {
  if (!data) return []

  const items = []
  const push = (label, value, caption, type = 'neutral') => {
    if (value == null) return
    if (typeof value !== 'string' && Number.isNaN(Number(value))) return
    items.push({
      label,
      value: typeof value === 'string' ? value : Math.round(Number(value)),
      caption,
      type,
    })
  }

  const monthlyRsi = Number(data.monthlyRsi)
  const weeklyRsi = Number(data.weeklyRsi)
  const position52w = Number(data.position52w)
  const ma200Weekly = Number(data.ma200Weekly)
  const ma200Deviation = Number(data.ma200Deviation)
  const epsMultiplier = Number(data.epsMultiplier ?? 1)
  const sectorMultiplier = Number(data.sectorMultiplier ?? 1)

  if (monthlyRsi <= 30) push('월봉 RSI', monthlyRsi, '장기 심리 하단', 'buy')
  else if (monthlyRsi >= 70) push('월봉 RSI', monthlyRsi, '장기 심리 상단', 'sell')

  if (weeklyRsi <= 30) push('주봉 RSI', weeklyRsi, '중기 과매도권', 'buy')
  else if (weeklyRsi >= 70) push('주봉 RSI', weeklyRsi, '중기 과열권', 'sell')

  if (position52w <= 30) push('52주 위치', `${position52w.toFixed(1)}%`, '연중 하단권', 'buy')
  else if (position52w >= 70) push('52주 위치', `${position52w.toFixed(1)}%`, '연중 상단권', 'sell')

  if (ma200Weekly <= 30) push('200주 MA', ma200Weekly, '장기 추세 하단', 'buy')
  else if (ma200Weekly >= 70) push('200주 MA', ma200Weekly, '장기 추세 상단', 'sell')

  if (ma200Deviation <= 30) push('MA200 이격', ma200Deviation, '장기선 대비 눌림', 'buy')
  else if (ma200Deviation >= 70) push('MA200 이격', ma200Deviation, '장기선 대비 과열', 'sell')

  if (epsMultiplier < 1) {
    items.push({
      label: 'EPS 보정',
      value: formatMultiplier(epsMultiplier),
      caption: epsMultiplierDesc(epsMultiplier),
      type: 'buy',
    })
  } else if (epsMultiplier > 1) {
    items.push({
      label: 'EPS 보정',
      value: formatMultiplier(epsMultiplier),
      caption: epsMultiplierDesc(epsMultiplier),
      type: 'warning',
    })
  }

  if (sectorMultiplier < 1) {
    items.push({
      label: '섹터 강도',
      value: formatMultiplier(sectorMultiplier),
      caption: sectorMultiplierDesc(sectorMultiplier),
      type: 'buy',
    })
  } else if (sectorMultiplier > 1) {
    items.push({
      label: '섹터 강도',
      value: formatMultiplier(sectorMultiplier),
      caption: sectorMultiplierDesc(sectorMultiplier),
      type: 'warning',
    })
  }

  if (items.length === 0) {
    items.push({
      label: 'HERD 균형',
      value: Math.round(data.herdV4 ?? data.herdScore ?? 50),
      caption: '강한 쏠림 없음',
      type: 'neutral',
    })
  }

  return items.slice(0, 5)
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
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}${suffix}`
}

export function fmtReliabilityPlainPct(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toFixed(0)}%`
}

export function fmtAnnualActions(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toFixed(1)}회`
}

export function fmtCurrencyCompact(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  if (Math.abs(n) >= 1_000_000_000_000) return `$${(n / 1_000_000_000_000).toFixed(1)}T`
  if (Math.abs(n) >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  return `$${Math.round(n).toLocaleString()}`
}

export function fmtNumber(value, digits = 1) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toFixed(digits)
}

export function fmtFinancePct(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toFixed(1)}%`
}

export function fundamentalTone(level) {
  switch (level) {
    case 'CLEAR': return 'var(--scatter)'
    case 'CAUTION': return 'var(--drift)'
    case 'RISK': return 'var(--rush)'
    default: return 'var(--text-3)'
  }
}

export function evaluateFundamentalGuard(financials, herdData) {
  if (!financials) {
    return {
      level: 'LIMITED',
      label: '재무 데이터 제한',
      summary: '제한된 재무 데이터 기준으로 판단을 보류합니다.',
      reasons: ['핵심 재무 지표를 불러오지 못했습니다.'],
    }
  }

  const eps = Number(financials.eps)
  const pe = Number(financials.trailingPe)
  const margin = Number(financials.operatingMargin)
  const revenue = Number(financials.totalRevenue)
  const marketCap = Number(financials.marketCap)
  const isBuySignal = herdData?.signal === 'BUY' || herdData?.signal === 'ADD'
  const isSellSignal = herdData?.signal === 'SELL' || herdData?.signal === 'REDUCE'
  const risks = []
  const cautions = []

  if (!Number.isFinite(revenue) || revenue <= 0) cautions.push('매출 데이터 확인 필요')
  if (!Number.isFinite(marketCap) || marketCap <= 0) cautions.push('시가총액 데이터 확인 필요')
  if (!Number.isFinite(eps)) cautions.push('EPS 데이터 확인 필요')
  if (Number.isFinite(eps) && eps < 0) cautions.push('EPS 적자')
  if (!Number.isFinite(margin)) cautions.push('영업이익률 데이터 확인 필요')
  if (Number.isFinite(margin) && margin < 0) cautions.push('영업이익률 음수')
  if (Number.isFinite(pe) && pe >= 80) cautions.push('PER 80 이상')
  if (!Number.isFinite(pe) && (!Number.isFinite(eps) || eps <= 0)) cautions.push('PER 산정 불가')

  if (Number.isFinite(eps) && eps < 0 && Number.isFinite(margin) && margin < 0) {
    risks.push('적자와 영업손실 동시 확인')
  }
  if ((!Number.isFinite(revenue) || revenue <= 0) && Number.isFinite(eps) && eps < 0) {
    risks.push('매출 공백과 EPS 적자 동시 확인')
  }
  if (isSellSignal && Number.isFinite(pe) && pe >= 100) {
    risks.push('고PER 구간의 Rush/Drift 신호')
  }

  const level = risks.length > 0 ? 'RISK' : cautions.length > 0 ? 'CAUTION' : 'CLEAR'
  const label = level === 'RISK'
    ? '재무 리스크 큼'
    : level === 'CAUTION'
      ? '재무 확인 필요'
      : '확인된 주요 경고 없음'

  let summary = '제한된 주요 재무 지표에서 큰 경고는 확인되지 않습니다.'
  if (isBuySignal && level === 'CLEAR') {
    summary = '매수 신호를 재무 데이터가 크게 방해하지 않습니다.'
  } else if (isBuySignal && level === 'CAUTION') {
    summary = '매수 신호지만 포지션 크기를 줄여 접근해야 합니다.'
  } else if (isBuySignal && level === 'RISK') {
    summary = '저점 신호만으로 매수 판단하지 마세요.'
  } else if (isSellSignal && level !== 'CLEAR') {
    summary = '익절 신호를 더 보수적으로 볼 구간입니다.'
  } else if (level === 'CAUTION') {
    summary = 'HERD 신호와 별도로 재무 지표 확인이 필요합니다.'
  } else if (level === 'RISK') {
    summary = 'HERD 신호보다 재무 리스크 확인을 우선해야 합니다.'
  }

  return {
    level,
    label,
    summary,
    reasons: [...risks, ...cautions].slice(0, 3),
  }
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
    {
      label: '매수 후 1M',
      value: fmtReliabilityPct(reliability.buyReturn1m),
      caption: 'Flee/Scatter 평균',
      tone: Number(reliability.buyReturn1m) >= 0 ? 'buy' : 'sell',
    },
    {
      label: '매수 후 3M',
      value: fmtReliabilityPct(reliability.buyReturn3m),
      caption: 'Flee/Scatter 평균',
      tone: Number(reliability.buyReturn3m) >= 0 ? 'buy' : 'sell',
    },
    {
      label: '매수 후 6M',
      value: fmtReliabilityPct(reliability.buyReturn6m),
      caption: 'Flee/Scatter 평균',
      tone: Number(reliability.buyReturn6m) >= 0 ? 'buy' : 'sell',
    },
    {
      label: '익절 후 1M',
      value: fmtReliabilityPct(reliability.sellDrawdown1m),
      caption: 'Drift/Rush 평균 저점',
      tone: Number(reliability.sellDrawdown1m) <= 0 ? 'sell' : 'neutral',
    },
    {
      label: '익절 후 3M',
      value: fmtReliabilityPct(reliability.sellDrawdown3m),
      caption: 'Drift/Rush 평균 저점',
      tone: Number(reliability.sellDrawdown3m) <= 0 ? 'sell' : 'neutral',
    },
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
  ]
}

export function journalActionLabel(type) {
  switch (type) {
    case 'BUY': return '매수 기록'
    case 'HOLD': return '보류 기록'
    case 'SELL': return '익절 기록'
    default: return '판단 기록'
  }
}

/* ── 버튼 레이블 매핑 ─────────────────────── */
export const BTN_LABELS = {
  portfolio: {
    idle:    '포트폴리오 추가',
    loading: '추가 중…',
    added:   '추가됨 ✓',
    exists:  '이미 추가됨',
  },
  watchlist: {
    idle:    '관심종목 추가',
    loading: '추가 중…',
    added:   '추가됨 ✓',
    exists:  '이미 추가됨',
  },
}


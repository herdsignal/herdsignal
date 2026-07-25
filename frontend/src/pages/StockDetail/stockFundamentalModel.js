export function fmtCurrencyCompact(value) {
  if (value == null) return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  if (Math.abs(number) >= 1_000_000_000_000) return `$${(number / 1_000_000_000_000).toFixed(1)}T`
  if (Math.abs(number) >= 1_000_000_000) return `$${(number / 1_000_000_000).toFixed(1)}B`
  if (Math.abs(number) >= 1_000_000) return `$${(number / 1_000_000).toFixed(1)}M`
  return `$${Math.round(number).toLocaleString()}`
}

export function fmtNumber(value, digits = 1) {
  if (value == null) return '—'
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(digits) : '—'
}

export function fmtFinancePct(value) {
  if (value == null) return '—'
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(1)}%` : '—'
}

export function fundamentalTone(level) {
  switch (level) {
    case 'CLEAR': return 'var(--hs-scatter)'
    case 'CAUTION': return 'var(--hs-drift)'
    case 'RISK': return 'var(--hs-rush)'
    default: return 'var(--hs-text-muted)'
  }
}

export function evaluateFundamentalGuard(financials) {
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
  const level = risks.length ? 'RISK' : cautions.length ? 'CAUTION' : 'CLEAR'
  const label = level === 'RISK'
    ? '재무 리스크 큼'
    : level === 'CAUTION' ? '재무 확인 필요' : '확인된 주요 경고 없음'

  const summary = level === 'RISK'
    ? '적자·영업손실 등 핵심 위험 항목이 확인됐습니다.'
    : level === 'CAUTION'
      ? '확인되지 않았거나 주의가 필요한 항목이 있습니다.'
      : '조회된 주요 재무 지표에 경고가 없습니다.'

  return { level, label, summary, reasons: [...risks, ...cautions].slice(0, 3) }
}

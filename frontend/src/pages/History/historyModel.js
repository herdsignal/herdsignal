export function fmtAxisDate(dateString) {
  const date = new Date(dateString)
  return Number.isNaN(date.getTime())
    ? dateString
    : `${date.getMonth() + 1}/${date.getDate()}`
}

export function fmtUSD(value) {
  if (value == null) return '—'
  return `$${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export function fmtPct(value) {
  if (value == null) return '—'
  const number = Number(value)
  return `${number >= 0 ? '+' : ''}${number.toFixed(2)}%`
}

export function pctColor(value) {
  if (value == null) return 'var(--text-3)'
  const number = Number(value)
  if (number > 0) return '#22C55E'
  if (number < 0) return 'var(--rush)'
  return 'var(--text-3)'
}

export function buildHistoryView(points) {
  const safePoints = Array.isArray(points) ? points : []
  if (safePoints.length === 0) {
    return { latest: null, insight: null, yDomain: [0, 1000] }
  }

  const latest = safePoints[safePoints.length - 1]
  const values = safePoints
    .map((point) => Number(point.totalValue))
    .filter(Number.isFinite)
  const minimum = values.length ? Math.min(...values) : 0
  const maximum = values.length ? Math.max(...values) : 1000
  const padding = (maximum - minimum) * 0.08 || 100
  const yDomain = [Math.max(0, minimum - padding), maximum + padding]

  if (safePoints.length < 2) return { latest, insight: null, yDomain }
  const first = safePoints[0]
  const peak = safePoints.reduce((best, point) =>
    Number(point.totalValue) > Number(best.totalValue) ? point : best
  , first)
  const drawdown = Number(latest.totalValue) && Number(peak.totalValue)
    ? (Number(latest.totalValue) / Number(peak.totalValue) - 1) * 100
    : null
  const fromStart = Number(first.totalValue) && Number(latest.totalValue)
    ? (Number(latest.totalValue) / Number(first.totalValue) - 1) * 100
    : null

  return {
    latest,
    yDomain,
    insight: { first, peak, drawdown, fromStart },
  }
}

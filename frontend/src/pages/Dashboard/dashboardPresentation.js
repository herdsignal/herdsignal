import { scoreColor, stageLabelFromScore } from '../../utils/herdStage'
import { formatInputDate } from './dashboardCache'

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

export function fmtShares(value) {
  if (value == null) return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number.toLocaleString('ko-KR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  })}주`
}

export function fmtWeightGap(row) {
  if (!row) return ''
  const gap = row.targetWeight - row.currentWeight
  if (Math.abs(gap) < 0.05) return '목표 근처'
  return gap > 0
    ? `목표까지 ${gap.toFixed(1)}%p`
    : `목표 초과 ${Math.abs(gap).toFixed(1)}%p`
}

export function pctColor(value) {
  if (value == null) return 'var(--text-3)'
  const number = Number(value)
  if (number > 0) return '#22C55E'
  if (number < 0) return '#EF4444'
  return 'var(--text-3)'
}

export function fmtTime(date) {
  if (!date) return ''
  return date.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })
}

export function fmtAxisDate(dateString) {
  const date = new Date(dateString)
  return Number.isNaN(date.getTime())
    ? dateString
    : `${date.getMonth() + 1}/${date.getDate()}`
}

export function normalizeHistoryPoint(point) {
  const investedValue = point.invested_value ?? point.investedValue ??
    point.totalValue ?? point.total_value ?? 0
  const cashBalance = point.cash_balance ?? point.cashBalance ?? 0
  const totalAssetValue = point.total_asset_value ?? point.totalAssetValue ??
    point.totalValue ?? point.total_value ?? 0
  return {
    date: point.date,
    investedValue: Number(investedValue),
    cashBalance: Number(cashBalance),
    totalAssetValue: Number(totalAssetValue),
    totalReturnPct: point.total_return_pct ?? point.totalReturnPct ?? null,
  }
}

export function currentAssetPoint(summary, cashBalance) {
  if (!summary) return null
  const investedValue = Number(summary.invested_value ?? 0)
  const cash = Number(summary.cash_balance ?? cashBalance ?? 0)
  const totalAssetValue = Number(
    summary.total_asset_value ?? summary.total_value ?? investedValue + cash
  )
  if (!Number.isFinite(totalAssetValue) || totalAssetValue <= 0) return null
  return {
    date: formatInputDate(),
    investedValue: Number.isFinite(investedValue) ? investedValue : 0,
    cashBalance: Number.isFinite(cash) ? cash : 0,
    totalAssetValue,
    totalReturnPct: summary.total_return_pct ?? null,
  }
}

export function mergeCurrentAssetPoint(history, currentPoint) {
  if (!currentPoint) return history
  const next = [...history]
  const sameDateIndex = next.findIndex((point) => point.date === currentPoint.date)
  if (sameDateIndex >= 0) next[sameDateIndex] = { ...next[sameDateIndex], ...currentPoint }
  else next.push(currentPoint)
  return next.sort((left, right) => new Date(left.date) - new Date(right.date))
}

export function fmtScoreDate(dateString, fetchTime) {
  if (!dateString) return '—'
  const nowKst = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Seoul' }))
  const pad = (number) => String(number).padStart(2, '0')
  const today = `${nowKst.getFullYear()}-${pad(nowKst.getMonth() + 1)}-${pad(nowKst.getDate())}`
  const yesterdayKst = new Date(nowKst)
  yesterdayKst.setDate(yesterdayKst.getDate() - 1)
  const yesterday = `${yesterdayKst.getFullYear()}-${pad(yesterdayKst.getMonth() + 1)}-${pad(yesterdayKst.getDate())}`

  if (dateString === today) {
    const time = fetchTime ?? new Date()
    return `오늘 ${time.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })}`
  }
  if (dateString === yesterday) return '어제'
  const date = new Date(dateString)
  return Number.isNaN(date.getTime())
    ? dateString
    : date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

export function scoreToColor(score) {
  return score == null ? 'var(--text-1)' : scoreColor(score)
}

export function scoreToStage(score) {
  return stageLabelFromScore(score, true)
}

export function averageScoreForLastDays(points, days, fallbackScore = null) {
  if (!points?.length) return null
  const now = new Date()
  const cutoff = new Date(now)
  cutoff.setDate(cutoff.getDate() - days)
  const values = []
  for (const point of points) {
    const pointDate = new Date(`${point.date}T00:00:00`)
    if (Number.isNaN(pointDate.getTime())) continue
    if (pointDate >= cutoff && pointDate <= now && point.score != null) {
      values.push(Number(point.score))
    }
  }
  if (values.length === 0) {
    const latest = points[points.length - 1]
    const score = fallbackScore ?? latest?.score
    return score == null ? null : { score }
  }
  return { score: values.reduce((sum, value) => sum + value, 0) / values.length }
}

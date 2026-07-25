export const ASSET_HISTORY_PERIODS = [
  { value: 'month', label: '1개월' },
  { value: 'year', label: '1년' },
  { value: 'all', label: '전체' },
]

function formatInputDate(value) {
  const date = value ? new Date(value) : new Date()
  if (Number.isNaN(date.getTime())) return ''
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
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

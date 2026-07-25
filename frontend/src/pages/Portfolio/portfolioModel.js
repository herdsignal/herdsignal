import { resolvePreviousScore } from '../../components/HerdLens/herdLensModel'

export const PORTFOLIO_SORTS = [
  { value: 'weight', label: '비중' },
  { value: 'today', label: '오늘' },
  { value: 'return', label: '수익률' },
  { value: 'herd', label: 'HERD' },
]

function numberOrNull(value) {
  if (value == null || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function previousSessionValue(currentValue, changePct) {
  const current = numberOrNull(currentValue)
  const change = numberOrNull(changePct)
  if (current == null || change == null || change <= -100) return null
  return current / (1 + change / 100)
}

export function buildPortfolioRows(portfolio = [], summary, herdMap = {}) {
  const stockMap = Object.fromEntries(
    (summary?.stocks ?? []).map((stock) => [stock.ticker, stock]),
  )
  const totalAssetValue = numberOrNull(
    summary?.total_asset_value ?? summary?.total_value,
  ) ?? 0

  return portfolio.map((holding) => {
    const ticker = String(holding?.ticker ?? '').toUpperCase()
    const price = stockMap[ticker] ?? null
    const herd = herdMap[ticker] ?? null
    const marketValue = numberOrNull(price?.market_value)
    const avgPrice = numberOrNull(holding?.avgPrice ?? holding?.avg_price)
    const quantity = numberOrNull(holding?.quantity)
    const cost = avgPrice != null && quantity != null
      ? avgPrice * quantity
      : null
    const pnl = marketValue != null && cost != null ? marketValue - cost : null
    const herdScore = numberOrNull(herd?.herdScore)

    return {
      ticker,
      companyName: herd?.companyName ?? null,
      logoUrl: herd?.logoUrl ?? null,
      marketValue,
      currentPrice: numberOrNull(price?.current_price),
      dailyChangePct: numberOrNull(price?.daily_change_pct),
      returnPct: numberOrNull(price?.return_pct),
      weightPct: marketValue != null && totalAssetValue > 0
        ? marketValue / totalAssetValue * 100
        : null,
      avgPrice,
      quantity,
      cost,
      pnl,
      herd,
      herdScore,
      herdStage: herd?.herdStage ?? null,
      herdPreviousScore: resolvePreviousScore(
        herdScore,
        null,
        herd?.delta4w,
      ),
      observationDate: herd?.lastObservedSession ?? herd?.scoreDate ?? null,
    }
  })
}

export function sortPortfolioRows(rows, sortBy = 'weight') {
  const field = {
    weight: 'weightPct',
    today: 'dailyChangePct',
    return: 'returnPct',
    herd: 'herdScore',
  }[sortBy] ?? 'weightPct'

  return [...rows].sort((left, right) => {
    const leftValue = numberOrNull(left[field])
    const rightValue = numberOrNull(right[field])
    if (leftValue == null && rightValue == null) {
      return left.ticker.localeCompare(right.ticker)
    }
    if (leftValue == null) return 1
    if (rightValue == null) return -1
    const difference = rightValue - leftValue
    return difference || left.ticker.localeCompare(right.ticker)
  })
}

export function portfolioTodayChange(summary) {
  const changes = (summary?.stocks ?? []).map((stock) => {
    const current = numberOrNull(stock?.market_value)
    const previous = previousSessionValue(current, stock?.daily_change_pct)
    return current != null && previous != null ? current - previous : null
  }).filter((value) => value != null)

  if (changes.length === 0) {
    return {
      amount: null,
      pct: numberOrNull(summary?.daily_change_pct),
    }
  }

  const amount = changes.reduce((sum, value) => sum + value, 0)
  const currentInvested = numberOrNull(summary?.invested_value) ?? 0
  const previousInvested = currentInvested - amount
  return {
    amount,
    pct: previousInvested > 0 ? amount / previousInvested * 100 : null,
  }
}

export function historyChartGeometry(points = [], width = 1000, height = 220) {
  const values = points
    .map((point) => numberOrNull(point?.totalAssetValue))
    .filter((value) => value != null)
  if (values.length === 0) return { path: '', areaPath: '', min: null, max: null }

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || Math.max(Math.abs(max) * 0.02, 1)
  const top = 12
  const bottom = height - 12
  const coordinates = values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : index / (values.length - 1) * width
    const y = bottom - (value - min) / range * (bottom - top)
    return [x, y]
  })
  const path = coordinates
    .map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`)
    .join(' ')
  const [firstX] = coordinates[0]
  const [lastX] = coordinates.at(-1)
  return {
    path,
    areaPath: `${path} L${lastX.toFixed(2)},${height} L${firstX.toFixed(2)},${height} Z`,
    min,
    max,
  }
}

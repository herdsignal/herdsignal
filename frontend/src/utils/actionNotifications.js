import { actionIntensityLabel } from './actionIntensity'
import { operationalSignal } from './portfolioTools'

export function notificationFingerprint(item) {
  return [
    operationalSignal(item),
    item?.actionRegime ?? '',
    actionIntensityLabel(item),
    item?.actionCooldownActive ? 'cooldown' : 'ready',
  ].join('|')
}

export function mergeTrackedStocks(portfolio = [], watchlist = []) {
  const merged = new Map()
  portfolio.forEach((item) => merged.set(item.ticker, { ...item, source: '포트폴리오' }))
  watchlist.forEach((item) => {
    if (!merged.has(item.ticker)) merged.set(item.ticker, { ...item, source: '관찰 대기열' })
  })
  return [...merged.values()].filter((item) => item.ticker)
}

export function buildActionNotificationState(items, previous = {}) {
  const snapshot = {}
  const changes = []
  const summary = { buy: 0, hold: 0, reduce: 0, total: items.length }

  items.forEach((item) => {
    const signal = operationalSignal(item)
    const fingerprint = notificationFingerprint(item)
    snapshot[item.ticker] = {
      fingerprint,
      scoreDate: item.scoreDate ?? null,
      signal,
    }

    if (previous[item.ticker] && previous[item.ticker].fingerprint !== fingerprint) {
      changes.push({
        ticker: item.ticker,
        source: item.source,
        signal,
        actionLabel: item.actionLabel ?? '판단 변경',
        intensity: actionIntensityLabel(item),
      })
    }

    if (['BUY', 'ADD'].includes(signal)) summary.buy += 1
    else if (['SELL', 'REDUCE'].includes(signal)) summary.reduce += 1
    else summary.hold += 1
  })

  return { snapshot, changes, summary }
}

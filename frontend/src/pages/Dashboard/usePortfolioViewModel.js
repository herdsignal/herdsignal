import { useMemo } from 'react'
import { buildPortfolioAlerts } from '../../utils/alertRules'
import {
  portfolioRows,
  portfolioRiskWarnings,
} from '../../utils/portfolioTools'
import {
  buildPositionAction,
  queuePriority,
  sortPortfolioItems,
} from './dashboardActions'

export function usePortfolioViewModel({
  portfolio,
  summary,
  herdMap,
  targetWeights,
  portfolioSort,
  priceMap,
}) {
  const rows = useMemo(
    () => portfolioRows(portfolio, summary, herdMap, targetWeights),
    [portfolio, summary, herdMap, targetWeights]
  )
  const sortedPortfolio = useMemo(
    () => sortPortfolioItems(portfolio, rows, herdMap, portfolioSort),
    [portfolio, rows, herdMap, portfolioSort]
  )
  const riskWarnings = useMemo(
    () => portfolioRiskWarnings(rows, summary),
    [rows, summary]
  )
  const portfolioAlerts = useMemo(
    () => buildPortfolioAlerts(rows, riskWarnings),
    [rows, riskWarnings]
  )
  const actionQueueCards = useMemo(() => {
    const rowMap = new Map(rows.map((row) => [row.ticker, row]))
    return sortedPortfolio
      .map((item) => {
        const herd = herdMap[item.ticker]
        const row = rowMap.get(item.ticker)
        if (!herd || !row) return null
        const action = buildPositionAction(herd, row)
        return {
          ticker: item.ticker,
          herd,
          row,
          action,
          score: Math.round(herd.herdScore ?? 0),
          stage: herd.herdStage?.startsWith('Herd ')
            ? herd.herdStage.slice(5)
            : herd.herdStage ?? 'Calm',
          price: priceMap[item.ticker],
          priority: queuePriority(action.code),
        }
      })
      .filter(Boolean)
      .sort((left, right) => {
        if (left.priority !== right.priority) return left.priority - right.priority
        return Number(right.herd.actionScore ?? 0) - Number(left.herd.actionScore ?? 0)
      })
      .slice(0, 3)
  }, [sortedPortfolio, rows, herdMap, priceMap])

  return {
    rows,
    sortedPortfolio,
    riskWarnings,
    portfolioAlerts,
    actionQueueCards,
  }
}

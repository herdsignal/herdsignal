import { describe, expect, it } from 'vitest'
import { buildHistorySummary, buildHistoryView, fmtAxisDate } from './historyModel'

describe('historyModel', () => {
  it('calculates account-value changes without labeling them as returns', () => {
    const view = buildHistoryView([
      { date: '2026-01-01', totalValue: 100 },
      { date: '2026-02-01', totalValue: 150 },
      { date: '2026-03-01', totalValue: 120 },
    ])

    expect(view.latest.totalValue).toBe(120)
    expect(view.insight.accountValueChange).toBeCloseTo(20)
    expect(view.insight.accountValueDrawdown).toBeCloseTo(-20)
    expect(view.insight.peak.totalValue).toBe(150)
    expect(view.yDomain[0]).toBeLessThan(100)
    expect(view.yDomain[1]).toBeGreaterThan(150)
  })

  it('separates account value from the holding cost-basis return', () => {
    expect(buildHistorySummary({
      totalAssetValue: 130,
      totalValue: 120,
      totalReturnPct: 5,
      dailyChangePct: -1,
    })).toEqual({
      accountValue: 130,
      holdingReturnPct: 5,
      dailyChangePct: -1,
    })
  })

  it('handles empty and invalid date input without chart exceptions', () => {
    expect(buildHistoryView([])).toEqual({
      latest: null,
      insight: null,
      yDomain: [0, 1000],
    })
    expect(fmtAxisDate('not-a-date')).toBe('not-a-date')
  })
})

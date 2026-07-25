import { describe, expect, it } from 'vitest'
import { buildAssetHistoryMetrics } from './usePortfolioAssetHistory'

describe('buildAssetHistoryMetrics', () => {
  it('derives flow, drawdown, and chart bounds without mutating history', () => {
    const history = [
      {
        date: '2026-07-01',
        investedValue: 100,
        cashBalance: 20,
        totalAssetValue: 120,
      },
      {
        date: '2026-07-10',
        investedValue: 140,
        cashBalance: 10,
        totalAssetValue: 150,
      },
    ]
    const original = structuredClone(history)
    const summary = {
      invested_value: 120,
      cash_balance: 10,
      total_asset_value: 130,
      total_return_pct: 5,
    }

    const metrics = buildAssetHistoryMetrics(history, summary, 10, 'year')

    expect(history).toEqual(original)
    expect(metrics.assetStartValue).toBe(120)
    expect(metrics.totalFlowPct).toBeCloseTo(8.3333, 3)
    expect(metrics.assetDrawdownPct).toBeCloseTo(-13.3333, 3)
    expect(metrics.assetPeriodLabel).toBe('1년')
    expect(metrics.assetYDomain[0]).toBeLessThan(100)
    expect(metrics.assetYDomain[1]).toBeGreaterThan(150)
  })
})

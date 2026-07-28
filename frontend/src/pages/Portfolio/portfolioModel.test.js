import { describe, expect, it } from 'vitest'
import {
  buildPortfolioRows,
  historyChartGeometry,
  portfolioTodayChange,
  sortPortfolioRows,
} from './portfolioModel'

describe('portfolio lens model', () => {
  const summary = {
    total_value: 1200,
    invested_value: 1000,
    stocks: [
      {
        ticker: 'NVDA',
        market_value: 600,
        price_date: '2026-07-27',
        return_pct: 20,
        daily_change_pct: 10,
      },
      {
        ticker: 'TSLA',
        market_value: 400,
        return_pct: -5,
        daily_change_pct: -2,
      },
    ],
  }

  it('builds account weights and four-week HERD history without actions', () => {
    const rows = buildPortfolioRows(
      [
        { ticker: 'NVDA', avgPrice: 100, quantity: 5, targetWeight: 0.4 },
        { ticker: 'TSLA', avgPrice: 210, quantity: 2, targetWeight: 0.3 },
      ],
      summary,
      {
        NVDA: {
          herdScore: 74,
          delta4w: 6,
          herdStage: 'Herd Drift',
          sector: 'Technology',
        },
      },
    )

    expect(rows[0]).toMatchObject({
      ticker: 'NVDA',
      weightPct: 50,
      cost: 500,
      pnl: 100,
      herdPreviousScore: 68,
      targetWeightPct: 40,
      targetGapPct: 10,
      sector: 'Technology',
      priceDate: '2026-07-27',
    })
    expect(rows[1].herdScore).toBeNull()
    expect(rows[0]).not.toHaveProperty('action')
  })

  it('sorts null observations last and computes daily account movement', () => {
    const rows = buildPortfolioRows(
      [{ ticker: 'NVDA' }, { ticker: 'TSLA' }],
      summary,
      { NVDA: { herdScore: 74 } },
    )

    expect(sortPortfolioRows(rows, 'herd').map((row) => row.ticker))
      .toEqual(['NVDA', 'TSLA'])
    expect(portfolioTodayChange(summary).amount).toBeGreaterThan(40)
    expect(portfolioTodayChange(summary).pct).toBeGreaterThan(4)
  })

  it('creates stable SVG paths, including a flat series', () => {
    const geometry = historyChartGeometry([
      { totalAssetValue: 100 },
      { totalAssetValue: 100 },
    ])
    expect(geometry.path).toContain('M')
    expect(geometry.path).not.toContain('NaN')
    expect(geometry.areaPath).toContain('Z')
  })
})

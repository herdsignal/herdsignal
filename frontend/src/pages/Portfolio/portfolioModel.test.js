import { describe, expect, it } from 'vitest'
import {
  buildPortfolioRows,
  buildPortfolioExposure,
  buildPortfolioHerdField,
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
    })
    expect(rows[1].herdScore).toBeNull()
    expect(rows[0]).not.toHaveProperty('action')
  })

  it('summarizes direct holding and sector exposure without assigning risk grades', () => {
    const rows = buildPortfolioRows(
      [
        { ticker: 'NVDA', targetWeight: 0.4 },
        { ticker: 'TSLA', targetWeight: 0.3 },
      ],
      summary,
      {
        NVDA: { sector: 'Technology' },
        TSLA: { sector: 'Consumer Cyclical' },
      },
    )
    const exposure = buildPortfolioExposure(rows, 200, 1200)

    expect(exposure.topHolding).toEqual({ ticker: 'NVDA', weightPct: 50 })
    expect(exposure.topThreeWeightPct).toBeCloseTo(83.33)
    expect(exposure.cashWeightPct).toBeCloseTo(16.67)
    expect(exposure.largestSector.name).toBe('Technology')
    expect(exposure).not.toHaveProperty('riskGrade')
  })

  it('maps observed holdings into a value-weighted HERD field', () => {
    const rows = buildPortfolioRows(
      [
        { ticker: 'NVDA' },
        { ticker: 'TSLA' },
      ],
      summary,
      {
        NVDA: { herdScore: 80 },
        TSLA: { herdScore: 20 },
      },
    )
    const field = buildPortfolioHerdField(rows)

    expect(field.weightedScore).toBeCloseTo(56)
    expect(field.weightedStage).toBe('Calm')
    expect(field.observedCount).toBe(2)
    expect(field.totalCount).toBe(2)
    expect(field.observedValueCoveragePct).toBe(100)
    expect(field.points.map((point) => point.ticker)).toEqual(['TSLA', 'NVDA'])
  })

  it('reports observation coverage instead of assigning a score to unsupported holdings', () => {
    const rows = buildPortfolioRows(
      [
        { ticker: 'NVDA' },
        { ticker: 'TSLA' },
      ],
      summary,
      { NVDA: { herdScore: 70 } },
    )
    const field = buildPortfolioHerdField(rows)

    expect(field.observedCount).toBe(1)
    expect(field.totalCount).toBe(2)
    expect(field.observedValueCoveragePct).toBe(60)
    expect(field.points).toHaveLength(1)
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

import { describe, expect, it } from 'vitest'
import { targetWeightsFromPortfolio } from './portfolioTools'

describe('targetWeightsFromPortfolio', () => {
  it('normalizes backend target weights for the editor', () => {
    expect(targetWeightsFromPortfolio([
      { ticker: 'NVDA', targetWeight: 0.25 },
      { ticker: 'AAPL', target_weight: 0.1 },
      { ticker: 'SPY' },
    ])).toEqual({
      NVDA: '25',
      AAPL: '10',
    })
  })
})

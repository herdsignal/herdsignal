import { describe, expect, it } from 'vitest'
import { formatPercent, presentValidationReport } from './herdModelPresentation'

describe('HERD Lab report presentation', () => {
  it('formats missing and signed percentages safely', () => {
    expect(formatPercent(null)).toBe('—')
    expect(formatPercent(8.12, '%p')).toBe('+8.1%p')
    expect(formatPercent(-2)).toBe('-2%')
  })

  it('maps live report metrics and ticker verdicts', () => {
    const result = presentValidationReport({
      modelVersion: 'HERD_v6.1', generatedAt: '2026-07-14T00:00:00Z',
      validationRun: { completedTickers: 55, requestedTickers: 55, coverage: 1, embargoDays: 20 },
      walkForward: { samples: 440, improvementRate: 36.4, mddImprovementMedian: 0.9 },
      parameterStability: { sameParameterRate: 59.4, singleParameterSpike: true, recommendation: 'USE_FIXED_PARAMETERS' },
      overfitting: { parametersTested: 9, deflatedSharpeStatus: 'FAIL' },
      adoptionGate: { policyVersion: '2026.07-v1', status: 'RESEARCH_VALIDATION', eligibleForHumanReview: false, failedCriteria: ['deflated_sharpe'] },
      scoreParityPassed: true, survivorshipStatus: 'SURVIVORSHIP_BIAS_REMAINS',
      tickers: [{ ticker: 'SPY', buyHoldReturn: 100, actionReturn: 70, capture: 70, mddImprovement: 5, actions: 8 }],
    })

    expect(result.metrics[0].value).toBe('+36.4%')
    expect(result.trustChecks[0].value).toBe('55/55')
    expect(result.rows[0].verdict).toBe('기준 통과')
    expect(result.model.status).toBe('RESEARCH_VALIDATION')
    expect(result.modelNotes).toContain('게이트 2026.07-v1 미통과: deflated_sharpe')
  })
})

import { describe, expect, it } from 'vitest'
import {
  buildStockStateSummary,
  transitionLabel,
} from './stockDetailModel'

describe('stock state summary', () => {
  it('shows a stable four-week comparison and the latest confirmed transition', () => {
    const summary = buildStockStateSummary({
      observation: {
        lastObservedSession: '2026-07-24',
        delta4w: 6,
      },
      currentScore: 63,
      currentStage: 'Drift',
      timeline: [
        {
          date: '2026-07-03',
          score: 55,
          stage: 'CALM',
          transition: 'NEUTRAL',
          transitionEvent: false,
        },
        {
          date: '2026-07-10',
          score: 60,
          stage: 'DRIFT',
          transition: 'RECOVERING',
          transitionEvent: true,
        },
        {
          date: '2026-07-17',
          score: 61,
          stage: 'DRIFT',
          transition: 'NEUTRAL',
          transitionEvent: false,
        },
        {
          date: '2026-07-24',
          score: 63,
          stage: 'DRIFT',
          transition: 'NEUTRAL',
          transitionEvent: false,
        },
      ],
    })

    expect(summary.fourWeekComparison).toBe('57 → 63')
    expect(summary.stageDurationLabel).toBe('3주째')
    expect(summary.stageDurationDays).toBe(14)
    expect(summary.recentTransition).toEqual({
      code: 'RECOVERING',
      label: '군중 회복',
      date: '2026-07-10',
    })
  })

  it('marks a duration as a lower bound when all loaded history is the same stage', () => {
    const summary = buildStockStateSummary({
      observation: { observationDate: '2026-07-24', delta4w: 1 },
      currentScore: 51,
      currentStage: 'Calm',
      timeline: [
        { date: '2026-07-17', score: 50, stage: 'CALM' },
        { date: '2026-07-24', score: 51, stage: 'CALM' },
      ],
    })

    expect(summary.stageDurationLabel).toBe('2주 이상')
    expect(summary.recentTransition).toBeNull()
  })

  it('does not expose neutral as a user-facing event', () => {
    expect(transitionLabel('NEUTRAL')).toBeNull()
    expect(transitionLabel('BREAKING')).toBe('밀집 훼손')
  })
})

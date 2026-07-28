import { describe, expect, it } from 'vitest'
import { timelineEvents } from './PriceHerdTimelineChart'

describe('timelineEvents', () => {
  it('keeps only observed transition events without inventing direction', () => {
    expect(timelineEvents([
      {
        date: '2026-07-03',
        score: 55,
        transition: 'NEUTRAL',
        transitionEvent: false,
      },
      {
        date: '2026-07-10',
        marketSession: '2026-07-10',
        adjustedClose: 151,
        score: 60,
        stage: 'DRIFT',
        transition: 'RECOVERING',
        transitionEvent: true,
      },
      {
        date: '2026-07-17',
        score: 63,
        transition: 'UNKNOWN',
        transitionEvent: true,
      },
    ])).toEqual([
      {
        date: '2026-07-10',
        marketSession: '2026-07-10',
        label: '군중 회복',
        stage: 'DRIFT',
        score: 60,
        adjustedClose: 151,
      },
    ])
  })
})

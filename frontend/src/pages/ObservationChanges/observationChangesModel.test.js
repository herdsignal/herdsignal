import { describe, expect, it } from 'vitest'
import {
  describeObservationChange,
  sortObservationChanges,
  trackingScopeLabel,
} from './observationChangesModel'

describe('observation changes presentation', () => {
  it('uses factual observation labels without action language', () => {
    expect(describeObservationChange({
      eventType: 'TRANSITION',
      transition: 'COOLING',
    })).toBe('밀집 완화')
    expect(describeObservationChange({
      eventType: 'STAGE_CHANGE',
      previousStage: 'CALM',
      stage: 'DRIFT',
    })).toBe('Calm → Drift')
  })

  it('keeps unread and recent changes first', () => {
    const sorted = sortObservationChanges([
      { id: 'old', unread: false, observationDate: '2026-07-24' },
      { id: 'new', unread: true, observationDate: '2026-07-17' },
    ])
    expect(sorted.map((item) => item.id)).toEqual(['new', 'old'])
  })

  it('prioritizes holdings and confirmed transitions without using score magnitude', () => {
    const sorted = sortObservationChanges([
      {
        id: 'watch-transition',
        unread: true,
        trackingScope: 'WATCHLIST',
        eventType: 'TRANSITION',
        observationDate: '2026-07-24',
      },
      {
        id: 'holding-stage',
        unread: true,
        trackingScope: 'HOLDING',
        eventType: 'STAGE_CHANGE',
        observationDate: '2026-07-17',
      },
      {
        id: 'holding-transition',
        unread: true,
        trackingScope: 'HOLDING',
        eventType: 'TRANSITION',
        observationDate: '2026-07-10',
      },
    ])

    expect(sorted.map((item) => item.id)).toEqual([
      'holding-transition',
      'holding-stage',
      'watch-transition',
    ])
    expect(trackingScopeLabel('HOLDING')).toBe('보유')
    expect(trackingScopeLabel('WATCHLIST')).toBe('관심')
  })
})

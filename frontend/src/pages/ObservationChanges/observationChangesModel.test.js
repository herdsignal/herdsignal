import { describe, expect, it } from 'vitest'
import {
  describeObservationChange,
  sortObservationChanges,
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
})

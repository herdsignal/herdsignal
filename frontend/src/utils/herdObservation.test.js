import { describe, expect, it } from 'vitest'
import {
  isObservationAvailable,
  normalizeObservationHistory,
  observationHistoryLimit,
  observationScore,
} from './herdObservation'

describe('HERD S1 observation view model', () => {
  it('never invents a neutral score for unavailable data', () => {
    const unavailable = {
      availabilityStatus: 'UNAVAILABLE',
      stateScore: null,
    }
    expect(isObservationAvailable(unavailable)).toBe(false)
    expect(observationScore(unavailable)).toBeNull()
  })

  it('normalizes newest-first API history into chart order', () => {
    const points = normalizeObservationHistory([
      { observationDate: '2026-07-24', stateScore: 62 },
      { observationDate: '2026-07-17', stateScore: 58 },
    ])
    expect(points.map((point) => point.date)).toEqual([
      '2026-07-17',
      '2026-07-24',
    ])
    expect(observationHistoryLimit('3y')).toBeLessThanOrEqual(260)
  })
})

import { describe, expect, it } from 'vitest'
import {
  isObservationAvailable,
  normalizeObservationHistory,
  observationBatchToMap,
  observationHistoryLimit,
  observationScore,
  observationToTrackedItem,
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

describe('S1 tracked item boundary', () => {
  it('never promotes legacy-like action fields from an observation', () => {
    const item = observationToTrackedItem({
      ticker: 'NVDA',
      availabilityStatus: 'AVAILABLE',
      stateScore: 78,
      stage: 'RUSH',
      operationalAction: 'SELL',
      operationalActionRatio: 0.15,
    })

    expect(item.herdScore).toBe(78)
    expect(item.herdStage).toBe('Herd Rush')
    expect(item.signal).toBe('HOLD')
    expect(item.actionRatio).toBe(0)
    expect(item.actionAuthorized).toBe(false)
  })

  it('preserves batch order metadata as a ticker map', () => {
    const map = observationBatchToMap({
      observations: [{
        ticker: 'AAPL',
        availabilityStatus: 'UNAVAILABLE',
        companyName: 'Apple Inc.',
      }],
    }, { AAPL: { memo: 'watch' } })

    expect(map.AAPL.companyName).toBe('Apple Inc.')
    expect(map.AAPL.memo).toBe('watch')
    expect(map.AAPL.herdScore).toBeNull()
  })
})

import { describe, expect, it } from 'vitest'
import {
  sortWatchlistObservations,
  summarizeWatchlistStages,
} from './watchlistModel'

describe('watch field model', () => {
  const items = [
    { ticker: 'A', herdScore: 82, lastObservedSession: '2026-07-20' },
    { ticker: 'B', herdScore: 12, lastObservedSession: '2026-07-24' },
    { ticker: 'C', herdScore: null, lastObservedSession: null },
  ]

  it('sorts unavailable observations last', () => {
    expect(sortWatchlistObservations(items, 'high').map((item) => item.ticker))
      .toEqual(['A', 'B', 'C'])
    expect(sortWatchlistObservations(items, 'recent').map((item) => item.ticker))
      .toEqual(['B', 'A', 'C'])
  })

  it('summarizes the five HERD states without action inference', () => {
    const summary = summarizeWatchlistStages(items)
    expect(summary.find((item) => item.stage === 'Rush').count).toBe(1)
    expect(summary.find((item) => item.stage === 'Flee').count).toBe(1)
    expect(summary.reduce((sum, item) => sum + item.count, 0)).toBe(2)
  })
})

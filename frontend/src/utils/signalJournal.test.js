import { describe, expect, it } from 'vitest'
import {
  filterSignalJournal,
  findHorizonOutcome,
  formatHorizonOutcome,
  getJournalReviewStatus,
  summarizeSignalJournal,
} from './signalJournal'

describe('signal journal outcomes', () => {
  const log = {
    actionType: 'SELL',
    horizonOutcomes: [
      { horizon: '1M', status: 'AVAILABLE', returnPct: -12.345 },
      { horizon: '3M', status: 'PENDING' },
      { horizon: '6M', status: 'UNAVAILABLE' },
    ],
  }

  it('shows objective returns without reversing sell records', () => {
    expect(formatHorizonOutcome(findHorizonOutcome(log, '1M'))).toBe('-12.3%')
    expect(formatHorizonOutcome(findHorizonOutcome(log, '3M'))).toBe('대기')
    expect(formatHorizonOutcome(findHorizonOutcome(log, '6M'))).toBe('자료 없음')
  })

  it('counts records with mature outcomes separately from pending records', () => {
    expect(summarizeSignalJournal([log])).toMatchObject({
      outcomeAvailableCount: 1,
      pendingOutcomeCount: 1,
    })
  })

  it('classifies and filters records by review availability', () => {
    const ready = { id: 1, actionType: 'SELL', horizonOutcomes: [{ status: 'AVAILABLE' }] }
    const pending = { id: 2, actionType: 'BUY', horizonOutcomes: [{ status: 'PENDING' }] }
    const unavailable = { id: 3, actionType: 'HOLD', horizonOutcomes: [{ status: 'UNAVAILABLE' }] }

    expect(getJournalReviewStatus(ready)).toBe('READY')
    expect(getJournalReviewStatus(pending)).toBe('PENDING')
    expect(getJournalReviewStatus(unavailable)).toBe('UNAVAILABLE')
    expect(filterSignalJournal([ready, pending, unavailable], 'ALL', 'READY')).toEqual([ready])
    expect(filterSignalJournal([ready, pending, unavailable], 'BUY', 'PENDING')).toEqual([pending])
  })
})

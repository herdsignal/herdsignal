import { describe, expect, it } from 'vitest'
import {
  buildActionNotificationState,
  mergeTrackedStocks,
  notificationFingerprint,
} from './actionNotifications'

describe('action notifications', () => {
  it('deduplicates portfolio and watchlist tickers', () => {
    const items = mergeTrackedStocks(
      [{ ticker: 'AAPL', signal: 'HOLD' }],
      [{ ticker: 'AAPL', signal: 'BUY' }, { ticker: 'NVDA', signal: 'BUY' }],
    )
    expect(items).toHaveLength(2)
    expect(items[0].source).toBe('포트폴리오')
  })

  it('does not create changes on the first snapshot', () => {
    const result = buildActionNotificationState([{ ticker: 'AAPL', signal: 'BUY' }])
    expect(result.changes).toEqual([])
    expect(result.summary.buy).toBe(1)
  })

  it('reports a changed action fingerprint', () => {
    const before = { AAPL: { fingerprint: notificationFingerprint({ signal: 'HOLD' }) } }
    const result = buildActionNotificationState(
      [{ ticker: 'AAPL', signal: 'REDUCE', actionLabel: '일부 축소' }],
      before,
    )
    expect(result.changes[0]).toMatchObject({ ticker: 'AAPL', signal: 'REDUCE' })
    expect(result.summary.reduce).toBe(1)
  })
})

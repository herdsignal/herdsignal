import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  enableObservationNotifications,
  notificationStatus,
  notifyConfirmedObservationChanges,
} from './observationNotifications'

describe('observation notifications', () => {
  beforeEach(() => {
    window.localStorage.clear()
    class NotificationMock {
      static permission = 'default'
      static requestPermission = vi.fn(async () => 'granted')
      constructor(title, options) {
        NotificationMock.calls.push({ title, options })
      }
      static calls = []
    }
    window.Notification = NotificationMock
  })

  it('requires an explicit permission request before enabling', async () => {
    expect(notificationStatus()).toBe('disabled')
    expect(await enableObservationNotifications()).toBe('enabled')
    window.Notification.permission = 'granted'
    expect(notificationStatus()).toBe('enabled')
  })

  it('sends one observation-only summary and deduplicates it', async () => {
    await enableObservationNotifications()
    window.Notification.permission = 'granted'
    const events = [{ id: 'NVDA:1', ticker: 'NVDA', observationDate: '2026-07-31', unread: true }]

    expect(notifyConfirmedObservationChanges(events)).toBe(true)
    expect(notifyConfirmedObservationChanges(events)).toBe(false)
    expect(window.Notification.calls).toHaveLength(1)
    expect(window.Notification.calls[0].options.body).not.toMatch(/매수|매도|익절|추천/)
  })
})

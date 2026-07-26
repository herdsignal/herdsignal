import { describe, expect, it } from 'vitest'
import { shouldNotifyObservationChange } from './observationNotifications'

describe('shouldNotifyObservationChange', () => {
  it('notifies only when an already observed unread count increases', () => {
    expect(shouldNotifyObservationChange(1, 2, true, 'granted')).toBe(true)
    expect(shouldNotifyObservationChange(null, 2, true, 'granted')).toBe(false)
    expect(shouldNotifyObservationChange(2, 2, true, 'granted')).toBe(false)
    expect(shouldNotifyObservationChange(1, 2, false, 'granted')).toBe(false)
    expect(shouldNotifyObservationChange(1, 2, true, 'denied')).toBe(false)
  })
})

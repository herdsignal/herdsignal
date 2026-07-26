export const OBSERVATION_NOTIFICATION_KEY = 'herdsignal_observation_notifications'

export function observationNotificationsEnabled(storage = localStorage) {
  try {
    return storage.getItem(OBSERVATION_NOTIFICATION_KEY) === 'enabled'
  } catch {
    return false
  }
}

export function setObservationNotificationsEnabled(enabled, storage = localStorage) {
  storage.setItem(OBSERVATION_NOTIFICATION_KEY, enabled ? 'enabled' : 'disabled')
}

export function canUseBrowserNotifications(scope = globalThis) {
  return typeof scope.Notification === 'function'
}

export function shouldNotifyObservationChange(previousCount, nextCount, enabled, permission) {
  return enabled
    && permission === 'granted'
    && Number.isFinite(previousCount)
    && nextCount > previousCount
}

export const OBSERVATION_NOTIFICATION_KEY = 'herdsignal_observation_notifications'

function preferenceKey(userId) {
  return userId ? `${OBSERVATION_NOTIFICATION_KEY}:${userId}` : OBSERVATION_NOTIFICATION_KEY
}

export function observationNotificationsEnabled(userId, storage = localStorage) {
  try {
    return storage.getItem(preferenceKey(userId)) === 'enabled'
  } catch {
    return false
  }
}

export function setObservationNotificationsEnabled(enabled, userId, storage = localStorage) {
  storage.setItem(preferenceKey(userId), enabled ? 'enabled' : 'disabled')
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

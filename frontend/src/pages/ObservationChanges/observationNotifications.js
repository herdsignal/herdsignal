const ENABLED_KEY = 'herdsignal.observationNotifications.enabled'
const LAST_KEY = 'herdsignal.observationNotifications.lastEvent'

export function notificationStatus() {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return 'unsupported'
  }
  if (window.Notification.permission === 'denied') return 'denied'
  return window.localStorage.getItem(ENABLED_KEY) === 'true'
    && window.Notification.permission === 'granted'
    ? 'enabled'
    : 'disabled'
}

export async function enableObservationNotifications() {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return 'unsupported'
  }
  const permission = await window.Notification.requestPermission()
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'disabled'
  window.localStorage.setItem(ENABLED_KEY, 'true')
  return 'enabled'
}

export function notifyConfirmedObservationChanges(events = []) {
  if (notificationStatus() !== 'enabled') return false
  const unread = events.filter((event) => event.unread)
  if (!unread.length) return false
  const latestKey = unread.map((event) => event.id).sort().join('|')
  if (window.localStorage.getItem(LAST_KEY) === latestKey) return false
  window.localStorage.setItem(LAST_KEY, latestKey)
  const first = unread[0]
  const body = unread.length === 1
    ? `${first.ticker} · ${first.observationDate} 주간 상태 변화`
    : `${first.ticker} 외 ${unread.length - 1}개 종목의 주간 상태 변화`
  new window.Notification('HerdSignal 관찰 변화', { body, tag: 'herdsignal-observation' })
  return true
}

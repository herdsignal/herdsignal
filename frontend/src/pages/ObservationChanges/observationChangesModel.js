import { normalizeStage } from '../../utils/herdStage'

const TRANSITIONS = {
  BREAKING: '밀집 훼손',
  RECOVERING: '군중 회복',
  COOLING: '밀집 완화',
}

export function displayStage(stage) {
  const normalized = normalizeStage(stage)
  if (!normalized) return '—'
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

export function describeObservationChange(event) {
  if (event?.eventType === 'TRANSITION') {
    return TRANSITIONS[event.transition] ?? '상태 전환'
  }
  return `${displayStage(event?.previousStage)} → ${displayStage(event?.stage)}`
}

export function formatObservationDelta(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '—'
  const rounded = Math.round(numeric)
  return `${rounded > 0 ? '+' : ''}${rounded}`
}

export function sortObservationChanges(events) {
  if (!Array.isArray(events)) return []
  return [...events].sort((left, right) => {
    if (left.unread !== right.unread) return left.unread ? -1 : 1
    const leftHolding = left.trackingScope === 'HOLDING'
    const rightHolding = right.trackingScope === 'HOLDING'
    if (leftHolding !== rightHolding) return leftHolding ? -1 : 1
    const leftTransition = left.eventType === 'TRANSITION'
    const rightTransition = right.eventType === 'TRANSITION'
    if (leftTransition !== rightTransition) return leftTransition ? -1 : 1
    return String(right.observationDate).localeCompare(String(left.observationDate))
  })
}

export function trackingScopeLabel(scope) {
  return scope === 'HOLDING' ? '보유' : '관심'
}

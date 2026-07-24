import { stageLabelFromScore } from './herdStage'

export const OBSERVATION_MODEL_VERSION = 'HERD_STATE_S1'

const HISTORY_LIMITS = {
  '1m': 6,
  '3m': 15,
  '1y': 54,
  '3y': 158,
}

export function isObservationAvailable(observation) {
  return observation?.availabilityStatus === 'AVAILABLE'
    && Number.isFinite(Number(observation?.stateScore))
}

export function observationScore(observation) {
  return isObservationAvailable(observation)
    ? Number(observation.stateScore)
    : null
}

export function observationStage(observation) {
  const score = observationScore(observation)
  return score == null ? null : stageLabelFromScore(score)
}

export function observationHistoryLimit(period) {
  return HISTORY_LIMITS[period] ?? HISTORY_LIMITS['1y']
}

export function normalizeObservationHistory(points) {
  if (!Array.isArray(points)) return []
  return points
    .map((point) => ({
      date: point.observationDate,
      lastObservedSession: point.lastObservedSession,
      score: Number(point.stateScore),
      stage: point.stage,
      transition: point.transition,
      transitionEvent: Boolean(point.transitionEvent),
    }))
    .filter((point) => point.date && Number.isFinite(point.score))
    .sort((left, right) => left.date.localeCompare(right.date))
}

export function observationFreshnessLabel(observation) {
  if (!isObservationAvailable(observation)) return '관찰값 준비 중'
  if (observation.freshnessStatus === 'STALE') return '업데이트 필요'
  return '최신 관찰'
}

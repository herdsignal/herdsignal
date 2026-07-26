import { stageLabelFromScore } from './herdStage'

export const OBSERVATION_MODEL_VERSION = 'HERD_STATE_S1'

const HISTORY_LIMITS = {
  '1m': 6,
  '3m': 15,
  '1y': 54,
  '3y': 158,
}

export const OBSERVATION_TIMELINE_LIMIT = 260

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

export function selectObservationHistory(points, period) {
  if (!Array.isArray(points)) return []
  return points.slice(-observationHistoryLimit(period))
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

/**
 * 기본 사용자 화면의 기존 카드들이 S1 필드명을 직접 추측하지 않도록 한다.
 * 레거시 signal/action 필드는 어떤 입력에서도 HOLD·0%로 닫는다.
 */
export function observationToTrackedItem(observation, extra = {}) {
  const available = isObservationAvailable(observation)
  const score = observationScore(observation)
  const stage = observationStage(observation)
  return {
    ...extra,
    ticker: observation?.ticker ?? extra.ticker,
    companyName: observation?.companyName ?? extra.companyName ?? null,
    sector: observation?.sector ?? extra.sector ?? null,
    logoUrl: observation?.logoUrl ?? extra.logoUrl ?? null,
    availabilityStatus: observation?.availabilityStatus ?? 'UNAVAILABLE',
    freshnessStatus: observation?.freshnessStatus ?? 'UNAVAILABLE',
    herdScore: available ? score : null,
    herdStage: available && stage ? `Herd ${stage}` : null,
    scoreDate: observation?.observationDate ?? null,
    lastObservedSession: observation?.lastObservedSession ?? null,
    delta4w: Number.isFinite(Number(observation?.delta4w))
      ? Number(observation.delta4w)
      : null,
    transition: observation?.transition ?? null,
    transitionEvent: observation?.transitionEvent === true,
    families: observation?.families ?? null,
    downsideRiskContext: observation?.downsideRiskContext ?? null,
    stateModelVersion: observation?.stateModelVersion ?? OBSERVATION_MODEL_VERSION,
    signal: 'HOLD',
    operationalAction: 'HOLD',
    operationalActionRatio: 0,
    actionRatio: 0,
    actionAuthorized: false,
  }
}

export function observationBatchToMap(batch, extrasByTicker = {}) {
  const observations = batch?.observations
  if (!Array.isArray(observations)) return {}
  return Object.fromEntries(observations.map((observation) => {
    const ticker = observation?.ticker
    return [
      ticker,
      observationToTrackedItem(observation, extrasByTicker[ticker]),
    ]
  }).filter(([ticker]) => ticker))
}

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

export function normalizeHerdPriceTimeline(points) {
  if (!Array.isArray(points)) return []
  return points
    .map((point) => {
      const adjustedClose = point.adjustedClose == null
        ? null
        : Number(point.adjustedClose)
      return {
        date: point.observationDate,
        marketSession: point.marketSession,
        adjustedClose: Number.isFinite(adjustedClose) ? adjustedClose : null,
        score: Number(point.herdScore),
        stage: point.herdStage,
        transition: point.transition,
        transitionEvent: Boolean(point.transitionEvent),
      }
    })
    .filter((point) => point.date && Number.isFinite(point.score))
    .sort((left, right) => left.date.localeCompare(right.date))
}

export function observationFreshnessLabel(observation) {
  if (!isObservationAvailable(observation)) return '주간 관찰 준비 중'
  if (observation.freshnessStatus === 'STALE') return '주간 관찰 갱신 필요'
  return '주간 관찰'
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

export function mergeDailyObservationBatch(
  confirmedMap,
  dailyBatch,
) {
  const dailyMap = observationBatchToMap(dailyBatch)
  return Object.fromEntries(Object.entries(confirmedMap ?? {}).map(
    ([ticker, confirmed]) => {
      const daily = dailyMap[ticker]
      if (
        daily?.availabilityStatus !== 'AVAILABLE'
        || !Number.isFinite(Number(daily?.herdScore))
      ) {
        return [ticker, {
          ...confirmed,
          confirmedHerdScore: confirmed.herdScore,
          confirmedHerdStage: confirmed.herdStage,
          confirmedObservationDate:
            confirmed.lastObservedSession ?? confirmed.scoreDate ?? null,
          provisional: false,
        }]
      }
      return [ticker, {
        ...confirmed,
        herdScore: daily.herdScore,
        herdStage: daily.herdStage,
        scoreDate: daily.scoreDate,
        lastObservedSession: daily.lastObservedSession,
        delta4w: daily.delta4w,
        families: daily.families,
        downsideRiskContext: daily.downsideRiskContext,
        stateModelVersion: daily.stateModelVersion,
        confirmedHerdScore: confirmed.herdScore,
        confirmedHerdStage: confirmed.herdStage,
        confirmedObservationDate:
          confirmed.lastObservedSession ?? confirmed.scoreDate ?? null,
        provisional: true,
      }]
    },
  ))
}

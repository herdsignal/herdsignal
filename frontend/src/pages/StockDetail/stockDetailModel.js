import { API_HOST } from '../../utils/apiConfig'
import { HERD_HISTORY_PERIODS } from '../../utils/historyPeriods'
import {
  normalizeStage,
  stageBadgeStyle,
  stageColor,
  stageLabelFromScore,
} from '../../utils/herdStage'

export { API_HOST, normalizeStage, stageColor }
export const HISTORY_PERIODS = HERD_HISTORY_PERIODS

export function badgeColors(stage) {
  const badge = stageBadgeStyle(stage)
  return { background: badge.bg, color: badge.color }
}

export function journalActionLabel(type) {
  switch (type) {
    case 'BUY': return '매수 기록'
    case 'HOLD': return '보류 기록'
    case 'SELL': return '익절 기록'
    default: return '판단 기록'
  }
}

const TRANSITION_LABELS = {
  BREAKING: '밀집 훼손',
  RECOVERING: '군중 회복',
  COOLING: '밀집 완화',
  EXTENDING: '밀집 확대',
  FALLING: '분산 확대',
  STABILIZING: '저위 안정',
  PLATEAU: '고위 정체',
}

function pointDate(point) {
  return point?.lastObservedSession ?? point?.date ?? null
}

function pointStage(point) {
  const normalized = normalizeStage(point?.stage)
  if (normalized) return normalized
  return normalizeStage(stageLabelFromScore(point?.score))
}

function dayDifference(start, end) {
  const startTime = Date.parse(`${start}T00:00:00Z`)
  const endTime = Date.parse(`${end}T00:00:00Z`)
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) return null
  return Math.max(0, Math.round((endTime - startTime) / 86_400_000))
}

export function transitionLabel(transition) {
  return TRANSITION_LABELS[String(transition ?? '').toUpperCase()] ?? null
}

export function buildStockStateSummary({
  observation,
  currentScore,
  currentStage,
  timeline = [],
}) {
  const sorted = [...timeline]
    .filter((point) => pointDate(point) && Number.isFinite(Number(point?.score)))
    .sort((left, right) => pointDate(left).localeCompare(pointDate(right)))
  const currentDate = observation?.lastObservedSession
    ?? observation?.observationDate
    ?? pointDate(sorted.at(-1))
  const normalizedCurrentStage = normalizeStage(currentStage)
  let stageStartDate = currentDate
  let stagePoints = 0

  for (let index = sorted.length - 1; index >= 0; index -= 1) {
    if (pointStage(sorted[index]) !== normalizedCurrentStage) break
    stageStartDate = pointDate(sorted[index])
    stagePoints += 1
  }

  const stageDurationDays = dayDifference(stageStartDate, currentDate)
  const stageDurationWeeks = stageDurationDays == null
    ? null
    : Math.max(1, Math.floor(stageDurationDays / 7) + 1)
  const stageDurationBounded = stagePoints > 0
    && stagePoints === sorted.length
    && sorted.length > 1
  const recentTransition = [...sorted]
    .reverse()
    .find((point) => point.transitionEvent && transitionLabel(point.transition))
  const previousScore = Number.isFinite(Number(observation?.delta4w))
    ? Number(currentScore) - Number(observation.delta4w)
    : null
  const durationLabel = stageDurationWeeks == null
    ? '—'
    : `${stageDurationWeeks}주${stageDurationBounded ? ' 이상' : '째'}`

  return {
    currentDate,
    fourWeekPreviousScore: Number.isFinite(previousScore) ? previousScore : null,
    fourWeekDelta: Number.isFinite(Number(observation?.delta4w))
      ? Number(observation.delta4w)
      : null,
    fourWeekComparison: Number.isFinite(previousScore)
      ? `${Math.round(previousScore)} → ${Math.round(currentScore)}`
      : `— → ${Math.round(currentScore)}`,
    stageLabel: currentStage ?? '—',
    stageDurationDays,
    stageDurationWeeks,
    stageDurationLabel: durationLabel,
    recentTransition: recentTransition
      ? {
          code: recentTransition.transition,
          label: transitionLabel(recentTransition.transition),
          date: pointDate(recentTransition),
        }
      : null,
  }
}

export const BTN_LABELS = {
  portfolio: {
    idle: '포트폴리오 추가',
    loading: '추가 중…',
    added: '추가됨 ✓',
    exists: '이미 추가됨',
  },
  watchlist: {
    idle: '관심종목 추가',
    loading: '추가 중…',
    added: '추가됨 ✓',
    exists: '이미 추가됨',
  },
}

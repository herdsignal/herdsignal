/**
 * HERD 히스토리 기반 최근 강도 변화 표시 유틸.
 */

import { normalizeStage, stageFromScore } from './herdStage'

function scoreOf(point) {
  const n = Number(point?.score)
  return Number.isFinite(n) ? n : null
}

export function getHerdMomentum(points, currentScore = null, currentStage = null) {
  const valid = Array.isArray(points)
    ? points.filter((point) => scoreOf(point) != null)
    : []

  const latestScore = Number.isFinite(Number(currentScore))
    ? Number(currentScore)
    : scoreOf(valid[valid.length - 1])

  if (latestScore == null || valid.length < 2) {
    return {
      label: '강도 확인 중',
      detail: '비교 이력 부족',
      delta: null,
      tone: 'neutral',
    }
  }

  const previous = [...valid]
    .reverse()
    .find((point) => scoreOf(point) !== latestScore)

  const previousScore = scoreOf(previous) ?? scoreOf(valid[Math.max(0, valid.length - 2)])
  if (previousScore == null) {
    return {
      label: '강도 확인 중',
      detail: '비교 이력 부족',
      delta: null,
      tone: 'neutral',
    }
  }

  const delta = latestScore - previousScore
  const absDelta = Math.abs(delta)
  const stage = normalizeStage(currentStage) || stageFromScore(latestScore)
  const isHot = stage === 'rush' || stage === 'drift'
  const isCold = stage === 'flee' || stage === 'scatter'

  if (absDelta < 2) {
    return {
      label: '강도 유지',
      detail: `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}pt`,
      delta,
      tone: 'neutral',
    }
  }

  if (delta > 0) {
    return {
      label: isHot ? '쏠림 확장' : isCold ? '저점 완화' : '강도 상승',
      detail: `+${delta.toFixed(1)}pt`,
      delta,
      tone: isHot ? 'warning' : 'positive',
    }
  }

  return {
    label: isHot ? '과열 둔화' : isCold ? '이탈 심화' : '강도 하락',
    detail: `${delta.toFixed(1)}pt`,
    delta,
    tone: isCold ? 'warning' : 'positive',
  }
}

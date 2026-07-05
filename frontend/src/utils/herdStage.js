/**
 * utils/herdStage.js — HERD 단계/색상 기준 단일화.
 *
 * 운영 행동 신호와 같은 15/40/60/75 기준을 frontend 표시에도 사용한다.
 */

export const HERD_STAGE_THRESHOLDS = {
  flee: 15,
  scatter: 40,
  drift: 60,
  rush: 75,
}

export function normalizeStage(stage) {
  const s = (stage || '').toLowerCase()
  return s.startsWith('herd ') ? s.slice(5) : s
}

export function stageFromScore(score) {
  if (score == null || Number.isNaN(Number(score))) return null
  const n = Number(score)
  if (n <= HERD_STAGE_THRESHOLDS.flee) return 'flee'
  if (n <= HERD_STAGE_THRESHOLDS.scatter) return 'scatter'
  if (n < HERD_STAGE_THRESHOLDS.drift) return 'calm'
  if (n < HERD_STAGE_THRESHOLDS.rush) return 'drift'
  return 'rush'
}

export function stageLabelFromScore(score, withPrefix = false) {
  const stage = stageFromScore(score)
  if (!stage) return withPrefix ? null : '—'
  const label = stage.charAt(0).toUpperCase() + stage.slice(1)
  return withPrefix ? `Herd ${label}` : label
}

export function stageColor(stage) {
  switch (normalizeStage(stage)) {
    case 'rush': return 'var(--rush)'
    case 'drift': return 'var(--drift)'
    case 'scatter': return 'var(--scatter)'
    case 'flee': return 'var(--flee)'
    default: return 'var(--calm)'
  }
}

export function scoreColor(score) {
  return stageColor(stageFromScore(score))
}

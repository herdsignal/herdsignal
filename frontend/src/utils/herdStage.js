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

export function stageDescription(stage) {
  switch (normalizeStage(stage)) {
    case 'rush': return '군중 밀집'
    case 'drift': return '밀집 진행'
    case 'scatter': return '군중 분산'
    case 'flee': return '군중 이탈'
    default: return '군중 균형'
  }
}

export function stageBadgeStyle(stage) {
  switch (normalizeStage(stage)) {
    case 'rush': return { bg: 'rgba(239,68,68,0.12)', color: 'var(--rush)' }
    case 'drift': return { bg: 'rgba(249,115,22,0.12)', color: 'var(--drift)' }
    case 'scatter': return { bg: 'rgba(96,165,250,0.12)', color: 'var(--scatter)' }
    case 'flee': return { bg: 'rgba(59,130,246,0.12)', color: 'var(--flee)' }
    default: return { bg: 'rgba(163,170,184,0.13)', color: 'var(--calm)' }
  }
}

/**
 * HERD 신호/단계 지속 기간 표시 유틸.
 */

function validDays(days) {
  const n = Number(days)
  return Number.isFinite(n) && n > 0 ? Math.round(n) : null
}

export function formatSignalDuration(data) {
  const days = validDays(data?.signalDurationDays)
  if (!days) return null
  return `신호 ${days}일째`
}

export function formatStageDuration(data) {
  const days = validDays(data?.stageDurationDays)
  if (!days) return null
  return `단계 ${days}일째`
}

export function formatSignalDurationDetail(data) {
  const signalDays = validDays(data?.signalDurationDays)
  const stageDays = validDays(data?.stageDurationDays)
  const signal = data?.signal ?? 'HOLD'
  const stage = data?.herdStage?.startsWith('Herd ')
    ? data.herdStage.slice(5)
    : data?.herdStage

  const parts = []
  if (signalDays) parts.push(`${signal} ${signalDays}일째`)
  if (stage && stageDays) parts.push(`${stage} ${stageDays}일째`)
  return parts.length > 0 ? parts.join(' · ') : null
}

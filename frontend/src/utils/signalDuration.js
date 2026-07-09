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

export function getSignalDurationMeta(data) {
  const days = validDays(data?.signalDurationDays)
  if (!days) {
    return {
      label: '신호 확인',
      detail: null,
      tone: 'neutral',
      days: null,
    }
  }

  if (days <= 5) {
    return {
      label: '초입 신호',
      detail: `신호 ${days}일째`,
      tone: 'fresh',
      days,
    }
  }

  if (days <= 20) {
    return {
      label: '진행 신호',
      detail: `신호 ${days}일째`,
      tone: 'active',
      days,
    }
  }

  return {
    label: '장기 지속',
    detail: `신호 ${days}일째`,
    tone: 'extended',
    days,
  }
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

export function formatSignalAgeLabel(data) {
  const meta = getSignalDurationMeta(data)
  return meta.detail ? `${meta.label} · ${meta.detail}` : meta.label
}

export function qualityColor(level) {
  switch (level) {
    case 'HIGH': return 'var(--flee)'
    case 'GOOD': return 'var(--calm)'
    case 'LIMITED': return 'var(--drift)'
    case 'LOW': return 'var(--rush)'
    default: return 'var(--text-3)'
  }
}

export function shouldShowQuality(data) {
  if (!data?.qualityLabel) return false
  if (data.qualityLevel === 'LIMITED' || data.qualityLevel === 'LOW') return true
  return Number(data.qualityScore ?? 100) < 70
}

export function qualityWarningText(data, options = {}) {
  const label = data?.qualityLevel === 'LOW' ? '데이터 부족' : '데이터 제한'
  const suffix = options.pointSuffix ? '점' : ''
  return `${label}${data?.qualityScore != null ? ` · ${data.qualityScore}${suffix}` : ''}`
}

export function qualityReasonText(data) {
  const reasons = Array.isArray(data?.qualityReasons) ? data.qualityReasons.filter(Boolean) : []
  if (reasons.length > 0) return reasons.slice(0, 2).join(' · ')
  if (data?.qualityLabel) return data.qualityLabel
  return '데이터 품질 확인 필요'
}

export function actionIntensity(value) {
  const ratio = Number(value ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return { code: 'NONE', label: '관찰' }
  if (ratio <= 0.05) return { code: 'LOW', label: '낮음' }
  if (ratio <= 0.15) return { code: 'MEDIUM', label: '중간' }
  return { code: 'HIGH', label: '높음' }
}

export function actionIntensityLabel(data) {
  if (data?.actionAuthorized !== true) return '관찰'
  return data?.actionIntensityLabel
    ?? actionIntensity(data?.operationalActionRatio ?? data?.actionRatio).label
}

export function formatActionScore(value) {
  if (value == null) return null
  const number = Number(value)
  if (!Number.isFinite(number)) return null
  return `강도 ${Math.round(number)}`
}

export function actionBasisLabel(data) {
  const intensity = actionIntensityLabel(data)
  if (intensity === '관찰') return '현재 비중 유지'
  const action = data?.operationalAction
  if (action === 'BUY' || action === 'ADD') return `${intensity} 강도로 분할매수 검토`
  if (action === 'SELL' || action === 'REDUCE') return `${intensity} 강도로 비중 축소 검토`
  return '현재 비중 유지'
}

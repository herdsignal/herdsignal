export function presentShadowStatus(status) {
  if (!status || status.shadowStatus !== 'SHADOW_ACTIVE') {
    return {
      tone: 'blocked',
      label: '차세대 후보 없음',
      candidate: null,
    }
  }
  return {
    tone: 'active',
    label: 'Shadow 관측 중',
    candidate: status.candidateId,
  }
}

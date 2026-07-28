function formatDate(value) {
  if (!value) return '—'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  })
}

export function presentProspectiveEvidence(status) {
  if (!status?.auditPassed) {
    return {
      available: false,
      statusLabel: '감사 확인 불가',
      archives: '0회',
      records: '0개',
      matured: '0개',
      pending: '0개',
      period: '—',
    }
  }
  return {
    available: true,
    statusLabel: '수집 중',
    archives: `${Number(status.observationArchives ?? 0).toLocaleString('ko-KR')}회`,
    records: `${Number(status.observationRecords ?? 0).toLocaleString('ko-KR')}개`,
    matured: `${Number(status.maturedOutcomes ?? 0).toLocaleString('ko-KR')}개`,
    pending: `${Number(status.pendingOutcomes ?? 0).toLocaleString('ko-KR')}개`,
    period: `${formatDate(status.firstObservationDate)} — ${formatDate(status.latestObservationDate)}`,
  }
}

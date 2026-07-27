const FAMILY_LABELS = {
  priceExtension: '가격 확장',
  trendPosition: '추세 위치',
  relativePosition: '상대 위치',
  participation: '시장 참여',
}

export function buildStockBrief({
  observation,
  fundamentalGuard,
  episodeStudy,
}) {
  const families = Object.entries(observation?.families ?? {})
    .map(([key, value]) => ({
      key,
      label: FAMILY_LABELS[key] ?? key,
      value: Number(value),
    }))
    .filter((item) => Number.isFinite(item.value))
    .sort((left, right) => right.value - left.value)
  const lead = families[0]
  const sampleCount = Math.max(
    0,
    ...(episodeStudy?.summaries ?? []).map(
      (summary) => Number(summary.completedCount) || 0,
    ),
  )

  return [
    {
      label: '주도',
      value: lead?.label ?? '—',
      note: lead ? `${Math.round(lead.value)}/100` : '자료 없음',
    },
    {
      label: '기업 상태',
      value: fundamentalGuard?.label ?? '확인 전',
      note: '현재 조회 기준',
    },
    {
      label: '과거 경로',
      value: episodeStudy?.evidenceStatus === 'DESCRIPTIVE_ONLY'
        ? `${sampleCount}건`
        : '표본 부족',
      note: '행동 근거 아님',
    },
  ]
}

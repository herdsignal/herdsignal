export const AREA_LABELS = {
  BUSINESS_HEALTH: '기업 체력',
  EXPECTATION_VALUATION: '기대 · 가격',
  MARKET_SECTOR: '시장 · 섹터',
  CHART_CROWD: '차트 · 군중',
  INFORMATION_CHANGE: '정보 변화',
}

export const STATUS_LABELS = {
  AVAILABLE: '확인',
  PARTIAL: '일부',
  NO_VIEW: '미연결',
  BLOCKED: '차단',
}

const BUSINESS_GROUPS = [
  { id: 'growth', label: '성장', primaryId: 'BUSINESS.PIT.REVENUE_YOY', primaryLabel: '매출 전년 대비' },
  {
    id: 'profitability', label: '수익성', primaryId: 'BUSINESS.PIT.NET_MARGIN',
    primaryLabel: '순이익률', secondaryId: 'BUSINESS.PIT.NET_MARGIN_YOY_CHANGE',
    secondaryLabel: '전년 대비',
  },
  {
    id: 'cash', label: '현금창출', primaryId: 'BUSINESS.PIT.OPERATING_CASH_FLOW_YOY',
    primaryLabel: '영업현금흐름 전년 대비',
  },
  {
    id: 'balance', label: '재무구조', primaryId: 'BUSINESS.PIT.LIABILITIES_TO_ASSETS',
    primaryLabel: '부채/자산', secondaryId: 'BUSINESS.PIT.LIABILITIES_TO_ASSETS_YOY_CHANGE',
    secondaryLabel: '전년 대비',
  },
]

const MARKET_FACT_IDS = new Set([
  'MARKET.SPY.RETURN_63',
  'MARKET.SECTOR.RELATIVE_63',
  'MARKET.ATTRIBUTION.CLASS',
])

const ATTRIBUTION_LABELS = {
  MARKET_COMMON: '시장 공통',
  SECTOR_COMMON: '섹터 공통',
  STOCK_SPECIFIC: '종목 고유',
  MIXED: '혼합',
  NO_DOWNSIDE_ATTRIBUTION: '하락 경로 아님',
}

export function normalized(review) {
  if (!review) return null
  if (review.objective) {
    return {
      status: review.synthesis?.decision ?? review.status,
      headline: review.synthesis?.headline ?? '상태 관찰',
      objective: review.objective,
      mandate: review.mandate,
      portfolioFit: review.portfolioFit,
      veto: review.riskVeto,
      limitations: review.synthesis?.limitations ?? [],
    }
  }
  return {
    status: review.status === 'AVAILABLE' ? 'OBSERVE' : review.status,
    headline: review.status === 'AVAILABLE' ? '상태 관찰' : '데이터 확인 필요',
    objective: review,
    mandate: null,
    portfolioFit: null,
    veto: null,
    limitations: review.dataGate?.reasons ?? [],
  }
}

export function pct(value) {
  if (!Number.isFinite(Number(value))) return '—'
  return `${(Number(value) * 100).toFixed(1)}%`
}

export function signedPercentagePoint(value) {
  if (!Number.isFinite(Number(value))) return '—'
  const percentagePoint = Number(value) * 100
  return `${percentagePoint > 0 ? '+' : ''}${percentagePoint.toFixed(1)}%p`
}

export function businessFacts(objective) {
  const available = new Map(
    (objective?.evidencePacket?.facts ?? [])
      .filter((fact) => fact.quality === 'AVAILABLE')
      .map((fact) => [fact.id, fact]),
  )
  return BUSINESS_GROUPS.flatMap((group) => {
    const primary = available.get(group.primaryId)
    const secondary = available.get(group.secondaryId)
    if (!primary && !secondary) return []
    return [{
      ...group,
      asOfDate: primary?.asOfDate ?? secondary?.asOfDate,
      primaryValue: primary ? pct(primary.value) : '—',
      secondaryValue: secondary ? pct(secondary.value) : null,
    }]
  })
}

export function guidanceFacts(objective) {
  return (objective?.evidencePacket?.facts ?? [])
    .filter((fact) => fact.quality === 'AVAILABLE' && fact.id.startsWith('EXPECTATION.GUIDANCE.'))
    .slice(0, 4)
}

export function marketFacts(objective) {
  return (objective?.evidencePacket?.facts ?? [])
    .filter((fact) => fact.quality === 'AVAILABLE' && MARKET_FACT_IDS.has(fact.id))
    .map((fact) => ({
      ...fact,
      displayValue: fact.id === 'MARKET.ATTRIBUTION.CLASS'
        ? ATTRIBUTION_LABELS[fact.value] ?? fact.value
        : pct(fact.value),
    }))
}

export function pricePathValue(outcome) {
  if (outcome?.status === 'BLOCKED_INTEGRITY') return '검증 차단'
  if (!outcome || outcome.status === 'UNAVAILABLE') return '자료 없음'
  if (outcome.status === 'PENDING') return '대기'
  const value = Number(outcome.priceReturnPct)
  if (!Number.isFinite(value)) return '자료 없음'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

export function integrityLabel(status) {
  if (status === 'VERIFIED') return '원장 검증됨'
  if (status === 'LEGACY_UNVERIFIED') return '기존 기록 · 원장 해시 이전'
  if (status === 'MISMATCH') return '원장 무결성 불일치'
  return '원장 상태 미확인'
}

export function recordDate(value) {
  if (!value) return '기준일 없음'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('ko-KR', { year: 'numeric', month: 'numeric', day: 'numeric' })
}

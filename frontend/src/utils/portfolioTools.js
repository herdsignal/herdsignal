/**
 * utils/portfolioTools.js — 포트폴리오 의사결정 보조 계산.
 *
 * DB/API 변경 없이 frontend에서 기존 포트폴리오, HERD, 히스토리 데이터를 조합한다.
 */

export const TARGET_WEIGHTS_KEY = 'hs_target_weights'

export function readTargetWeights() {
  try {
    return JSON.parse(localStorage.getItem(TARGET_WEIGHTS_KEY) || '{}')
  } catch {
    return {}
  }
}

export function writeTargetWeights(weights) {
  try {
    localStorage.setItem(TARGET_WEIGHTS_KEY, JSON.stringify(weights))
  } catch { /* localStorage 실패 무시 */ }
}

function num(value, fallback = 0) {
  if (value == null || value === '') return fallback
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function stageRank(signal) {
  switch (signal) {
    case 'BUY': return 5
    case 'ADD': return 4
    case 'HOLD': return 3
    case 'REDUCE': return 2
    case 'SELL': return 1
    default: return 3
  }
}

export function equalTargetWeight(count) {
  return count > 0 ? 100 / count : 0
}

export function portfolioRows(portfolio, summary, herdMap, targetWeights) {
  const totalValue = num(summary?.total_value)
  const fallbackTarget = equalTargetWeight(portfolio.length)
  const priceMap = {}
  summary?.stocks?.forEach((s) => { priceMap[s.ticker] = s })

  return portfolio.map((item) => {
    const price = priceMap[item.ticker]
    const marketValue = num(price?.market_value)
    const currentWeight = totalValue > 0 ? marketValue / totalValue * 100 : 0
    const targetWeight = num(targetWeights[item.ticker], fallbackTarget)
    const drift = currentWeight - targetWeight
    const herd = herdMap[item.ticker]
    const signal = herd?.signal ?? 'HOLD'

    let action = '유지'
    if (drift > 5 && (signal === 'SELL' || signal === 'REDUCE')) action = '익절 우선'
    else if (drift > 5) action = '추가매수 금지'
    else if (drift < -5 && (signal === 'BUY' || signal === 'ADD')) action = '분할매수 후보'
    else if (drift < -5) action = '비중 부족'
    else if (signal === 'SELL' || signal === 'REDUCE') action = '일부 덜기'
    else if (signal === 'BUY' || signal === 'ADD') action = '작게 추가'

    return {
      ticker: item.ticker,
      currentWeight,
      targetWeight,
      drift,
      herd,
      signal,
      action,
      marketValue,
    }
  })
}

export function rebalanceIdeas(rows) {
  return [...rows]
    .sort((a, b) => {
      const driftScore = Math.abs(b.drift) - Math.abs(a.drift)
      if (driftScore !== 0) return driftScore
      return stageRank(b.signal) - stageRank(a.signal)
    })
    .slice(0, 4)
}

export function buildChangeSummary(prevMap, nextMap) {
  const changes = []
  Object.entries(nextMap).forEach(([ticker, next]) => {
    const prev = prevMap?.[ticker]
    if (!prev) return
    const prevScore = num(prev.herdScore, null)
    const nextScore = num(next.herdScore, null)
    if (prevScore == null || nextScore == null) return

    const prevSignal = prev.signal ?? 'HOLD'
    const nextSignal = next.signal ?? 'HOLD'
    const scoreDelta = Math.round(nextScore - prevScore)

    if (prevSignal !== nextSignal) {
      changes.push(`${ticker} ${prevSignal} → ${nextSignal}`)
    } else if (Math.abs(scoreDelta) >= 3) {
      changes.push(`${ticker} HERD ${Math.round(prevScore)} → ${Math.round(nextScore)}`)
    }
  })
  return changes.slice(0, 4)
}

export function historyStats(points) {
  if (!points?.length) return null
  const values = points
    .map((p) => num(p.totalValue ?? p.total_value ?? p.value, null))
    .filter((v) => v != null && v > 0)
  if (values.length < 2) return null

  const start = values[0]
  const end = values[values.length - 1]
  let peak = start
  let mdd = 0
  values.forEach((value) => {
    if (value > peak) peak = value
    mdd = Math.min(mdd, (value - peak) / peak * 100)
  })
  return {
    returnPct: (end / start - 1) * 100,
    mdd,
  }
}

export function opportunityRows(watchlist) {
  return [...watchlist]
    .map((item) => {
      const score = num(item.herdScore, 50)
      const signal = item.signal ?? 'HOLD'
      const signalBoost = signal === 'BUY' ? 30 : signal === 'ADD' ? 18 : signal === 'HOLD' ? 4 : -12
      const opportunityScore = Math.max(0, Math.min(100, 100 - score + signalBoost))
      return {
        ...item,
        opportunityScore,
        reason: signal === 'BUY' || signal === 'ADD'
          ? '매수 대기 우선순위 높음'
          : signal === 'HOLD'
            ? '가격 식을 때까지 관찰'
            : '과열 해소 전까지 대기',
      }
    })
    .sort((a, b) => b.opportunityScore - a.opportunityScore)
}

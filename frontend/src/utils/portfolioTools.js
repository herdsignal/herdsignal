/**
 * utils/portfolioTools.js — 포트폴리오 의사결정 보조 계산.
 *
 * DB/API 변경 없이 frontend에서 기존 포트폴리오, HERD, 히스토리 데이터를 조합한다.
 */

export const TARGET_WEIGHTS_KEY = 'hs_target_weights'
export const REBALANCE_SETTINGS_KEY = 'hs_rebalance_settings'

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

export function readRebalanceSettings() {
  try {
    return JSON.parse(localStorage.getItem(REBALANCE_SETTINGS_KEY) || '{}')
  } catch {
    return {}
  }
}

export function writeRebalanceSettings(settings) {
  try {
    localStorage.setItem(REBALANCE_SETTINGS_KEY, JSON.stringify(settings))
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

function signalBias(signal) {
  switch (signal) {
    case 'BUY': return 1.35
    case 'ADD': return 1.15
    case 'REDUCE': return 1.10
    case 'SELL': return 1.30
    default: return 0.65
  }
}

function modeMultiplier(mode) {
  switch (mode) {
    case 'conservative': return 0.55
    case 'aggressive': return 1.25
    default: return 0.85
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

export function opportunityRows(watchlist) {
  return [...watchlist]
    .map((item, index) => {
      const score = num(item.herdV4 ?? item.herdScore, 50)
      const signal = item.signal ?? 'HOLD'
      const actionScore = num(item.actionScore)
      const signalBoost = signal === 'BUY' ? 34 : signal === 'ADD' ? 22 : signal === 'HOLD' ? 2 : -24
      const strengthBoost = actionScore > 0 ? Math.min(16, actionScore / 8) : 0
      const opportunityScore = Math.max(0, Math.min(100, 100 - score + signalBoost))
      return {
        ...item,
        opportunityScore: Math.max(0, Math.min(100, opportunityScore + strengthBoost)),
        opportunityRank: signal === 'BUY' ? 3 : signal === 'ADD' ? 2 : signal === 'HOLD' ? 1 : 0,
        originalIndex: index,
        reason: signal === 'BUY'
          ? 'Flee 우선 대기'
          : signal === 'ADD'
            ? 'Scatter 분할매수 후보'
            : signal === 'HOLD'
              ? 'Calm 관찰'
              : 'Rush/Drift 제외',
      }
    })
    .sort((a, b) => {
      if (b.opportunityRank !== a.opportunityRank) return b.opportunityRank - a.opportunityRank
      if (num(b.actionScore) !== num(a.actionScore)) return num(b.actionScore) - num(a.actionScore)
      if (b.opportunityScore !== a.opportunityScore) return b.opportunityScore - a.opportunityScore
      return a.originalIndex - b.originalIndex
    })
}

export function buildRebalancePlan(rows, options = {}) {
  const budget = Math.max(0, num(options.budget))
  const cashTargetPct = Math.max(0, num(options.cashTargetPct))
  const mode = options.mode ?? 'standard'
  const totalValue = Math.max(0, num(options.totalValue))
  const deployableBudget = Math.max(0, budget * (1 - cashTargetPct / 100))
  const intensity = modeMultiplier(mode)

  const buys = []
  const sells = []
  const holds = []

  rows.forEach((row) => {
    const driftUsd = totalValue > 0 ? Math.abs(row.drift) / 100 * totalValue : 0
    const signal = row.signal ?? 'HOLD'
    const bias = signalBias(signal)

    if (row.drift < -2 && (signal === 'BUY' || signal === 'ADD' || mode === 'aggressive')) {
      buys.push({
        ...row,
        amount: Math.min(deployableBudget, driftUsd * bias * intensity),
        reason: row.drift < -5
          ? '목표 비중보다 부족하고 HERD 신호가 매수권입니다.'
          : '목표 비중 근처지만 HERD 신호가 우호적입니다.',
      })
    } else if (row.drift > 2 && (signal === 'SELL' || signal === 'REDUCE' || mode !== 'conservative')) {
      sells.push({
        ...row,
        amount: driftUsd * bias * intensity,
        reason: row.drift > 5
          ? '목표 비중보다 높아 일부 비중 조정이 필요합니다.'
          : '목표 비중 근처지만 HERD 신호가 군중 밀집권입니다.',
      })
    } else {
      holds.push({
        ...row,
        amount: 0,
        reason: '목표 비중과 HERD 신호가 강한 조정을 요구하지 않습니다.',
      })
    }
  })

  const buyTotal = buys.reduce((sum, item) => sum + item.amount, 0)
  if (buyTotal > deployableBudget && buyTotal > 0) {
    buys.forEach((item) => { item.amount = item.amount / buyTotal * deployableBudget })
  }

  return {
    buys: buys.filter((item) => item.amount > 1).sort((a, b) => b.amount - a.amount),
    sells: sells.filter((item) => item.amount > 1).sort((a, b) => b.amount - a.amount),
    holds: holds.sort((a, b) => Math.abs(b.drift) - Math.abs(a.drift)),
    deployableBudget,
  }
}

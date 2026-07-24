/**
 * utils/portfolioTools.js — 포트폴리오 의사결정 보조 계산.
 *
 * DB/API 변경 없이 frontend에서 기존 포트폴리오, HERD, 히스토리 데이터를 조합한다.
 */

export function targetWeightsFromPortfolio(portfolio) {
  const weights = {}
  ;(portfolio ?? []).forEach((item) => {
    const value = item.targetWeight ?? item.target_weight
    if (value != null) weights[item.ticker] = String(Number(value) * 100)
  })
  return weights
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

function equalTargetWeight(count) {
  return count > 0 ? 100 / count : 0
}

/**
 * 연구용 signal은 화면에 전달되더라도 운영 행동으로 승격하지 않는다.
 * 서버가 명시적으로 승인하고 승인 비율이 0보다 큰 경우만 행동 신호로 본다.
 * 오래된 캐시처럼 operationalAction만 남은 데이터는 항상 HOLD로 닫는다.
 */
export function operationalSignal(item) {
  const ratio = num(item?.operationalActionRatio ?? item?.actionRatio)
  if (item?.actionAuthorized !== true || ratio <= 0) return 'HOLD'
  const action = String(item?.operationalAction ?? '').toUpperCase()
  return ['BUY', 'ADD', 'REDUCE', 'SELL'].includes(action) ? action : 'HOLD'
}

/** 과거 모델의 구간 파생값. 상태 진단 외의 행동 계산에는 사용하지 않는다. */
export function legacySignal(item) {
  return item?.legacySignal ?? item?.stateSignal ?? (
    item?.actionAuthorized == null && num(item?.actionRatio) === 0
      ? item?.signal
      : null
  ) ?? 'HOLD'
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
    const stateSignal = legacySignal(herd)
    const signal = operationalSignal(herd)

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
      stateSignal,
      action,
      marketValue,
      returnPct: num(price?.return_pct, null),
    }
  })
}

export function portfolioRiskWarnings(rows, summary) {
  const items = Array.isArray(rows) ? rows : []
  if (items.length === 0) return []

  const totalValue = num(summary?.total_value)
  const cash = num(summary?.cash_balance)
  const cashRatio = totalValue > 0 ? cash / totalValue * 100 : 0
  const sortedByWeight = [...items].sort((a, b) => b.currentWeight - a.currentWeight)
  const top = sortedByWeight[0]
  const top3Weight = sortedByWeight.slice(0, 3).reduce((sum, item) => sum + item.currentWeight, 0)
  const heatedWeight = items
    .filter((item) => item.signal === 'SELL' || item.signal === 'REDUCE' || num(item.herd?.herdScore, 50) >= 60)
    .reduce((sum, item) => sum + item.currentWeight, 0)
  const buyCandidateCount = items.filter((item) => item.signal === 'BUY' || item.signal === 'ADD').length
  const lossCluster = items
    .filter((item) => num(item.returnPct, 0) <= -15)
    .reduce((sum, item) => sum + item.currentWeight, 0)

  const warnings = []
  if (top && top.currentWeight >= 35) {
    warnings.push({
      level: 'HIGH',
      title: `${top.ticker} 비중 집중`,
      value: `${top.currentWeight.toFixed(1)}%`,
      detail: '단일 종목 변동성이 전체 자산을 크게 흔들 수 있습니다.',
    })
  } else if (top && top.currentWeight >= 28) {
    warnings.push({
      level: 'MEDIUM',
      title: `${top.ticker} 비중 점검`,
      value: `${top.currentWeight.toFixed(1)}%`,
      detail: '목표 비중과 HERD 신호를 함께 확인하세요.',
    })
  }

  if (top3Weight >= 72) {
    warnings.push({
      level: 'MEDIUM',
      title: '상위 3종목 집중',
      value: `${top3Weight.toFixed(1)}%`,
      detail: '수익 기여는 크지만 조정장 낙폭도 같이 커질 수 있습니다.',
    })
  }

  if (heatedWeight >= 45) {
    warnings.push({
      level: 'MEDIUM',
      title: '쏠림 구간 비중',
      value: `${heatedWeight.toFixed(1)}%`,
      detail: 'Drift/Rush 비중이 높아 리밸런싱 후보를 우선 확인하세요.',
    })
  }

  if (buyCandidateCount > 0 && cashRatio < 5) {
    warnings.push({
      level: 'LOW',
      title: '매수 후보 대비 현금 부족',
      value: `${cashRatio.toFixed(1)}%`,
      detail: `${buyCandidateCount}개 후보가 있지만 추가 투입 여력이 낮습니다.`,
    })
  }

  if (lossCluster >= 35) {
    warnings.push({
      level: 'MEDIUM',
      title: '손실 구간 집중',
      value: `${lossCluster.toFixed(1)}%`,
      detail: '손실 종목이 한쪽에 몰려 있어 추가매수 전 신호 검증이 필요합니다.',
    })
  }

  if (warnings.length === 0) {
    return [{
      level: 'CLEAR',
      title: '위험 쏠림 낮음',
      value: '정상',
      detail: '현재 보유 비중과 HERD 구간에서 큰 집중 경고는 없습니다.',
    }]
  }

  return warnings.slice(0, 3)
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
      const score = num(item.herdScore, 50)
      const stateSignal = legacySignal(item)
      const signal = operationalSignal(item)
      const actionScore = num(item.actionScore)
      const signalDays = num(item.signalDurationDays)
      const qualityScore = num(item.qualityScore, 80)
      const signalBoost = signal === 'BUY' ? 34 : signal === 'ADD' ? 22 : signal === 'HOLD' ? 2 : -24
      const strengthBoost = actionScore > 0 ? Math.min(16, actionScore / 8) : 0
      const lifecycleBoost = signalDays >= 6 && signalDays <= 20
        ? 8
        : signalDays > 45
          ? -10
          : signalDays > 0 && signalDays <= 5
            ? -4
            : 0
      const qualityPenalty = qualityScore < 65 ? -12 : 0
      const opportunityScore = Math.max(0, Math.min(100, 100 - score + signalBoost))
      const adjustedScore = Math.max(0, Math.min(100, opportunityScore + strengthBoost + lifecycleBoost + qualityPenalty))
      const queueState = signal === 'BUY' || signal === 'ADD'
        ? adjustedScore >= 80
          ? 'READY'
          : adjustedScore >= 55 ? 'WATCH' : 'WAIT'
        : signal === 'HOLD'
          ? 'WAIT'
          : 'AVOID'
      return {
        ...item,
        stateSignal,
        signal,
        opportunityScore: adjustedScore,
        queueState,
        queueLabel: queueState === 'READY'
          ? '우선 확인'
          : queueState === 'WATCH'
            ? '관찰 유지'
            : queueState === 'AVOID'
              ? '고밀집 관찰'
              : '대기',
        queueDetail: signalDays > 45
          ? '오래된 신호라 추격 금지'
          : signalDays > 0 && signalDays <= 5
            ? '초입 신호 확인 필요'
            : qualityScore < 65
              ? '데이터 품질 확인 필요'
              : signal === 'BUY' || signal === 'ADD'
                ? '승인 행동 확인'
                : '연구 상태 관찰',
        opportunityRank: signal === 'BUY' ? 3 : signal === 'ADD' ? 2 : signal === 'HOLD' ? 1 : 0,
        originalIndex: index,
        reason: signal !== 'HOLD'
          ? '승인된 운영 행동'
          : `${stateSignal} 연구 상태`,
      }
    })
    .sort((a, b) => {
      if (b.opportunityRank !== a.opportunityRank) return b.opportunityRank - a.opportunityRank
      if (num(b.actionScore) !== num(a.actionScore)) return num(b.actionScore) - num(a.actionScore)
      if (b.opportunityScore !== a.opportunityScore) return b.opportunityScore - a.opportunityScore
      return a.originalIndex - b.originalIndex
    })
}

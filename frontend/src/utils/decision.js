/**
 * utils/decision.js — HERD 점수를 장기투자 행동 문장으로 변환.
 *
 * 운영 HERD 점수는 변경하지 않는다.
 * 화면에서만 보유 여부와 포트폴리오 비중을 함께 해석한다.
 */
import { normalizeStage } from './herdStage'

export function signalDesc(signal) {
  switch (signal) {
    case 'BUY':    return '적극 매수'
    case 'ADD':    return '추가 매수 고려'
    case 'HOLD':   return '보유 유지'
    case 'REDUCE': return '일부 익절 고려'
    case 'SELL':   return '적극 익절'
    default:       return '보유 유지'
  }
}

export function signalLongDesc(signal) {
  switch (signal) {
    case 'BUY':    return '군중이 크게 이탈한 구간입니다. 품질 훼손이 없다면 적극 추가매수를 검토합니다.'
    case 'ADD':    return '군중이 흩어진 구간입니다. 한 번에 들어가기보다 분할매수 관점이 적합합니다.'
    case 'HOLD':   return '군중 균형 구간입니다. 새 행동보다 기존 계획을 유지하는 구간입니다.'
    case 'REDUCE': return '군중 쏠림이 진행 중입니다. 과도한 비중이라면 일부 익절을 검토합니다.'
    case 'SELL':   return '군중이 한쪽으로 밀집한 구간입니다. 장기 보유분 일부를 현금화할 수 있는 구간입니다.'
    default:       return '현재는 추가 판단 데이터가 제한적입니다.'
  }
}

export function stageDesc(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return '군중 밀집 · 적극 익절'
    case 'drift':   return '쏠림 진행 · 일부 익절 고려'
    case 'scatter': return '군중 흩어짐 · 분할 매수'
    case 'flee':    return '군중 이탈 · 적극 매수'
    default:        return '군중 균형 · 보유 유지'
  }
}

function toNumber(value) {
  if (value == null || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function holdingValue(holding, summaryStock) {
  const summaryValue = toNumber(summaryStock?.market_value ?? summaryStock?.marketValue)
  if (summaryValue != null) return summaryValue

  const avgPrice = toNumber(holding?.avgPrice ?? holding?.avg_price)
  const quantity = toNumber(holding?.quantity)
  if (avgPrice == null || quantity == null) return null
  return avgPrice * quantity
}

function portfolioWeight(holding, summary, summaryStock) {
  const total = toNumber(summary?.total_value ?? summary?.totalValue)
  const value = holdingValue(holding, summaryStock)
  if (total == null || total <= 0 || value == null) return null
  return value / total * 100
}

export function buildDecision({ herdData, holding, summary }) {
  const score = toNumber(herdData?.herdV4 ?? herdData?.herdScore) ?? 50
  const signal = herdData?.signal ?? 'HOLD'
  const stage = herdData?.herdStage ?? 'Herd Calm'
  const ticker = herdData?.ticker ?? holding?.ticker ?? ''
  const summaryStock = summary?.stocks?.find?.((s) => s.ticker === ticker)
  const weight = portfolioWeight(holding, summary, summaryStock)
  const hasHolding = Boolean(holding)

  const notes = []
  if (hasHolding) {
    if (weight != null && weight >= 25) {
      notes.push(`현재 포트폴리오 비중이 약 ${weight.toFixed(1)}%로 높아 추가매수보다 비중 관리가 우선입니다.`)
    } else if (weight != null && weight >= 15) {
      notes.push(`현재 포트폴리오 비중은 약 ${weight.toFixed(1)}%입니다. 추가매수는 작게 나누는 편이 안전합니다.`)
    } else if (weight != null) {
      notes.push(`현재 포트폴리오 비중은 약 ${weight.toFixed(1)}%입니다. 신호가 강하면 분할매수 여지가 있습니다.`)
    } else {
      notes.push('보유 종목입니다. 비중 데이터가 제한적이므로 평단가와 목표 비중을 함께 확인하세요.')
    }
  } else if (signal === 'BUY' || signal === 'ADD') {
    notes.push('미보유 종목입니다. 신규 진입은 한 번에 매수하지 말고 분할 접근이 적합합니다.')
  } else {
    notes.push('미보유 종목입니다. 현재 구간에서는 추격 매수보다 관찰 우선입니다.')
  }

  let title = signalDesc(signal)
  let subtitle = signalLongDesc(signal)
  let priority = '중립'

  if ((signal === 'BUY' || signal === 'ADD') && hasHolding && weight != null && weight >= 25) {
    title = '추가매수 보류'
    subtitle = 'HERD는 저점권이지만 이미 비중이 높습니다. 현금 투입보다 리스크 관리가 먼저입니다.'
    priority = '주의'
  } else if ((signal === 'SELL' || signal === 'REDUCE') && !hasHolding) {
    title = '신규매수 보류'
    subtitle = '군중 밀집 신호입니다. 보유자가 아니라면 가격이 식을 때까지 기다리는 편이 낫습니다.'
    priority = '주의'
  } else if (signal === 'BUY' || signal === 'SELL') {
    priority = '높음'
  }

  return {
    score,
    stage,
    signal,
    title,
    subtitle,
    priority,
    notes,
  }
}

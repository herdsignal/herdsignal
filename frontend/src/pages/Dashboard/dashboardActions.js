import { signalDesc as decisionSignalDesc } from '../../utils/decision'
import {
  actionBasisLabel,
  actionIntensityLabel,
  formatActionScore,
} from '../../utils/actionIntensity'
import { signalStyle as sharedSignalStyle } from '../../utils/signalStyle'
import { operationalSignal } from '../../utils/portfolioTools'
import {
  normalizeStage,
  stageBadgeStyle,
  stageColor,
} from '../../utils/herdStage'

export { normalizeStage, stageColor }

export function stageDesc(stage) {
  switch (normalizeStage(stage)) {
    case 'rush': return '군중 밀집 · 익절 근거 미채택'
    case 'drift': return '쏠림 진행 · 행동 검증 중'
    case 'scatter': return '군중 분산 · 매수 근거 미채택'
    case 'flee': return '군중 이탈 · 매수 근거 미채택'
    default: return '군중 균형 · 보유 유지'
  }
}

export function signalStyle(signal) {
  return sharedSignalStyle(signal)
}

export function badgeStyle(stage) {
  return stageBadgeStyle(stage)
}

export { formatActionScore }

export function formatActionText(herd) {
  const action = herd?.actionLabel ?? decisionSignalDesc(herd?.signal)
  const strength = formatActionScore(herd?.actionScore)
  return [strength, action].filter(Boolean).join(' · ')
}

export function formatActionBasis(herd) {
  return actionBasisLabel(herd)
}

export function formatActionCode(herd) {
  if (!herd?.signal) return 'HOLD'
  const intensity = actionIntensityLabel(herd)
  return intensity === '관찰' ? herd.signal : `${herd.signal} · ${intensity}`
}

export function positionGap(row) {
  if (!row) return null
  const gap = Number(row.targetWeight ?? 0) - Number(row.currentWeight ?? 0)
  return Number.isFinite(gap) ? gap : null
}

export function buildPositionAction(herd, row) {
  const gap = positionGap(row)
  const signal = operationalSignal(herd)
  const operationalHerd = { ...herd, signal }
  const isBuy = signal === 'BUY' || signal === 'ADD'
  const isSell = signal === 'SELL' || signal === 'REDUCE'
  const base = {
    code: formatActionCode(operationalHerd),
    text: formatActionText(operationalHerd),
    basis: formatActionBasis(operationalHerd),
    muted: false,
  }

  if (gap == null) return base

  const absoluteGap = Math.abs(gap).toFixed(1)
  if (isBuy && gap < -2) {
    return {
      code: 'WAIT',
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 추가매수 보류`,
      basis: `목표보다 ${absoluteGap}%p 초과 · HERD는 매수권`,
      muted: true,
    }
  }
  if (isBuy && gap > 2) {
    return {
      ...base,
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 목표비중 채우기`,
      basis: `목표까지 ${gap.toFixed(1)}%p 부족 · 분할 투입 우선`,
    }
  }
  if (isSell && gap < -2) {
    return {
      ...base,
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 비중 축소 우선`,
      basis: `목표보다 ${absoluteGap}%p 초과 · 익절 신호와 일치`,
    }
  }
  if (isSell && gap > 2) {
    return {
      ...base,
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 익절은 작게`,
      basis: `목표까지 ${gap.toFixed(1)}%p 부족 · 과도한 축소 주의`,
    }
  }
  if (signal === 'HOLD' && Math.abs(gap) > 5) {
    return {
      ...base,
      text: gap > 0 ? '강도 보통 · 비중 부족' : '강도 보통 · 비중 초과',
      basis: gap > 0
        ? `목표까지 ${gap.toFixed(1)}%p 부족 · HERD는 보유`
        : `목표보다 ${absoluteGap}%p 초과 · HERD는 보유`,
    }
  }
  return base
}

export function actionPriority(signal) {
  switch (signal) {
    case 'SELL': return 0
    case 'REDUCE': return 1
    case 'BUY': return 2
    case 'ADD': return 3
    case 'HOLD': return 4
    default: return 5
  }
}

export function queuePriority(actionCode) {
  if (actionCode?.startsWith('SELL')) return 0
  if (actionCode?.startsWith('REDUCE')) return 1
  if (actionCode?.startsWith('BUY')) return 2
  if (actionCode?.startsWith('ADD')) return 3
  if (actionCode?.startsWith('WAIT')) return 4
  return 5
}

export function sortPortfolioItems(list, rows, herdMap, sortMode) {
  const rowMap = new Map(rows.map((row) => [row.ticker, row]))
  return [...list].sort((left, right) => {
    const leftHerd = herdMap[left.ticker]
    const rightHerd = herdMap[right.ticker]
    const leftScore = Number(leftHerd?.herdScore ?? 50)
    const rightScore = Number(rightHerd?.herdScore ?? 50)

    if (sortMode === 'herdLow') return leftScore - rightScore
    if (sortMode === 'herdHigh') return rightScore - leftScore
    if (sortMode === 'weight') {
      return Number(rowMap.get(right.ticker)?.currentWeight ?? 0) -
        Number(rowMap.get(left.ticker)?.currentWeight ?? 0)
    }

    const priorityDifference =
      actionPriority(leftHerd?.signal) - actionPriority(rightHerd?.signal)
    if (priorityDifference !== 0) return priorityDifference
    const actionDifference =
      Number(rightHerd?.actionScore ?? 0) - Number(leftHerd?.actionScore ?? 0)
    return actionDifference !== 0
      ? actionDifference
      : left.ticker.localeCompare(right.ticker)
  })
}

export function refreshResultText(priceResult, herdResult, spyResult) {
  const done = []
  const failed = []
  if (priceResult.status === 'fulfilled') done.push('현재가 갱신')
  else failed.push('가격')
  if (herdResult.status === 'fulfilled') done.push('HERD 조회')
  else failed.push('HERD')
  if (spyResult.status === 'fulfilled') done.push('SPY 갱신')
  else failed.push('SPY')
  if (done.length === 0) return '새로고침 실패'
  if (failed.length > 0) return `${done.join(' · ')} · ${failed.join('/')} 실패`
  return done.join(' · ')
}

import { API_HOST } from '../../utils/apiConfig'
import { HERD_HISTORY_PERIODS } from '../../utils/historyPeriods'
import {
  normalizeStage,
  stageBadgeStyle,
  stageColor,
} from '../../utils/herdStage'

export { API_HOST, normalizeStage, stageColor }
export const HISTORY_PERIODS = HERD_HISTORY_PERIODS

export function badgeColors(stage) {
  const badge = stageBadgeStyle(stage)
  return { background: badge.bg, color: badge.color }
}

export function getTimingSignal(score) {
  if (score >= 75) return '군중 밀집 · 익절 근거 미채택'
  if (score >= 60) return '군중 쏠림 · 행동 근거 검증 중'
  if (score >= 40) return '군중 균형'
  if (score >= 15) return '군중 분산 · 매수 근거 미채택'
  return '군중 이탈 · 매수 근거 미채택'
}

export function journalActionLabel(type) {
  switch (type) {
    case 'BUY': return '매수 기록'
    case 'HOLD': return '보류 기록'
    case 'SELL': return '익절 기록'
    default: return '판단 기록'
  }
}

export const BTN_LABELS = {
  portfolio: {
    idle: '포트폴리오 추가',
    loading: '추가 중…',
    added: '추가됨 ✓',
    exists: '이미 추가됨',
  },
  watchlist: {
    idle: '관심종목 추가',
    loading: '추가 중…',
    added: '추가됨 ✓',
    exists: '이미 추가됨',
  },
}

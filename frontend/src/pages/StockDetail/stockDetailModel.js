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

import {
  actionBasisLabel,
  actionIntensity,
  formatActionScore,
} from '../../utils/actionIntensity'
import { signalStyle as sharedSignalStyle } from '../../utils/signalStyle'
import { API_HOST } from '../../utils/apiConfig'
import { HERD_HISTORY_PERIODS } from '../../utils/historyPeriods'
import {
  normalizeStage,
  stageBadgeStyle,
  stageColor,
} from '../../utils/herdStage'

export { API_HOST, normalizeStage, stageColor }

/*
 * ── HERD v3 지표 정의 (가중치 순) ─────────────
 *
 * weight: HERD 점수 산출 시 반영 비율 (%)
 * min/max: 바 너비 정규화 기준. ma200Deviation은 ±50% 기준
 */
export const INDICATORS = [
  { key: 'monthlyRsi',     label: '월봉 RSI',       weight: 24, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'ma200Weekly',    label: '200주 MA 위치',  weight: 20, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'weeklyRsi',      label: '주봉 RSI',       weight: 19, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'position52w',    label: '52주 위치',      weight: 19, min: 0,   max: 100, unit: '%', signed: false },
  { key: 'ma200Deviation', label: 'MA200 이격도',   weight: 18, min: -50, max: 50,  unit: '%', signed: true  },
]

export const HISTORY_PERIODS = HERD_HISTORY_PERIODS

/* ── 유틸 ─────────────────────────────────── */

/** signal → 배지 배경/텍스트 색 */
export function signalStyle(signal) {
  return sharedSignalStyle(signal)
}

/** stage → 티커 배지 배경/텍스트 색 */
export function badgeColors(stage) {
  const badge = stageBadgeStyle(stage)
  return { background: badge.bg, color: badge.color }
}

/** score → Timing Signal 텍스트 */
export function getTimingSignal(score) {
  if (score >= 75) return '군중 밀집 상태입니다 · 익절 근거는 미채택입니다'
  if (score >= 60) return '군중 쏠림 상태입니다 · 비중 행동은 검증 중입니다'
  if (score >= 40) return '군중 균형 상태입니다'
  if (score >= 15) return '군중 분산 상태입니다 · 매수 근거는 미채택입니다'
  return '군중 이탈 상태입니다 · 매수 근거는 미채택입니다'
}

/** 지표 값 → 바 너비 % (0~100, min~max 범위 정규화) */
export function normalizeBar(value, min, max) {
  return Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
}

/** 지표 값 → 표시 문자열 */
export function formatIndicator(value, unit, signed) {
  const fixed = value.toFixed(1)
  return signed && value > 0 ? `+${fixed}${unit}` : `${fixed}${unit}`
}

export function formatMultiplier(value) {
  if (value == null) return '×1.00'
  return `×${Number(value).toFixed(2)}`
}

export function epsMultiplierDesc(value) {
  const n = Number(value ?? 1)
  if (n <= 0.85) return '4연속 beat'
  if (n <= 0.90) return '3연속 beat'
  if (n <= 0.95) return '2연속 beat'
  if (n >= 1.15) return '4연속 miss'
  if (n >= 1.10) return '3연속 miss'
  if (n >= 1.05) return '2연속 miss'
  return '중립'
}

export function sectorMultiplierDesc(value) {
  const n = Number(value ?? 1)
  if (n <= 0.90) return '섹터 대비 강한 우위'
  if (n <= 0.95) return '섹터 대비 우위'
  if (n >= 1.10) return '섹터 대비 뚜렷한 약세'
  if (n >= 1.05) return '섹터 약세'
  return '중립'
}

export { formatActionScore }

export function formatActionRatio(value) {
  return actionIntensity(value).label
}

export function formatActionBasis(data) {
  return actionBasisLabel(data)
}

export function formatActionMeta(data) {
  return [
    data?.actionModelVersion ?? 'HERD_v6.1',
    formatActionScore(data?.actionScore),
  ].filter(Boolean).join(' · ')
}

export function evidenceTone(type) {
  switch (type) {
    case 'buy': return 'var(--flee)'
    case 'sell': return 'var(--rush)'
    case 'warning': return 'var(--drift)'
    default: return 'var(--calm)'
  }
}

export function buildSignalEvidence(data) {
  if (!data) return []

  const items = []
  const push = (label, value, caption, type = 'neutral') => {
    if (value == null) return
    if (typeof value !== 'string' && Number.isNaN(Number(value))) return
    items.push({
      label,
      value: typeof value === 'string' ? value : Math.round(Number(value)),
      caption,
      type,
    })
  }

  const monthlyRsi = Number(data.monthlyRsi)
  const weeklyRsi = Number(data.weeklyRsi)
  const position52w = Number(data.position52w)
  const ma200Weekly = Number(data.ma200Weekly)
  const ma200Deviation = Number(data.ma200Deviation)
  const epsMultiplier = Number(data.epsMultiplier ?? 1)
  const sectorMultiplier = Number(data.sectorMultiplier ?? 1)

  if (monthlyRsi <= 30) push('월봉 RSI', monthlyRsi, '장기 심리 하단', 'buy')
  else if (monthlyRsi >= 70) push('월봉 RSI', monthlyRsi, '장기 심리 상단', 'sell')

  if (weeklyRsi <= 30) push('주봉 RSI', weeklyRsi, '중기 과매도권', 'buy')
  else if (weeklyRsi >= 70) push('주봉 RSI', weeklyRsi, '중기 과열권', 'sell')

  if (position52w <= 30) push('52주 위치', `${position52w.toFixed(1)}%`, '연중 하단권', 'buy')
  else if (position52w >= 70) push('52주 위치', `${position52w.toFixed(1)}%`, '연중 상단권', 'sell')

  if (ma200Weekly <= 30) push('200주 MA', ma200Weekly, '장기 추세 하단', 'buy')
  else if (ma200Weekly >= 70) push('200주 MA', ma200Weekly, '장기 추세 상단', 'sell')

  if (ma200Deviation <= 30) push('MA200 이격', ma200Deviation, '장기선 대비 눌림', 'buy')
  else if (ma200Deviation >= 70) push('MA200 이격', ma200Deviation, '장기선 대비 과열', 'sell')

  if (epsMultiplier < 1) {
    items.push({
      label: 'EPS 보정',
      value: formatMultiplier(epsMultiplier),
      caption: epsMultiplierDesc(epsMultiplier),
      type: 'buy',
    })
  } else if (epsMultiplier > 1) {
    items.push({
      label: 'EPS 보정',
      value: formatMultiplier(epsMultiplier),
      caption: epsMultiplierDesc(epsMultiplier),
      type: 'warning',
    })
  }

  if (sectorMultiplier < 1) {
    items.push({
      label: '섹터 강도',
      value: formatMultiplier(sectorMultiplier),
      caption: sectorMultiplierDesc(sectorMultiplier),
      type: 'buy',
    })
  } else if (sectorMultiplier > 1) {
    items.push({
      label: '섹터 강도',
      value: formatMultiplier(sectorMultiplier),
      caption: sectorMultiplierDesc(sectorMultiplier),
      type: 'warning',
    })
  }

  if (items.length === 0) {
    items.push({
      label: 'HERD 균형',
      value: Math.round(data.herdV4 ?? data.herdScore ?? 50),
      caption: '강한 쏠림 없음',
      type: 'neutral',
    })
  }

  return items.slice(0, 5)
}

export function journalActionLabel(type) {
  switch (type) {
    case 'BUY': return '매수 기록'
    case 'HOLD': return '보류 기록'
    case 'SELL': return '익절 기록'
    default: return '판단 기록'
  }
}

/* ── 버튼 레이블 매핑 ─────────────────────── */
export const BTN_LABELS = {
  portfolio: {
    idle:    '포트폴리오 추가',
    loading: '추가 중…',
    added:   '추가됨 ✓',
    exists:  '이미 추가됨',
  },
  watchlist: {
    idle:    '관심종목 추가',
    loading: '추가 중…',
    added:   '추가됨 ✓',
    exists:  '이미 추가됨',
  },
}

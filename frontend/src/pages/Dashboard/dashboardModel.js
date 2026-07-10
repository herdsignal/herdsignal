import { signalDesc as decisionSignalDesc } from '../../utils/decision'
import { scoreColor, stageLabelFromScore } from '../../utils/herdStage'

export const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

/* ── localStorage 캐시 키 ──────────────────── */
export const CACHE_KEY_REALTIME    = 'hs_portfolio_realtime'
export const CACHE_KEY_HERD        = 'hs_portfolio_herd'
export const CACHE_KEY_SPY         = 'hs_spy_herd'
export const CACHE_KEY_SPY_HISTORY = 'hs_spy_history'
export const CACHE_KEY_SPY_HISTORY_VERSION = 'v2'
export const CACHE_KEY_TIME        = 'hs_cache_time'
export const CACHE_KEY_VERSION     = 'hs_dashboard_cache_version'
export const CACHE_KEY_PORTFOLIO_SORT = 'hs_dashboard_sort'
export const DASHBOARD_CACHE_VERSION = 'v3-logo'
export const DASHBOARD_CACHE_TTL_MS = 30 * 60 * 1000

export const HISTORY_PERIODS = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '1y', label: '1Y' },
  { value: '3y', label: '3Y' },
]

export const ASSET_HISTORY_PERIODS = [
  { value: 'month', label: '1개월' },
  { value: 'year', label: '1년' },
  { value: 'all', label: '전체' },
]

export const PORTFOLIO_SORT_OPTIONS = [
  { value: 'action', label: '행동순' },
  { value: 'herdLow', label: 'HERD 낮은순' },
  { value: 'herdHigh', label: 'HERD 높은순' },
  { value: 'weight', label: '비중순' },
]

export const REFRESH_SCOPE_TITLE = 'yfinance 현재가, HERD DB 조회, SPY 최신 점수만 갱신합니다. 히스토리와 신뢰도는 각 화면에서 별도 조회됩니다.'

/** localStorage에서 JSON 파싱. 실패 시 null 반환 */
export function readCache(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** localStorage에 JSON 저장. 실패 시 조용히 무시 */
export function writeCache(key, data) {
  try {
    localStorage.setItem(key, JSON.stringify(data))
  } catch { /* 용량 초과 등 무시 */ }
}

export function formatInputDate(value) {
  const date = value ? new Date(value) : new Date()
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function spyHistoryCacheKey(period) {
  return `${CACHE_KEY_SPY_HISTORY}_${period}_${CACHE_KEY_SPY_HISTORY_VERSION}`
}

export function ensureDashboardCacheVersion() {
  try {
    if (localStorage.getItem(CACHE_KEY_VERSION) === DASHBOARD_CACHE_VERSION) {
      return false
    }

    [
      CACHE_KEY_REALTIME,
      CACHE_KEY_HERD,
      CACHE_KEY_SPY,
      CACHE_KEY_TIME,
      ...HISTORY_PERIODS.map((period) => spyHistoryCacheKey(period.value)),
    ].forEach((key) => localStorage.removeItem(key))

    localStorage.setItem(CACHE_KEY_VERSION, DASHBOARD_CACHE_VERSION)
    return true
  } catch {
    return false
  }
}

export function minSpyHistoryPoints(period) {
  switch (period) {
    case '1m': return 4
    case '3m': return 8
    case '1y': return 20
    case '3y': return 50
    default: return 4
  }
}

export function isUsableSpyHistoryCache(period, points) {
  return Array.isArray(points) && points.length >= minSpyHistoryPoints(period)
}

/** backend camelCase / Python snake_case 포트폴리오 요약을 화면 모델(snake_case)로 통일 */
export function normalizePortfolioSummary(data) {
  if (!data) return null
  const investedValue = data.invested_value ?? data.investedValue ?? data.total_value ?? data.totalValue ?? null
  const cashBalance = data.cash_balance ?? data.cashBalance ?? 0
  const totalAssetValue = data.total_asset_value ?? data.totalAssetValue ??
    (investedValue == null ? null : Number(investedValue) + Number(cashBalance ?? 0))
  return {
    total_value:      totalAssetValue,
    invested_value:   investedValue,
    cash_balance:     cashBalance,
    total_asset_value: totalAssetValue,
    total_cost:       data.total_cost       ?? data.totalCost       ?? null,
    total_return_pct: data.total_return_pct ?? data.totalReturnPct  ?? null,
    daily_change_pct: data.daily_change_pct ?? data.dailyChangePct  ?? null,
    stocks: (data.stocks ?? []).map((s) => ({
      ticker:           s.ticker,
      avg_price:        s.avg_price        ?? s.avgPrice        ?? null,
      quantity:         s.quantity         ?? null,
      current_price:    s.current_price    ?? s.currentPrice    ?? null,
      market_value:     s.market_value     ?? s.marketValue     ?? null,
      return_pct:       s.return_pct       ?? s.returnPct       ?? null,
      daily_change_pct: s.daily_change_pct ?? s.dailyChangePct  ?? null,
    })),
  }
}

/** 캐시 저장 시각을 ISO string으로 기록하고 Date 객체 반환 */
export function saveCacheTime() {
  const now = new Date()
  localStorage.setItem(CACHE_KEY_TIME, now.toISOString())
  return now
}

/** 현재가/HERD 묶음 캐시는 30분까지만 자동 재사용한다. */
export function isDashboardCacheFresh(now = Date.now()) {
  try {
    const savedAt = new Date(localStorage.getItem(CACHE_KEY_TIME) || '').getTime()
    return Number.isFinite(savedAt) && now - savedAt <= DASHBOARD_CACHE_TTL_MS
  } catch {
    return false
  }
}

/** 서로 함께 사용되는 포트폴리오 캐시를 한 번에 무효화한다. */
export function clearPortfolioCaches() {
  try {
    localStorage.removeItem(CACHE_KEY_REALTIME)
    localStorage.removeItem(CACHE_KEY_HERD)
    localStorage.removeItem(CACHE_KEY_TIME)
  } catch { /* 브라우저 저장소 접근 실패는 다음 API 조회로 복구 */ }
}

/* ── 유틸 ─────────────────────────────────── */

/** "Herd Scatter" → "scatter" */
export function normalizeStage(stage) {
  const s = (stage || '').toLowerCase()
  return s.startsWith('herd ') ? s.slice(5) : s
}

/** stage → CSS 변수 색상 */
export function stageColor(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return 'var(--rush)'
    case 'drift':   return 'var(--drift)'
    case 'scatter': return 'var(--scatter)'
    case 'flee':    return 'var(--flee)'
    default:        return 'var(--calm)'
  }
}

/** stage → 한국어 설명 (배너 하단) */
export function stageDesc(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return '군중 밀집 · 적극 익절'
    case 'drift':   return '쏠림 진행 · 일부 익절 고려'
    case 'scatter': return '군중 흩어짐 · 분할 매수'
    case 'flee':    return '군중 이탈 · 적극 매수'
    default:        return '군중 균형 · 보유 유지'
  }
}

/** signal → 배지 배경·텍스트 색 */
export function signalStyle(signal) {
  switch (signal) {
    case 'SELL':   return { bg: 'rgba(239,68,68,0.1)',    color: '#EF4444' }
    case 'REDUCE': return { bg: 'rgba(249,115,22,0.1)',   color: '#F97316' }
    case 'HOLD':   return { bg: 'rgba(163,170,184,0.14)', color: 'var(--calm)' }
    case 'ADD':    return { bg: 'rgba(96,165,250,0.12)',  color: '#60A5FA' }
    case 'BUY':    return { bg: 'rgba(59,130,246,0.12)',  color: '#3B82F6' }
    default:       return { bg: 'rgba(163,170,184,0.14)', color: 'var(--calm)' }
  }
}

/** stage → 티커 배지 배경·텍스트 색 */
export function badgeStyle(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return { bg: 'rgba(239,68,68,0.12)',   color: 'var(--rush)' }
    case 'drift':   return { bg: 'rgba(249,115,22,0.12)',  color: 'var(--drift)' }
    case 'scatter': return { bg: 'rgba(96,165,250,0.12)',  color: 'var(--scatter)' }
    case 'flee':    return { bg: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:        return { bg: 'rgba(163,170,184,0.13)', color: 'var(--calm)' }
  }
}

export function formatActionScore(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `강도 ${Math.round(n)}`
}

export function formatActionText(herd) {
  const action = herd?.actionLabel ?? decisionSignalDesc(herd?.signal)
  const strength = formatActionScore(herd?.actionScore)
  return [strength, action].filter(Boolean).join(' · ')
}

export function formatActionBasis(herd) {
  const ratio = Number(herd?.actionRatio ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return '현재 비중 유지'

  const pct = Math.round(ratio * 100)
  if (herd?.signal === 'BUY' || herd?.signal === 'ADD') {
    return `목표 투자금 기준 ${pct}% 분할 투입`
  }
  if (herd?.signal === 'SELL' || herd?.signal === 'REDUCE') {
    return `보유 평가금액 기준 ${pct}% 축소`
  }
  return '현재 비중 유지'
}

export function formatActionCode(herd) {
  if (!herd?.signal) return 'HOLD'
  const ratio = Number(herd.actionRatio ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return herd.signal
  return `${herd.signal} ${Math.round(ratio * 100)}%`
}

export function positionGap(row) {
  if (!row) return null
  const gap = Number(row.targetWeight ?? 0) - Number(row.currentWeight ?? 0)
  return Number.isFinite(gap) ? gap : null
}

export function buildPositionAction(herd, row) {
  const gap = positionGap(row)
  const signal = herd?.signal ?? 'HOLD'
  const isBuy = signal === 'BUY' || signal === 'ADD'
  const isSell = signal === 'SELL' || signal === 'REDUCE'
  const base = {
    code: formatActionCode(herd),
    text: formatActionText(herd),
    basis: formatActionBasis(herd),
    muted: false,
  }

  if (gap == null) return base

  const absGap = Math.abs(gap).toFixed(1)
  if (isBuy && gap < -2) {
    return {
      code: 'WAIT',
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 추가매수 보류`,
      basis: `목표보다 ${absGap}%p 초과 · HERD는 매수권`,
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
      basis: `목표보다 ${absGap}%p 초과 · 익절 신호와 일치`,
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
        : `목표보다 ${absGap}%p 초과 · HERD는 보유`,
    }
  }

  return base
}

export function actionPriority(signal) {
  switch (signal) {
    case 'SELL':   return 0
    case 'REDUCE': return 1
    case 'BUY':    return 2
    case 'ADD':    return 3
    case 'HOLD':   return 4
    default:       return 5
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
  return [...list].sort((a, b) => {
    const aHerd = herdMap[a.ticker]
    const bHerd = herdMap[b.ticker]
    const aScore = Number(aHerd?.herdV4 ?? aHerd?.herdScore ?? 50)
    const bScore = Number(bHerd?.herdV4 ?? bHerd?.herdScore ?? 50)

    if (sortMode === 'herdLow') return aScore - bScore
    if (sortMode === 'herdHigh') return bScore - aScore
    if (sortMode === 'weight') {
      const aWeight = Number(rowMap.get(a.ticker)?.currentWeight ?? 0)
      const bWeight = Number(rowMap.get(b.ticker)?.currentWeight ?? 0)
      return bWeight - aWeight
    }

    const priorityDiff = actionPriority(aHerd?.signal) - actionPriority(bHerd?.signal)
    if (priorityDiff !== 0) return priorityDiff

    const aAction = Number(aHerd?.actionScore ?? 0)
    const bAction = Number(bHerd?.actionScore ?? 0)
    if (bAction !== aAction) return bAction - aAction

    return a.ticker.localeCompare(b.ticker)
  })
}

export function refreshResultText(priceRes, herdRes, spyRes) {
  const done = []
  const failed = []

  if (priceRes.status === 'fulfilled') done.push('현재가 갱신')
  else failed.push('가격')

  if (herdRes.status === 'fulfilled') done.push('HERD 조회')
  else failed.push('HERD')

  if (spyRes.status === 'fulfilled') done.push('SPY 갱신')
  else failed.push('SPY')

  if (done.length === 0) return '새로고침 실패'
  if (failed.length > 0) return `${done.join(' · ')} · ${failed.join('/')} 실패`
  return done.join(' · ')
}

/** USD 금액 포맷: $1,234.56 */
export function fmtUSD(value) {
  if (value == null) return '—'
  return `$${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** 퍼센트 포맷: +12.34% / -3.98% */
export function fmtPct(value) {
  if (value == null) return '—'
  const n = Number(value)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

/** 보유 수량 포맷: 정수는 12주, 소수는 12.3456주 */
export function fmtShares(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('ko-KR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  })}주`
}

export function fmtWeightGap(row) {
  if (!row) return ''
  const gap = row.targetWeight - row.currentWeight
  if (Math.abs(gap) < 0.05) return '목표 근처'
  return gap > 0
    ? `목표까지 ${gap.toFixed(1)}%p`
    : `목표 초과 ${Math.abs(gap).toFixed(1)}%p`
}

/** 수익률 색상: 양수→초록, 음수→빨강, 0→회색 */
export function pctColor(value) {
  if (value == null) return 'var(--text-3)'
  const n = Number(value)
  if (n > 0)  return '#22C55E'
  if (n < 0)  return '#EF4444'
  return 'var(--text-3)'
}

/** 업데이트 완료 시간 포맷: "오후 1:35" */
export function fmtTime(date) {
  if (!date) return ''
  return date.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })
}

/** 차트 X축 날짜 포맷: 2026-06-30 → 6/30 */
export function fmtAxisDate(dateStr) {
  const d = new Date(dateStr)
  return Number.isNaN(d.getTime()) ? dateStr : `${d.getMonth() + 1}/${d.getDate()}`
}

export function normalizeHistoryPoint(point) {
  const investedValue = point.invested_value ?? point.investedValue ?? point.totalValue ?? point.total_value ?? 0
  const cashBalance = point.cash_balance ?? point.cashBalance ?? 0
  const totalAssetValue = point.total_asset_value ?? point.totalAssetValue ?? point.totalValue ?? point.total_value ?? 0
  return {
    date: point.date,
    investedValue: Number(investedValue),
    cashBalance: Number(cashBalance),
    totalAssetValue: Number(totalAssetValue),
    totalReturnPct: point.total_return_pct ?? point.totalReturnPct ?? null,
  }
}

export function currentAssetPoint(summary, cashBalance) {
  if (!summary) return null

  const investedValue = Number(summary.invested_value ?? 0)
  const cash = Number(summary.cash_balance ?? cashBalance ?? 0)
  const totalAssetValue = Number(
    summary.total_asset_value ?? summary.total_value ?? investedValue + cash
  )
  if (!Number.isFinite(totalAssetValue) || totalAssetValue <= 0) return null

  return {
    date: formatInputDate(),
    investedValue: Number.isFinite(investedValue) ? investedValue : 0,
    cashBalance: Number.isFinite(cash) ? cash : 0,
    totalAssetValue,
    totalReturnPct: summary.total_return_pct ?? null,
  }
}

export function mergeCurrentAssetPoint(history, currentPoint) {
  if (!currentPoint) return history

  const next = [...history]
  const sameDateIndex = next.findIndex((point) => point.date === currentPoint.date)
  if (sameDateIndex >= 0) {
    next[sameDateIndex] = { ...next[sameDateIndex], ...currentPoint }
  } else {
    next.push(currentPoint)
  }

  return next.sort((a, b) => new Date(a.date) - new Date(b.date))
}

export function fmtScoreDate(dateStr, fetchTime) {
  if (!dateStr) return '—'

  const nowKST = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Seoul' }))
  const pad    = (n) => String(n).padStart(2, '0')
  const todayStr = `${nowKST.getFullYear()}-${pad(nowKST.getMonth() + 1)}-${pad(nowKST.getDate())}`
  const ystKST   = new Date(nowKST)
  ystKST.setDate(ystKST.getDate() - 1)
  const ystStr = `${ystKST.getFullYear()}-${pad(ystKST.getMonth() + 1)}-${pad(ystKST.getDate())}`

  if (dateStr === todayStr) {
    const t = fetchTime ?? new Date()
    return `오늘 ${t.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })}`
  }
  if (dateStr === ystStr) return '어제'

  const d = new Date(dateStr)
  return isNaN(d) ? dateStr : d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

/** HERD 점수 → 단계 색상 (히스토리 통계용) */
export function scoreToColor(score) {
  return score == null ? 'var(--text-1)' : scoreColor(score)
}

/** HERD 점수 → 단계명 (히스토리 통계용) */
export function scoreToStage(score) {
  return stageLabelFromScore(score, true)
}

/** points 배열에서 최근 N일 평균 점수 반환 */
export function averageScoreForLastDays(points, days, fallbackScore = null) {
  if (!points?.length) return null
  const now = new Date()
  const cutoff = new Date(now)
  cutoff.setDate(cutoff.getDate() - days)

  const values = []
  for (const p of points) {
    const pointDate = new Date(`${p.date}T00:00:00`)
    if (Number.isNaN(pointDate.getTime())) continue
    if (pointDate >= cutoff && pointDate <= now && p.score != null) {
      values.push(Number(p.score))
    }
  }

  if (values.length === 0) {
    const latest = points[points.length - 1]
    const score = fallbackScore ?? latest?.score
    return score == null ? null : { score }
  }

  const score = values.reduce((sum, v) => sum + v, 0) / values.length
  return { score }
}


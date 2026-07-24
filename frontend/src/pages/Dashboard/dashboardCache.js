import { API_HOST } from '../../utils/apiConfig'
import { HERD_HISTORY_PERIODS } from '../../utils/historyPeriods'
import {
  CACHE_KEY_REALTIME,
  CACHE_KEY_HERD,
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_TIME,
  clearAllPortfolioCaches,
  clearPortfolioCaches,
  readCache,
  readUserCache,
  userCacheKey,
  writeCache,
  writeUserCache,
} from '../../features/portfolio/portfolioCache'

export { API_HOST }

export {
  CACHE_KEY_REALTIME,
  CACHE_KEY_HERD,
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_TIME,
  clearPortfolioCaches,
  readCache,
  readUserCache,
  userCacheKey,
  writeCache,
  writeUserCache,
}
export const CACHE_KEY_SPY = 'hs_spy_observation_s1'
export const CACHE_KEY_SPY_HISTORY = 'hs_spy_observation_history'
export const CACHE_KEY_SPY_HISTORY_VERSION = 's1-v1'
export const CACHE_KEY_VERSION = 'hs_dashboard_cache_version'
export const CACHE_KEY_PORTFOLIO_SORT = 'hs_dashboard_sort'
export const DASHBOARD_CACHE_VERSION = 's1-market-observation'
export const DASHBOARD_CACHE_TTL_MS = 30 * 60 * 1000

export const HISTORY_PERIODS = HERD_HISTORY_PERIODS

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

export function formatInputDate(value) {
  const date = value ? new Date(value) : new Date()
  if (Number.isNaN(date.getTime())) return ''
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function spyHistoryCacheKey(period) {
  return `${CACHE_KEY_SPY_HISTORY}_${period}_${CACHE_KEY_SPY_HISTORY_VERSION}`
}

export function ensureDashboardCacheVersion() {
  try {
    if (localStorage.getItem(CACHE_KEY_VERSION) === DASHBOARD_CACHE_VERSION) return false

    const cacheKeys = [
      CACHE_KEY_SPY,
    ].concat(HISTORY_PERIODS.map((period) => spyHistoryCacheKey(period.value)))
    clearAllPortfolioCaches()
    cacheKeys.forEach((key) => localStorage.removeItem(key))
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

export function normalizePortfolioSummary(data) {
  if (!data) return null
  const investedValue = data.invested_value ?? data.investedValue ??
    data.total_value ?? data.totalValue ?? null
  const cashBalance = data.cash_balance ?? data.cashBalance ?? 0
  const totalAssetValue = data.total_asset_value ?? data.totalAssetValue ??
    (investedValue == null ? null : Number(investedValue) + Number(cashBalance ?? 0))
  return {
    total_value: totalAssetValue,
    invested_value: investedValue,
    cash_balance: cashBalance,
    total_asset_value: totalAssetValue,
    total_cost: data.total_cost ?? data.totalCost ?? null,
    total_return_pct: data.total_return_pct ?? data.totalReturnPct ?? null,
    daily_change_pct: data.daily_change_pct ?? data.dailyChangePct ?? null,
    market_data_date: data.market_data_date ?? data.marketDataDate ?? null,
    stocks: (data.stocks ?? []).map((stock) => ({
      ticker: stock.ticker,
      avg_price: stock.avg_price ?? stock.avgPrice ?? null,
      quantity: stock.quantity ?? null,
      current_price: stock.current_price ?? stock.currentPrice ?? null,
      price_date: stock.price_date ?? stock.priceDate ?? null,
      market_value: stock.market_value ?? stock.marketValue ?? null,
      return_pct: stock.return_pct ?? stock.returnPct ?? null,
      daily_change_pct: stock.daily_change_pct ?? stock.dailyChangePct ?? null,
    })),
  }
}

export function saveCacheTime(userId, key = CACHE_KEY_TIME) {
  const now = new Date()
  localStorage.setItem(userCacheKey(key, userId), now.toISOString())
  return now
}

export function isDashboardCacheFresh(userId, now = Date.now()) {
  try {
    const savedAt = new Date(
      localStorage.getItem(userCacheKey(CACHE_KEY_HERD_TIME, userId)) || ''
    ).getTime()
    return Number.isFinite(savedAt) && now - savedAt <= DASHBOARD_CACHE_TTL_MS
  } catch {
    return false
  }
}

import { API_HOST } from '../../utils/apiConfig'
import {
  CACHE_KEY_HERD,
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_REALTIME,
  CACHE_KEY_TIME,
  clearAllPortfolioCaches,
  readUserCache,
  userCacheKey,
  writeUserCache,
} from '../../features/portfolio/portfolioCache'

export {
  API_HOST,
  CACHE_KEY_HERD,
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_REALTIME,
  CACHE_KEY_TIME,
  readUserCache,
  userCacheKey,
  writeUserCache,
}

export const CACHE_KEY_VERSION = 'hs_portfolio_cache_version'
export const PORTFOLIO_CACHE_VERSION = 's1-portfolio-v3'
export const PORTFOLIO_CACHE_TTL_MS = 30 * 60 * 1000

export function ensurePortfolioCacheVersion() {
  try {
    if (localStorage.getItem(CACHE_KEY_VERSION) === PORTFOLIO_CACHE_VERSION) {
      return false
    }
    clearAllPortfolioCaches()
    localStorage.removeItem('hs_dashboard_cache_version')
    localStorage.setItem(CACHE_KEY_VERSION, PORTFOLIO_CACHE_VERSION)
    return true
  } catch {
    return false
  }
}

export function normalizePortfolioSummary(data) {
  if (!data) return null
  const investedValue = data.invested_value ?? data.investedValue ??
    data.total_value ?? data.totalValue ?? null
  const cashBalance = data.cash_balance ?? data.cashBalance ?? 0
  const totalAssetValue = data.total_asset_value ?? data.totalAssetValue ??
    (investedValue == null ? null : Number(investedValue) + Number(cashBalance))
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

export function savePortfolioCacheTime(userId, key = CACHE_KEY_TIME) {
  const now = new Date()
  localStorage.setItem(userCacheKey(key, userId), now.toISOString())
  return now
}

export function isPortfolioCacheFresh(userId, now = Date.now()) {
  try {
    const savedAt = new Date(
      localStorage.getItem(userCacheKey(CACHE_KEY_HERD_TIME, userId)) || ''
    ).getTime()
    return Number.isFinite(savedAt) && now - savedAt <= PORTFOLIO_CACHE_TTL_MS
  } catch {
    return false
  }
}

export function portfolioRefreshResultText(priceResult, herdResult) {
  const pricesUpdated = priceResult.status === 'fulfilled'
  const observationsUpdated = herdResult.status === 'fulfilled'
  if (pricesUpdated && observationsUpdated) {
    return '현재가와 State S1 관찰값을 갱신했습니다.'
  }
  if (pricesUpdated) return '현재가는 갱신했지만 State S1 관찰값 조회에 실패했습니다.'
  if (observationsUpdated) return 'State S1 관찰값은 갱신했지만 현재가 조회에 실패했습니다.'
  return '데이터 갱신에 실패했습니다. 잠시 후 다시 시도해주세요.'
}

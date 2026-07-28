import { beforeEach, describe, expect, it } from 'vitest'
import {
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_REALTIME,
  PORTFOLIO_CACHE_TTL_MS,
  isPortfolioCacheFresh,
  normalizePortfolioSummary,
  userCacheKey,
} from './portfolioDataModel'
import { clearPortfolioCaches } from '../../features/portfolio/portfolioCache'

const USER_ID = 'user-1'

beforeEach(() => localStorage.clear())

describe('portfolio cache policy', () => {
  it('expires State S1 observations outside the TTL', () => {
    const now = Date.now()
    localStorage.setItem(
      userCacheKey(CACHE_KEY_HERD_TIME, USER_ID),
      new Date(now - PORTFOLIO_CACHE_TTL_MS - 1).toISOString(),
    )

    expect(isPortfolioCacheFresh(USER_ID, now)).toBe(false)
  })

  it('keeps fresh State S1 observations inside the TTL', () => {
    const now = Date.now()
    localStorage.setItem(
      userCacheKey(CACHE_KEY_HERD_TIME, USER_ID),
      new Date(now - 1_000).toISOString(),
    )

    expect(isPortfolioCacheFresh(USER_ID, now)).toBe(true)
  })

  it('isolates portfolio caches by authenticated user', () => {
    localStorage.setItem(userCacheKey(CACHE_KEY_REALTIME, 'user-1'), '{"owner":1}')
    localStorage.setItem(userCacheKey(CACHE_KEY_REALTIME, 'user-2'), '{"owner":2}')

    clearPortfolioCaches('user-1')

    expect(localStorage.getItem(userCacheKey(CACHE_KEY_REALTIME, 'user-1'))).toBeNull()
    expect(localStorage.getItem(userCacheKey(CACHE_KEY_REALTIME, 'user-2'))).toBe('{"owner":2}')
  })

  it('normalizes mixed backend field names at the data boundary', () => {
    expect(normalizePortfolioSummary({
      investedValue: 100,
      cashBalance: 20,
      expectedStockCount: 2,
      pricedStockCount: 1,
      missingPriceTickers: ['TSLA'],
      valuationStatus: 'PARTIAL',
      stocks: [{
        ticker: 'NVDA',
        currentPrice: 10,
        dailyChangePct: 1.2,
      }],
    })).toMatchObject({
      invested_value: 100,
      cash_balance: 20,
      total_asset_value: 120,
      expected_stock_count: 2,
      priced_stock_count: 1,
      missing_price_tickers: ['TSLA'],
      valuation_status: 'PARTIAL',
      stocks: [{
        ticker: 'NVDA',
        current_price: 10,
        daily_change_pct: 1.2,
      }],
    })
  })
})

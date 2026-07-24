import { expect, test } from '@playwright/test'
import {
  dataStatus,
  financials,
  history,
  journal,
  nvda,
  nvdaObservation,
  observationHistory,
  portfolio,
  portfolioHerd,
  portfolioSummary,
  reliability,
  spy,
  spyObservation,
  user,
  watchlist,
} from './visualFixtures'

const json = (data) => ({ success: true, data, message: null })

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-07-24T01:00:00Z'))
  await page.addInitScript(() => {
    let seed = 20260724
    Math.random = () => {
      seed = (seed * 1664525 + 1013904223) >>> 0
      return seed / 4294967296
    }
    localStorage.clear()
    localStorage.setItem('herdsignal_theme', 'dark')
    window.requestAnimationFrame = () => 0
    window.cancelAnimationFrame = () => {}
  })

  await page.route('https://api.frankfurter.dev/**', (route) => (
    route.fulfill({ json: { rates: { KRW: 1378.4 } } })
  ))
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (!url.pathname.startsWith('/api/')) {
      await route.continue()
      return
    }
    const payload = responseFor(url.pathname)
    await route.fulfill({
      status: payload === undefined ? 404 : 200,
      contentType: 'application/json',
      body: JSON.stringify(payload === undefined ? json(null) : json(payload)),
    })
  })
})

for (const scenario of [
  { name: 'dashboard', path: '/app', ready: '내 포트폴리오' },
  { name: 'stock-detail', path: '/stock/NVDA', ready: 'NVDA' },
  { name: 'watchlist', path: '/watchlist', ready: '매수 대기열' },
]) {
  test(`${scenario.name} visual regression`, async ({ page }, testInfo) => {
    await page.goto(scenario.path)
    await expect(page.getByText(scenario.ready, { exact: true }).first()).toBeVisible({
      timeout: 15_000,
    })
    await expect(page).toHaveScreenshot(
      `${scenario.name}-${testInfo.project.name}.png`,
      { timeout: 15_000 }
    )
  })
}

function responseFor(pathname) {
  if (pathname === '/api/auth/csrf') return { token: 'visual-token' }
  if (pathname === '/api/auth/me') return user
  if (pathname === '/api/system/data-status') return dataStatus
  if (pathname === '/api/portfolio') return portfolio
  if (pathname === '/api/portfolio/summary') return portfolioSummary
  if (pathname === '/api/portfolio/cash') return { cashAmount: portfolioSummary.cash_balance }
  if (pathname === '/api/portfolio/herd') {
    return { stocks: portfolioHerd, averageScore: 54, totalCount: portfolioHerd.length }
  }
  if (pathname === '/api/watchlist/herd') {
    return { stocks: watchlist, averageScore: 49.5, totalCount: watchlist.length }
  }
  if (pathname === '/api/journal') return journal
  if (pathname === '/api/observations/SPY') return spyObservation
  if (pathname === '/api/observations/SPY/history') {
    return {
      availabilityStatus: 'AVAILABLE',
      ticker: 'SPY',
      stateModelVersion: 'HERD_STATE_S1',
      points: observationHistory,
    }
  }
  if (pathname === '/api/observations/NVDA') return nvdaObservation
  if (pathname === '/api/observations/NVDA/history') {
    return {
      availabilityStatus: 'AVAILABLE',
      ticker: 'NVDA',
      stateModelVersion: 'HERD_STATE_S1',
      points: observationHistory,
    }
  }
  if (pathname === '/api/stocks/SPY/herd') return spy
  if (pathname === '/api/stocks/SPY/herd/history') return { points: history }
  if (pathname === '/api/stocks/NVDA/herd') return nvda
  if (pathname === '/api/stocks/NVDA/herd/history') return { points: history }
  if (pathname === '/api/stocks/NVDA/herd/reliability') return reliability
  if (pathname === '/api/stocks/NVDA/financials') return financials
  return undefined
}

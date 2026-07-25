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
  portfolioHistory,
  trackedObservations,
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

const visualScenarios = [
  { name: 'market-home', path: '/app', ready: 'SPY' },
  { name: 'portfolio', path: '/portfolio', ready: '내 포트폴리오' },
  { name: 'stock-detail', path: '/stock/NVDA', ready: 'NVDA' },
  { name: 'watchlist', path: '/watchlist', ready: '관심종목' },
  {
    name: 'search',
    path: '/search',
    ready: 'NVDA 종목 상세 열기',
    prepare: async (page) => {
      await page.getByRole('textbox', { name: '티커 또는 종목명 검색' }).fill('NVDA')
    },
  },
]

for (const scenario of visualScenarios) {
  test(`${scenario.name} visual regression`, async ({ page }, testInfo) => {
    await page.goto(scenario.path)
    await scenario.prepare?.(page)
    const readyTarget = scenario.name === 'search'
      ? page.getByRole('button', { name: scenario.ready })
      : page.getByText(scenario.ready, { exact: true }).first()
    await expect(readyTarget).toBeVisible({ timeout: 15_000 })
    expect(await page.evaluate(() => (
      document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    ))).toBe(false)
    await expect(page).toHaveScreenshot(
      `${scenario.name}-${testInfo.project.name}.png`,
      { timeout: 15_000 }
    )
  })
}

test('protected shell and search remain keyboard operable', async ({ page }) => {
  await page.goto('/search')
  await expect(page.getByRole('heading', { name: '종목 찾기' })).toBeVisible()
  await expect(page.locator('#main-content')).toBeFocused()
  await expect(page.getByRole('link', { name: '본문으로 건너뛰기' })).toHaveAttribute(
    'href',
    '#main-content',
  )

  const accountTrigger = page.getByRole('button', { name: '계정 메뉴 열기' })
  await accountTrigger.click()
  await expect(page.getByRole('complementary', { name: '계정 메뉴' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(accountTrigger).toBeFocused()

  await page.getByRole('textbox', { name: '티커 또는 종목명 검색' }).fill('NVDA')
  const openStock = page.getByRole('button', { name: 'NVDA 종목 상세 열기' })
  await expect(openStock).toBeVisible()
  await openStock.focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/stock\/NVDA$/)
  await expect(page.locator('#main-content')).toBeFocused()
})

function responseFor(pathname) {
  if (pathname === '/api/auth/csrf') return { token: 'visual-token' }
  if (pathname === '/api/auth/me') return user
  if (pathname === '/api/system/data-status') return dataStatus
  if (pathname === '/api/portfolio') return portfolio
  if (pathname === '/api/portfolio/summary') return portfolioSummary
  if (pathname === '/api/portfolio/history') return { points: portfolioHistory }
  if (pathname === '/api/portfolio/cash') return { cashAmount: portfolioSummary.cash_balance }
  if (pathname === '/api/observations') {
    return {
      requestedCount: trackedObservations.length,
      availableCount: trackedObservations.length,
      observations: trackedObservations,
    }
  }
  if (pathname === '/api/portfolio/herd') {
    return { stocks: portfolioHerd, averageScore: 54, totalCount: portfolioHerd.length }
  }
  if (pathname === '/api/watchlist/herd') {
    return { stocks: watchlist, averageScore: 49.5, totalCount: watchlist.length }
  }
  if (pathname === '/api/watchlist') {
    return watchlist.map(({ ticker }) => ({ ticker, memo: null }))
  }
  if (pathname === '/api/journal') return journal
  if (pathname === '/api/stocks/search') {
    return {
      results: [
        { ticker: 'NVDA', name: 'NVIDIA Corporation', type: 'Semiconductors' },
      ],
    }
  }
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

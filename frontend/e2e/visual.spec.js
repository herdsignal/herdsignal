import { expect, test } from '@playwright/test'
import {
  dataStatus,
  financials,
  history,
  journal,
  nvda,
  nvdaObservation,
  observationHistory,
  observationTimeline,
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
  { name: 'login', path: '/login', ready: '내 포트폴리오 보기' },
  { name: 'dashboard', path: '/app', ready: 'SPY' },
  { name: 'stock-detail', path: '/stock/NVDA', ready: 'NVDA' },
  { name: 'watchlist', path: '/watchlist', ready: '관심종목' },
  { name: 'history', path: '/history', ready: '자산 히스토리' },
  { name: 'herd-lab', path: '/herd-lab', ready: 'HERD 연구실' },
  { name: 'journal', path: '/journal', ready: '판단 기록' },
  { name: 'settings', path: '/settings', ready: '투자 프로필' },
]

for (const scenario of visualScenarios) {
  test(`${scenario.name} visual regression`, async ({ page }, testInfo) => {
    await page.goto(scenario.path)
    await scenario.prepare?.(page)
    const readyTarget = page.getByText(scenario.ready, { exact: true }).first()
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

test('root opens the dashboard without a separate public home', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/app$/)
  await expect(page.getByRole('searchbox', { name: '티커 또는 종목명 검색' })).toBeVisible()
})

test('protected shell and search remain keyboard operable', async ({ page }) => {
  await page.goto('/app')
  await expect(page.getByRole('navigation', { name: '주요 메뉴' })).toContainText('관찰')
  await expect(page.getByRole('button', { name: '내 자산 보기' })).toBeVisible()
  await expect(page.getByRole('searchbox', { name: '티커 또는 종목명 검색' })).toBeVisible()
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

  const searchbox = page.getByRole('searchbox', { name: '티커 또는 종목명 검색' })
  await searchbox.fill('NVDA')
  await expect(page.getByRole('button', { name: 'HERD 보기' })).toBeEnabled()
  await searchbox.focus()
  await page.keyboard.press('Enter')
  const openStock = page.getByRole('link', { name: '종목 상세 보기' })
  await expect(openStock).toHaveAttribute('href', '/stock/NVDA')
  await openStock.focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/stock\/NVDA$/)
  await expect(page.locator('#main-content')).toBeFocused()
})

test('market field moves and portfolio holdings open stock details', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'no-preference' })
  await page.goto('/app')

  const firstDot = page.locator('section[role="img"] i').first()
  await expect(firstDot).toBeVisible()
  await expect(firstDot).not.toHaveCSS('animation-name', 'none')
  const firstTransform = await firstDot.evaluate((element) => (
    getComputedStyle(element).transform
  ))
  await page.waitForTimeout(350)
  const nextTransform = await firstDot.evaluate((element) => (
    getComputedStyle(element).transform
  ))
  expect(nextTransform).not.toBe(firstTransform)

  await page.getByRole('button', { name: 'NVDA 종목 상세 열기' }).click()
  await expect(page).toHaveURL(/\/stock\/NVDA$/)
  await expect(page.getByRole('heading', { name: '현재 군중 상태' })).toBeVisible({
    timeout: 15_000,
  })
  await expect(page.getByRole('heading', { name: 'HERD 구성' })).toBeVisible()
  await expect(page.getByText('가격 확장', { exact: true })).toBeVisible()
  await expect(page.getByText('하방 위험 맥락', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '기업 정보 · 판단 로그' })).toBeVisible()
  await expect(page.locator('details')).toHaveCount(0)
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
  if (pathname === '/api/investor-profile') {
    return {
      strategy: 'TARGET_REBALANCE',
      riskTolerance: 'BALANCED',
      timeHorizonYears: 10,
      liquidityBufferMonths: 6,
      maxActionRatio: 0.05,
      targetEquityRatio: 0.8,
    }
  }
  if (pathname === '/api/model/shadow-status') {
    return {
      shadowStatus: 'SHADOW_ACTIVE',
      candidateId: 'HERD_STATE_S1',
    }
  }
  if (pathname === '/api/model/validation') {
    return {
      modelVersion: 'HERD_v6.1',
      generatedAt: '2026-07-24T00:52:00Z',
      validationRun: {
        completedTickers: 55,
        requestedTickers: 55,
        coverage: 1,
        embargoDays: 20,
      },
      walkForward: {
        samples: 440,
        improvementRate: 36.4,
        mddImprovementMedian: 0.9,
      },
      parameterStability: {
        sameParameterRate: 59.4,
        singleParameterSpike: true,
        recommendation: 'USE_FIXED_PARAMETERS',
      },
      overfitting: {
        parametersTested: 9,
        deflatedSharpeStatus: 'FAIL',
      },
      adoptionGate: {
        policyVersion: '2026.07-v1',
        status: 'RESEARCH_VALIDATION',
        eligibleForHumanReview: false,
        failedCriteria: ['deflated_sharpe', 'survivorship_bias'],
      },
      scoreParityPassed: true,
      survivorshipStatus: 'SURVIVORSHIP_BIAS_REMAINS',
      actionOutcomes: [
        {
          horizon: '3m',
          samples: 126,
          hitRate: 58.7,
          counterfactualDeltaMean: 1.8,
          drawdownMean: -6.4,
        },
      ],
      tickers: [
        { ticker: 'NVDA', buyHoldReturn: 180, actionReturn: 142, capture: 78.9, mddImprovement: 4.8, actions: 11 },
        { ticker: 'JPM', buyHoldReturn: 65, actionReturn: 57, capture: 87.7, mddImprovement: 3.1, actions: 8 },
        { ticker: 'LLY', buyHoldReturn: 210, actionReturn: 160, capture: 76.2, mddImprovement: 2.6, actions: 10 },
        { ticker: 'AMZN', buyHoldReturn: 92, actionReturn: 71, capture: 77.2, mddImprovement: 1.7, actions: 9 },
        { ticker: 'GE', buyHoldReturn: 88, actionReturn: 70, capture: 79.5, mddImprovement: 2.2, actions: 8 },
        { ticker: 'XOM', buyHoldReturn: 41, actionReturn: 30, capture: 73.2, mddImprovement: -0.4, actions: 7 },
      ],
    }
  }
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
  if (pathname === '/api/observations/NVDA/timeline') {
    return {
      availabilityStatus: 'AVAILABLE',
      ticker: 'NVDA',
      stateModelVersion: 'HERD_STATE_S1',
      priceField: 'ADJUSTED_CLOSE',
      observationCount: observationTimeline.length,
      pricedObservationCount: observationTimeline.length,
      points: observationTimeline,
    }
  }
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

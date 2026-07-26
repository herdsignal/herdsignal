import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Portfolio from './Portfolio'
import { usePortfolioPageData } from './usePortfolioPageData'

vi.mock('./usePortfolioPageData', () => ({
  usePortfolioPageData: vi.fn(),
}))

function pageData() {
  return {
    portfolio: [{
      ticker: 'NVDA',
      avgPrice: 100,
      quantity: 2,
      targetWeight: 0.6,
    }],
    summary: {
      total_value: 500,
      total_asset_value: 500,
      invested_value: 400,
    },
    loading: false,
    error: null,
    refreshing: false,
    refreshNotice: null,
    lastUpdated: new Date('2026-07-25T10:00:00'),
    currencyMode: 'USD',
    exchangeRate: 1380,
    selectCurrency: vi.fn(),
    cashBalance: 100,
    cashDraft: '100',
    setCashDraft: vi.fn(),
    cashSaving: false,
    assetHistoryPeriod: 'year',
    setAssetHistoryPeriod: vi.fn(),
    assetHistoryLoading: false,
    assetHistoryError: null,
    assetChartHistory: [
      { date: '2026-01-01', totalAssetValue: 400 },
      { date: '2026-07-25', totalAssetValue: 500 },
    ],
    assetPeriodLabel: '1년',
    accountValueChangePct: 25,
    sortedRows: [{
      ticker: 'NVDA',
      companyName: 'NVIDIA',
      marketValue: 400,
      currentPrice: 200,
      returnPct: 100,
      dailyChangePct: -2,
      weightPct: 80,
      targetWeightPct: 60,
      targetGapPct: 20,
      avgPrice: 100,
      quantity: 2,
      cost: 200,
      pnl: 200,
      herdScore: 78,
      herdStage: 'Herd Rush',
      herdPreviousScore: 69,
      observationDate: '2026-07-24',
    }],
    sortBy: 'weight',
    selectSort: vi.fn(),
    todayChange: { amount: -8, pct: -1.6 },
    exposure: {
      topHolding: { ticker: 'NVDA', weightPct: 80 },
      topThreeWeightPct: 80,
      largestSector: { name: 'Technology', weightPct: 80 },
      cashWeightPct: 20,
      sectors: [{ name: 'Technology', weightPct: 80 }],
    },
    displayAmount: (value) => value == null ? '—' : `$${Number(value).toFixed(2)}`,
    displaySignedAmount: (value) => value == null
      ? '—'
      : `${Number(value) >= 0 ? '+' : '-'}$${Math.abs(Number(value)).toFixed(2)}`,
    refresh: vi.fn(),
    fetchData: vi.fn(),
    handleCashSave: vi.fn(),
    handleDelete: vi.fn(),
    handleTargetWeightSave: vi.fn(),
    deletingTicker: null,
    targetSavingTicker: null,
    modalTicker: null,
    setModalTicker: vi.fn(),
    modalStock: null,
    handleModalSaved: vi.fn(),
  }
}

describe('Portfolio Lens', () => {
  afterEach(cleanup)

  beforeEach(() => {
    usePortfolioPageData.mockReturnValue(pageData())
  })

  it('keeps account essentials visible without operational action copy', () => {
    render(<MemoryRouter><Portfolio /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: '내 포트폴리오' })).toBeInTheDocument()
    expect(screen.getByText('전체 자산')).toBeInTheDocument()
    expect(screen.getByText('주식 평가액')).toBeInTheDocument()
    expect(screen.getAllByText('현금').length).toBeGreaterThan(0)
    expect(screen.getByText('계좌 가치 변화')).toBeInTheDocument()
    expect(screen.getByText('투자 수익률 아님')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '비중·노출' })).toBeInTheDocument()
    expect(screen.getByText('ETF 내부 섹터 구성 미반영', { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '상세 보기' })).toHaveAttribute('href', '/history')
    expect(screen.getByRole('img', { name: /HERD 78/ })).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/매수|매도|익절|추천/)
  })

  it('opens the stock detail from a holding row', () => {
    render(
      <MemoryRouter initialEntries={['/portfolio']}>
        <Routes>
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/stock/:ticker" element={<div>NVDA 상세 화면</div>} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'NVDA 종목 상세 열기' }))
    expect(screen.getByText('NVDA 상세 화면')).toBeInTheDocument()
  })

  it('keeps holding management separate from stock navigation', () => {
    render(<MemoryRouter><Portfolio /></MemoryRouter>)

    fireEvent.click(screen.getByRole('button', { name: 'NVDA 보유 정보 관리' }))
    expect(screen.getByText('평균 매수가')).toBeInTheDocument()
    expect(screen.getByText('+20.0%p')).toBeInTheDocument()
    expect(screen.getByLabelText('목표 비중 (%)')).toHaveValue(60)
    expect(screen.getByRole('button', { name: '종목 분석' })).toBeInTheDocument()
  })
})

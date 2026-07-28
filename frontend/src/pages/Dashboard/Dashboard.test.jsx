import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'

const addWatchlist = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { authenticated: true, id: 1 } }),
}))

vi.mock('../MarketHome/useMarketHomeData', () => ({
  useMarketHomeData: () => ({
    observation: {
      scope: 'MARKET_AGGREGATE',
      stateScore: 51,
      stage: 'CALM',
      delta4w: -3.8,
      observationDate: '2026-07-24',
      availabilityStatus: 'AVAILABLE',
    },
    loading: false,
    observationError: false,
  }),
}))

vi.mock('../Search/useStockSearch', () => ({
  useStockSearch: (query) => ({
    recentSearches: ['TSLA', 'IONQ', 'PLTR'],
    searchResult: query.length >= 2
      ? {
          status: 'found',
          data: {
            ticker: 'NVDA',
            herdScore: 24,
            herdStage: 'Scatter',
            delta4w: -7,
            scoreDate: '2026-07-24',
          },
          matches: [{ ticker: 'NVDA', name: 'NVIDIA', sector: 'Semiconductors' }],
        }
      : null,
  }),
}))

vi.mock('../Search/useTickerMembership', () => ({
  useTickerMembership: () => ({
    watchlistStatus: 'idle',
    addError: '',
    handleAddWatchlist: addWatchlist,
  }),
}))

vi.mock('../Portfolio/usePortfolioPageData', () => ({
  usePortfolioPageData: () => ({
    portfolio: [],
    summary: { total_asset_value: 1000, invested_value: 800 },
    cashBalance: 200,
    loading: false,
    error: null,
    currencyMode: 'KRW',
    selectCurrency: vi.fn(),
    privacyMode: true,
    togglePrivacyMode: vi.fn(),
    displayAmount: () => '••••••',
    assetChartHistory: [],
    assetHistoryPeriod: 'year',
    assetPeriodLabel: '1년',
    accountValueChangePct: null,
    assetHistoryLoading: false,
    assetHistoryError: null,
    setAssetHistoryPeriod: vi.fn(),
    setAssetPanelOpen: vi.fn(),
    sortedRows: [],
    sortBy: 'weight',
    deletingTicker: null,
    displaySignedAmount: vi.fn(),
    selectSort: vi.fn(),
    setModalTicker: vi.fn(),
    handleDelete: vi.fn(),
    handleTargetWeightSave: vi.fn(),
    targetSavingTicker: null,
    modalTicker: null,
    fetchData: vi.fn(),
  }),
}))

vi.mock('../Portfolio/PortfolioHistory', () => ({
  default: () => <div>자산 그래프</div>,
}))

vi.mock('../Portfolio/PortfolioHoldings', () => ({
  default: () => <div>보유 종목 표</div>,
}))

describe('Dashboard', () => {
  beforeEach(() => addWatchlist.mockClear())
  afterEach(cleanup)

  it('SPY를 기본으로 보여주고 자산은 요청할 때만 연다', () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>)

    const search = screen.getByRole('searchbox', { name: '티커 또는 종목명 검색' })
    const observation = screen.getByRole('heading', { name: 'SPY' })
    const portfolio = screen.getByRole('heading', { name: '보유 현황' })

    expect(search.compareDocumentPosition(observation)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
    expect(observation.compareDocumentPosition(portfolio)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
    expect(screen.queryByText('전체 자산')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'TSLA' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '내 자산 보기' }))

    expect(screen.getByText('전체 자산')).toBeInTheDocument()
    expect(screen.getByText('자산 그래프')).toBeInTheDocument()
  })

  it('검색한 종목을 선택해야 HERD 패널을 교체한다', () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>)

    fireEvent.change(screen.getByRole('searchbox', { name: '티커 또는 종목명 검색' }), {
      target: { value: 'NVDA' },
    })
    expect(screen.getByRole('heading', { name: 'SPY' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'HERD 보기' }))

    expect(screen.getByRole('heading', { name: 'NVDA' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '종목 상세 보기' })).toHaveAttribute(
      'href',
      '/stock/NVDA',
    )
  })
})

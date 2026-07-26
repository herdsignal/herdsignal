import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ROUTER_FUTURE } from '../../routerConfig'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StockDetail from './StockDetail'
import * as api from '../../api/herdApi'

vi.mock('../../api/herdApi', () => ({
  getHerdObservation: vi.fn(),
  getHerdObservationHistory: vi.fn(),
  addToPortfolio: vi.fn(),
  addToWatchlist: vi.fn(),
  getPortfolio: vi.fn(),
  getWatchlist: vi.fn(),
  getStockFinancials: vi.fn(),
  getSignalJournal: vi.fn(),
  createSignalJournal: vi.fn(),
  deleteSignalJournal: vi.fn(),
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { authenticated: true, id: 'user-1' } }),
}))

const response = (data) => Promise.resolve({ data: { data } })

beforeEach(() => {
  api.getPortfolio.mockReturnValue(response([]))
  api.getWatchlist.mockReturnValue(response([]))
  api.getHerdObservation.mockReturnValue(response({
    ticker: 'NVDA',
    companyName: 'NVIDIA Corp',
    availabilityStatus: 'AVAILABLE',
    freshnessStatus: 'FRESH',
    stateScore: 63,
    delta4w: 6,
    stage: 'DRIFT',
    observationDate: '2026-07-24',
    lastObservedSession: '2026-07-24',
    transition: 'NEUTRAL',
    families: {
      priceExtension: 70,
      trendPosition: 65,
      relativePosition: 60,
      participation: 57,
    },
    downsideRiskContext: 35,
  }))
  api.getSignalJournal.mockReturnValue(response([]))
  api.getHerdObservationHistory.mockReturnValue(response({ points: [
    {
      observationDate: '2026-07-03',
      stateScore: 55,
      stage: 'CALM',
      transition: 'NEUTRAL',
      transitionEvent: false,
    },
    {
      observationDate: '2026-07-10',
      stateScore: 60,
      stage: 'DRIFT',
      transition: 'RECOVERING',
      transitionEvent: true,
    },
    {
      observationDate: '2026-07-17',
      stateScore: 61,
      stage: 'DRIFT',
      transition: 'NEUTRAL',
      transitionEvent: false,
    },
    {
      observationDate: '2026-07-24',
      stateScore: 63,
      stage: 'DRIFT',
      transition: 'NEUTRAL',
      transitionEvent: false,
    },
  ] }))
  api.getStockFinancials.mockReturnValue(response({
    marketCap: 5_000_000_000_000, trailingPe: 32, eps: 6.5,
    operatingMargin: 65, totalRevenue: 250_000_000_000,
  }))
})

describe('StockDetail route', () => {
  it('renders the stock page after loading', async () => {
    render(
      <MemoryRouter initialEntries={['/stock/NVDA']} future={ROUTER_FUTURE}>
        <Routes>
          <Route path="/stock/:ticker" element={<StockDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('NVIDIA Corp')).toBeInTheDocument()
    expect(screen.getByText('HERD State S1')).toBeInTheDocument()
    expect(screen.getByText('현재 군중 상태')).toBeInTheDocument()
    expect(await screen.findByText('57 → 63')).toBeInTheDocument()
    expect(screen.getByText('Drift · 3주째')).toBeInTheDocument()
    expect(screen.getByText('군중 회복')).toBeInTheDocument()
    expect(screen.getByText('HERD 구성')).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/익절 근거|매수 근거|추천/)
  })
})

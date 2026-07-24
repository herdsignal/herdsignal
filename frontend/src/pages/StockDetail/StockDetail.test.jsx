import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ROUTER_FUTURE } from '../../routerConfig'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StockDetail from './StockDetail'
import * as api from '../../api/herdApi'

vi.mock('../../api/herdApi', () => ({
  getStockHerd: vi.fn(),
  getHerdObservation: vi.fn(),
  getHerdObservationHistory: vi.fn(),
  addToPortfolio: vi.fn(),
  addToWatchlist: vi.fn(),
  getStockFinancials: vi.fn(),
  getStockHerdReliability: vi.fn(),
  getPortfolio: vi.fn(),
  getPortfolioSummary: vi.fn(),
  getSignalJournal: vi.fn(),
  createSignalJournal: vi.fn(),
  deleteSignalJournal: vi.fn(),
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { authenticated: true, id: 'user-1' } }),
}))

const response = (data) => Promise.resolve({ data: { data } })

beforeEach(() => {
  api.getStockHerd.mockReturnValue(response({
    ticker: 'NVDA', companyName: 'NVIDIA Corp', herdScore: 19, herdV4: 19,
    herdStage: 'Herd Scatter', signal: 'ADD', scoreDate: '2026-07-10',
    qualityLevel: 'HIGH', actionGrade: 'WATCH', actionLabel: '관찰 우선',
  }))
  api.getHerdObservation.mockReturnValue(response({
    ticker: 'NVDA',
    availabilityStatus: 'AVAILABLE',
    freshnessStatus: 'FRESH',
    stateScore: 63,
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
  api.getPortfolio.mockReturnValue(response([]))
  api.getPortfolioSummary.mockReturnValue(response(null))
  api.getSignalJournal.mockReturnValue(response([]))
  api.getHerdObservationHistory.mockReturnValue(response({ points: [] }))
  api.getStockHerdReliability.mockReturnValue(response({
    fitScore: 70, reliabilityGrade: 'GOOD', reliabilityLabel: '신뢰 가능',
    fleeHitRate: 60, rushHitRate: 55, buySignalEdge: 4, sellSignalEdge: 3,
    sampleQuality: 'GOOD', totalSignalSamples: 12, annualActions: 5,
  }))
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
  })
})

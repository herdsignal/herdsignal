import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import MarketHome from './MarketHome'

vi.mock('./useMarketHomeData', () => ({
  useMarketHomeData: () => ({
    observation: {
      availabilityStatus: 'AVAILABLE',
      freshnessStatus: 'FRESH',
      scope: 'MARKET_AGGREGATE',
      stateScore: 64,
      delta4w: -4.2,
      lastObservedSession: '2026-07-23',
    },
    loading: false,
    observationError: false,
  }),
}))

describe('MarketHome', () => {
  it('identifies the aggregate scope and exposes no action recommendation', () => {
    render(<MarketHome />)

    expect(screen.getByRole('heading', { name: 'SPY' })).toBeInTheDocument()
    expect(screen.getByText('MARKET AGGREGATE')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /HERD 64, Drift/ })).toBeInTheDocument()
    expect(screen.getByText(/4W -4.2/)).toBeInTheDocument()
    expect(screen.getByRole('img')).toHaveAttribute('data-motion', 'releasing')
    expect(screen.queryByText(/BUY|SELL|매수|익절/)).not.toBeInTheDocument()
  })
})

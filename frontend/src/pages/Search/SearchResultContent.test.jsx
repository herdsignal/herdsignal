import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SearchResultContent from './SearchResultContent'

afterEach(cleanup)

const readyResult = {
  status: 'ready',
  data: {
    ticker: 'NVDA',
    companyName: 'NVIDIA',
    herdScore: 78,
    herdStage: 'Rush',
    delta4w: null,
    scoreDate: '2026-07-23',
    freshnessStatus: 'FRESH',
  },
  matches: [
    { ticker: 'NVDA', name: 'NVIDIA Corporation', sector: 'Semiconductors' },
  ],
}

describe('SearchResultContent', () => {
  it('offers explicit keyboard actions without inferring an investment decision', () => {
    const onOpen = vi.fn()
    const onAddPortfolio = vi.fn()
    const onAddWatchlist = vi.fn()

    render(
      <SearchResultContent
        result={readyResult}
        portfolioStatus="idle"
        watchlistStatus="idle"
        addError=""
        onOpen={onOpen}
        onAddPortfolio={onAddPortfolio}
        onAddWatchlist={onAddWatchlist}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'NVDA 종목 상세 열기' }))
    fireEvent.click(screen.getByRole('button', { name: '+ 포트폴리오' }))
    fireEvent.click(screen.getByRole('button', { name: '+ 관심종목' }))

    expect(onOpen).toHaveBeenCalledWith('NVDA')
    expect(onAddPortfolio).toHaveBeenCalledWith('NVDA')
    expect(onAddWatchlist).toHaveBeenCalledWith('NVDA')
    expect(screen.getByText('4주 —')).toBeInTheDocument()
    expect(screen.queryByText(/편입|매수|매도/)).not.toBeInTheDocument()
  })

  it('allows portfolio and watchlist tracking before a HERD observation exists', () => {
    const onOpen = vi.fn()
    const onAddPortfolio = vi.fn()
    const onAddWatchlist = vi.fn()
    render(
      <SearchResultContent
        result={{
          status: 'symbol_found',
          candidate: { ticker: 'TEST', name: 'Test Corp', sector: 'Technology' },
        }}
        portfolioStatus="idle"
        watchlistStatus="idle"
        addError=""
        onOpen={onOpen}
        onAddPortfolio={onAddPortfolio}
        onAddWatchlist={onAddWatchlist}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'TEST 종목 상세 열기' }))
    fireEvent.click(screen.getByRole('button', { name: '+ 포트폴리오' }))
    fireEvent.click(screen.getByRole('button', { name: '+ 관심종목' }))

    expect(onOpen).toHaveBeenCalledWith('TEST')
    expect(onAddPortfolio).toHaveBeenCalledWith('TEST')
    expect(onAddWatchlist).toHaveBeenCalledWith('TEST')
    expect(screen.getByText('State S1 관찰 준비 중')).toBeInTheDocument()
  })
})

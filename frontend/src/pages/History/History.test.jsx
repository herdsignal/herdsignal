import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import History from './History'
import { usePortfolioHistory } from './usePortfolioHistory'

vi.mock('./HistoryChart', () => ({
  default: () => <div data-testid="history-chart" />,
}))
vi.mock('./PerformanceChart', () => ({
  default: () => <div data-testid="performance-chart" />,
}))

vi.mock('./usePortfolioHistory', () => ({
  usePortfolioHistory: vi.fn(),
}))

afterEach(cleanup)

describe('History', () => {
  it('separates account-value changes from holding cost-basis results', () => {
    usePortfolioHistory.mockReturnValue({
      points: [
        { date: '2026-01-01', totalValue: 100, totalReturnPct: 4 },
        { date: '2026-07-25', totalValue: 120, totalReturnPct: 5 },
      ],
      summary: {
        totalAssetValue: 130,
        totalValue: 120,
        totalReturnPct: 5,
        dailyChangePct: -1,
      },
      performance: {
        status: 'PERFORMANCE_READY',
        portfolioReturnPct: 12,
        benchmarkReturnPct: 10,
        excessReturnPct: 2,
        points: [{ date: '2026-01-01', portfolioIndex: 100, benchmarkIndex: 100 }],
      },
      loading: false,
      error: null,
      fetchData: vi.fn(),
    })

    render(<History />)

    expect(screen.getByText('현재 계좌 가치')).toBeInTheDocument()
    expect(screen.getByText('$130.00')).toBeInTheDocument()
    expect(screen.getAllByText('보유 주식 평가손익').length).toBeGreaterThan(0)
    expect(screen.getByText(/입출금을 제거한 별도 계산/)).toBeInTheDocument()
    expect(screen.getByText('투자 성과 · 일별 TWR')).toBeInTheDocument()
    expect(screen.getByTestId('performance-chart')).toBeInTheDocument()
    expect(screen.getByText('계좌 가치 고점 대비')).toBeInTheDocument()
    expect(screen.queryByText('총 수익률')).not.toBeInTheDocument()
  })
})

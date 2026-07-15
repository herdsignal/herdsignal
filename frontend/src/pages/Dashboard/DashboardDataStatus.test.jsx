import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import DashboardDataStatus from './DashboardDataStatus'

describe('DashboardDataStatus', () => {
  it('shows partial scheduler failures with data dates', () => {
    render(<DashboardDataStatus status={{
      status: 'WARNING',
      latestPriceDate: '2026-07-14',
      latestScoreDate: '2026-07-14',
      latestRun: {
        status: 'PARTIAL_FAILURE',
        startedAt: '2026-07-15T03:00:00',
        finishedAt: '2026-07-15T03:10:00',
        totalCount: 12,
        successCount: 11,
        failedCount: 1,
        failedTickers: ['SNDK'],
      },
    }} />)

    expect(screen.getByText('확인 필요')).toBeInTheDocument()
    expect(screen.getByText(/가격 7\/14 · HERD 7\/14/)).toBeInTheDocument()
    expect(screen.getByText(/11\/12 성공 · 실패 1개 \(SNDK\)/)).toBeInTheDocument()
  })

  it('shows an explicit unknown state when the API fails', () => {
    render(<DashboardDataStatus failed />)
    expect(screen.getByText('상태 확인 불가')).toBeInTheDocument()
  })
})

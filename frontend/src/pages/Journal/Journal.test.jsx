import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getSignalJournal } from '../../api/herdApi'
import Journal from './Journal'

vi.mock('../../api/herdApi', () => ({
  getSignalJournal: vi.fn(),
}))

describe('Journal', () => {
  afterEach(cleanup)

  it('shows fixed horizon price paths without action-direction success labels', async () => {
    getSignalJournal.mockResolvedValue({
      data: {
        data: [{
          id: 1,
          ticker: 'NVDA',
          actionType: 'SELL',
          actionLabel: '내 판단',
          referencePrice: 100,
          referencePriceDate: '2025-01-02',
          horizonOutcomes: [
            { horizon: '1M', status: 'AVAILABLE', returnPct: -10 },
            { horizon: '3M', status: 'PENDING' },
            { horizon: '6M', status: 'UNAVAILABLE' },
          ],
          recordedAt: '2025-01-02T12:00:00',
        }],
      },
    })

    render(<MemoryRouter><Journal /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())
    expect(screen.getByText('-10.0%')).toBeInTheDocument()
    expect(screen.getByText('대기')).toBeInTheDocument()
    expect(screen.getByText('자료 없음')).toBeInTheDocument()
    expect(screen.getByText('기준 $100 · 2025. 1. 2.')).toBeInTheDocument()
    expect(screen.getByText('결과 확인 가능')).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/익절 후 방어|현재 결과/)

    fireEvent.click(screen.getByRole('button', { name: '대기 중' }))
    expect(screen.getByText('조건에 맞는 기록이 없습니다.')).toBeInTheDocument()
  })
})

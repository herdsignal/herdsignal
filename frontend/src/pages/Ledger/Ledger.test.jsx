import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getPortfolioLedger,
  getPortfolioLedgerSummary,
  getPortfolioSourceReconciliation,
  importPortfolioOpeningSnapshot,
} from '../../api/herdApi'
import Ledger from './Ledger'

vi.mock('../../api/herdApi', () => ({
  createPortfolioLedgerEntry: vi.fn(),
  deletePortfolioLedgerEntry: vi.fn(),
  exportPortfolioLedgerCsv: vi.fn(),
  getPortfolioLedger: vi.fn(),
  getPortfolioLedgerSummary: vi.fn(),
  getPortfolioSourceReconciliation: vi.fn(),
  importPortfolioOpeningSnapshot: vi.fn(),
}))

describe('Ledger', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getPortfolioLedger.mockResolvedValue({ data: { data: [] } })
    getPortfolioLedgerSummary.mockResolvedValue({
      data: { data: { status: 'EMPTY_LEDGER', positions: [] } },
    })
    getPortfolioSourceReconciliation.mockResolvedValue({
      data: {
        data: {
          status: 'NO_LEDGER',
          ledgerCanBecomeSource: false,
          positionDifferences: [],
        },
      },
    })
    importPortfolioOpeningSnapshot.mockResolvedValue({
      data: { data: { status: 'MATCHED' } },
    })
  })

  it('imports current assets only through an explicit opening snapshot action', async () => {
    render(<Ledger />)

    const button = await screen.findByRole('button', {
      name: '현재 자산을 시작점으로 가져오기',
    })
    expect(screen.getByText(/이 날짜 이후 기록만 계산/)).toBeInTheDocument()

    fireEvent.click(button)

    await waitFor(() => {
      expect(importPortfolioOpeningSnapshot).toHaveBeenCalledOnce()
    })
    expect(window.confirm).toHaveBeenCalledOnce()
  })
})

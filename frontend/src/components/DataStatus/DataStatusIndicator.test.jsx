import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getDataStatus } from '../../api/herdApi'
import DataStatusIndicator from './DataStatusIndicator'

vi.mock('../../api/herdApi', () => ({
  getDataStatus: vi.fn(),
}))

afterEach(cleanup)

beforeEach(() => {
  getDataStatus.mockResolvedValue({
    data: {
      data: {
        status: 'FRESH',
        latestPriceDate: '2026-07-24',
        latestObservationDate: '2026-07-24',
        expectedTickerCount: 55,
        latestRun: {
          status: 'SUCCESS',
          successCount: 55,
          failedCount: 0,
          skippedCount: 0,
        },
      },
    },
  })
})

describe('DataStatusIndicator', () => {
  it('keeps the top bar compact and reveals operational detail on demand', async () => {
    render(<DataStatusIndicator />)

    const trigger = await screen.findByRole('button', { name: '데이터 상태: 데이터 최신' })
    expect(screen.queryByRole('dialog', { name: '데이터 수집 상태' })).not.toBeInTheDocument()

    fireEvent.click(trigger)
    expect(screen.getByRole('dialog', { name: '데이터 수집 상태' })).toBeInTheDocument()
    expect(screen.getAllByText('2026.07.24')).toHaveLength(2)
    expect(screen.getByText('55/55 종목')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: '데이터 수집 상태' })).not.toBeInTheDocument()
    })
    expect(trigger).toHaveFocus()
  })
})

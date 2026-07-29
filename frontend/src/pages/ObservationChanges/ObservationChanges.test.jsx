import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../api/herdApi'
import ObservationChanges from './ObservationChanges'

const navigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

vi.mock('../../api/herdApi', () => ({
  getObservationChanges: vi.fn(),
  markAllObservationChangesSeen: vi.fn(),
  markObservationTickerSeen: vi.fn(),
}))

beforeEach(() => {
  navigate.mockReset()
  api.markObservationTickerSeen.mockResolvedValue({})
  api.markAllObservationChangesSeen.mockResolvedValue({})
  api.getObservationChanges.mockResolvedValue({
    data: { data: {
      generatedThrough: '2026-07-24',
      trackedTickerCount: 2,
      unreadCount: 1,
      events: [{
        id: 'NVDA:2026-07-24:TRANSITION',
        ticker: 'NVDA',
        companyName: 'NVIDIA Corporation',
        observationDate: '2026-07-24',
        eventType: 'TRANSITION',
        stateScore: 64,
        stage: 'DRIFT',
        transition: 'COOLING',
        delta4w: -6,
        trackingScope: 'HOLDING',
        unread: true,
      }],
      provisionalAttention: [{
        ticker: 'TSLA',
        provisionalDate: '2026-07-28',
        provisionalScore: 39,
        provisionalStage: 'SCATTER',
        confirmedDate: '2026-07-24',
        confirmedScore: 43,
        confirmedStage: 'CALM',
      }],
    } },
  })
})

describe('ObservationChanges', () => {
  it('shows observation-only changes and opens the stock context', async () => {
    render(
      <MemoryRouter>
        <ObservationChanges />
      </MemoryRouter>,
    )

    expect(await screen.findByText('NVIDIA Corporation')).toBeInTheDocument()
    expect(screen.getByText('밀집 완화')).toBeInTheDocument()
    expect(screen.getByText(/보유 · Drift · 상태 전환/)).toBeInTheDocument()
    expect(screen.getByText('주간 확정과 다른 단계')).toBeInTheDocument()
    expect(screen.getByText('Calm → Scatter')).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/매수|매도|익절|추천/)

    fireEvent.click(screen.getByRole('button', {
      name: /NVDA NVIDIA Corporation 밀집 완화/,
    }))
    await waitFor(() => expect(api.markObservationTickerSeen).toHaveBeenCalledWith(
      'NVDA',
      '2026-07-24',
    ))
    expect(navigate).toHaveBeenCalledWith('/stock/NVDA')
  })
})

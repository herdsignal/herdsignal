import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ROUTER_FUTURE } from '../../routerConfig'
import { describe, expect, it, vi } from 'vitest'
import PublicHome from './PublicHome'

vi.mock('../../api/herdApi', () => ({
  getHerdObservation: vi.fn(() => Promise.resolve({ data: { data: {
    availabilityStatus: 'AVAILABLE',
    stateScore: 68,
    stage: 'DRIFT',
  } } })),
}))

describe('PublicHome', () => {
  it('서비스 가치와 공개 분석 진입점을 보여준다', async () => {
    render(<MemoryRouter future={ROUTER_FUTURE}><PublicHome /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: /시장에 사람이/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'HERD 확인' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '내 대시보드' })).toHaveAttribute('href', '/app')
    expect(screen.getByRole('link', { name: '내 포트폴리오 보기' })).toHaveAttribute('href', '/portfolio')
    expect((await screen.findAllByText('Drift')).length).toBeGreaterThan(0)
  })
})

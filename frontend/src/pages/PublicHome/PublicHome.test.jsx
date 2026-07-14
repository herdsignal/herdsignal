import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import PublicHome from './PublicHome'

vi.mock('../../api/herdApi', () => ({
  getStockHerd: vi.fn(() => Promise.resolve({ data: { data: { herdScore: 68, herdStage: 'Drift' } } })),
  getModelValidationReport: vi.fn(() => Promise.resolve({ data: { data: null } })),
}))

describe('PublicHome', () => {
  it('서비스 가치와 공개 분석 진입점을 보여준다', async () => {
    render(<MemoryRouter><PublicHome /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: /시장이 시끄러울수록/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'HERD 확인' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '모델 검증 보기 ↗' })).toHaveAttribute('href', '/herd-lab')
    expect((await screen.findAllByText('Drift')).length).toBeGreaterThan(0)
  })
})

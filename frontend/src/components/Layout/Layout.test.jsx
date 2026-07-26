import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Layout from './Layout'

vi.mock('../../api/herdApi', () => ({
  getDataStatus: vi.fn().mockResolvedValue({
    data: { data: { status: 'FRESH' } },
  }),
  getObservationChanges: vi.fn().mockResolvedValue({
    data: { data: { unreadCount: 2 } },
  }),
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    user: {
      authenticated: true,
      developmentMode: true,
      displayName: '테스트 사용자',
    },
    signOut: vi.fn(),
  }),
}))

afterEach(cleanup)

describe('Layout', () => {
  it('통합 대시보드와 관찰 및 연구를 주요 경로로 제공한다', () => {
    render(
      <MemoryRouter initialEntries={['/portfolio']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/portfolio" element={<div>포트폴리오 화면</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('link', { name: '대시보드' })[0]).toHaveAttribute('href', '/app')
    expect(screen.getAllByRole('link', { name: '관찰' })[0]).toHaveAttribute('href', '/watchlist')
    expect(screen.getAllByRole('link', { name: '연구' })[0]).toHaveAttribute('href', '/herd-lab')
    expect(screen.getByRole('link', { name: '본문으로 건너뛰기' })).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(document.title).toBe('대시보드 · HerdSignal')
    expect(screen.getByText('포트폴리오 화면')).toBeInTheDocument()
  })

  it('returns focus to the account trigger when Escape closes the panel', () => {
    render(
      <MemoryRouter initialEntries={['/portfolio']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/portfolio" element={<div>포트폴리오 화면</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    const trigger = screen.getByRole('button', { name: '계정 메뉴 열기' })
    fireEvent.click(trigger)
    expect(screen.getByRole('button', { name: '계정 메뉴 닫기' })).toHaveAttribute('aria-expanded', 'true')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByLabelText('계정 메뉴')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})

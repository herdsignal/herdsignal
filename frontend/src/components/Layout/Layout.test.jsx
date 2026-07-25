import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Layout from './Layout'

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

vi.mock('../ActionNotifications/ActionNotifications', () => ({
  default: () => <div>알림 요약</div>,
}))

afterEach(cleanup)

describe('Layout', () => {
  it('exposes the new primary routes without dropping the current page outlet', () => {
    render(
      <MemoryRouter initialEntries={['/portfolio']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/portfolio" element={<div>포트폴리오 화면</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('link', { name: '시장' })[0]).toHaveAttribute('href', '/app')
    expect(screen.getAllByRole('link', { name: '포트폴리오' })[0]).toHaveAttribute('href', '/portfolio')
    expect(screen.getAllByRole('link', { name: '종목' })[0]).toHaveAttribute('href', '/search')
    expect(screen.getAllByRole('link', { name: '연구' })[0]).toHaveAttribute('href', '/herd-lab')
    expect(screen.getByRole('link', { name: '본문으로 건너뛰기' })).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(document.title).toBe('포트폴리오 · HerdSignal')
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

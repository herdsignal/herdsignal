import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
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
    expect(screen.getByText('포트폴리오 화면')).toBeInTheDocument()
  })
})

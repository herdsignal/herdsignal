import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import DashboardOnboarding, {
  DASHBOARD_ONBOARDING_KEY,
} from './DashboardOnboarding'

describe('DashboardOnboarding', () => {
  beforeEach(() => localStorage.clear())
  afterEach(cleanup)

  it('shows once and stays dismissed after confirmation', () => {
    const { unmount } = render(<DashboardOnboarding />)

    expect(screen.getByLabelText('대시보드 사용 순서')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '사용 순서 닫기' }))
    expect(localStorage.getItem(DASHBOARD_ONBOARDING_KEY)).toBe('done')
    expect(screen.queryByLabelText('대시보드 사용 순서')).not.toBeInTheDocument()

    unmount()
    render(<DashboardOnboarding />)
    expect(screen.queryByLabelText('대시보드 사용 순서')).not.toBeInTheDocument()
  })
})

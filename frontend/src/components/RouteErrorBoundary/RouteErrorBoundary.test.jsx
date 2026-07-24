import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { RouteErrorBoundary } from './RouteErrorBoundary'

function BrokenPage() {
  throw new Error('broken page')
}

test('resets a captured render error when the route key changes', () => {
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  const view = render(
    <RouteErrorBoundary resetKey="/broken">
      <BrokenPage />
    </RouteErrorBoundary>,
  )
  expect(screen.getByRole('alert')).toHaveTextContent('broken page')

  view.rerender(
    <RouteErrorBoundary resetKey="/healthy">
      <div>healthy page</div>
    </RouteErrorBoundary>,
  )

  expect(screen.getByText('healthy page')).toBeInTheDocument()
  consoleError.mockRestore()
})

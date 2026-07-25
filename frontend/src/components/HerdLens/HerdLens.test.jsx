import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import HerdLens from './HerdLens'

describe('HerdLens', () => {
  it('renders a stable density lens and accessible movement summary', () => {
    const { container } = render(
      <HerdLens score={68} stage="drift" previousScore={72} />,
    )

    expect(container.querySelectorAll('i')).toHaveLength(14)
    expect(
      screen.getByRole('img', {
        name: /HERD 68, Drift, 밀집 진행, 4주 전 72에서 -4 변화/,
      }),
    ).toBeInTheDocument()
  })

  it('fails closed when a score is unavailable', () => {
    render(<HerdLens score={null} />)

    expect(
      screen.getByRole('img', { name: 'HERD 관찰값 없음' }),
    ).toBeInTheDocument()
  })
})

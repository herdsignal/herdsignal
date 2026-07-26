import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import InvestorProfilePanel from './InvestorProfilePanel'

afterEach(cleanup)

describe('InvestorProfilePanel', () => {
  it('shows durable investor context without exposing an unvalidated action cap', () => {
    const onChange = vi.fn()
    render(
      <InvestorProfilePanel
        profile={{
          strategy: 'EXISTING_HOLDER',
          riskTolerance: 'BALANCED',
          timeHorizonYears: 10,
          liquidityBufferMonths: 6,
          maxActionRatio: 0.15,
          targetEquityRatio: 0.7,
        }}
        status=""
        onChange={onChange}
        onSubmit={vi.fn()}
      />,
    )

    expect(screen.getByText('기존 보유자 · 균형 · 10년')).toBeInTheDocument()
    expect(screen.queryByText(/1회 상한|승인 시 상한/)).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('설정 변경'))
    expect(screen.getByText('목표 주식 비중')).toBeInTheDocument()
    expect(screen.queryByText(/1회 상한|승인 시 상한/)).not.toBeInTheDocument()
  })
})

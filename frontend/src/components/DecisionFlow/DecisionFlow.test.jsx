import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import DecisionFlow from './DecisionFlow'

describe('DecisionFlow', () => {
  it('connects herd trend weight and action', () => {
    render(<DecisionFlow herd={{
      herdScore: 72,
      herdStage: 'Herd Drift',
      signal: 'REDUCE',
      actionLabel: '일부 축소',
      actionReasons: ['장기 추세 품질 78/100'],
    }} currentWeight={22} targetWeight={15} />)

    expect(screen.getByText('Drift 72')).toBeInTheDocument()
    expect(screen.getByText('품질 78/100')).toBeInTheDocument()
    expect(screen.getByText('목표 초과')).toBeInTheDocument()
    expect(screen.getByText('일부 축소')).toBeInTheDocument()
  })
})

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getModelValidationReport,
  getShadowModelStatus,
} from '../../api/herdApi'
import HerdLab from './HerdLab'

vi.mock('../../api/herdApi', () => ({
  getModelValidationReport: vi.fn(),
  getShadowModelStatus: vi.fn(),
}))

const legacyReport = {
  modelVersion: 'HERD_v6.1',
  generatedAt: '2026-07-14T00:00:00Z',
  validationRun: {
    completedTickers: 55,
    requestedTickers: 55,
    coverage: 1,
    embargoDays: 20,
  },
  walkForward: {
    samples: 440,
    improvementRate: 36.4,
    mddImprovementMedian: 0.9,
  },
  parameterStability: {
    sameParameterRate: 59.4,
    singleParameterSpike: true,
    recommendation: 'USE_FIXED_PARAMETERS',
  },
  overfitting: {
    parametersTested: 9,
    deflatedSharpeStatus: 'FAIL',
  },
  adoptionGate: {
    policyVersion: '2026.07-v1',
    status: 'RESEARCH_VALIDATION',
    eligibleForHumanReview: false,
    failedCriteria: ['deflated_sharpe'],
  },
  scoreParityPassed: true,
  survivorshipStatus: 'SURVIVORSHIP_BIAS_REMAINS',
  tickers: [],
  actionOutcomes: [],
}

afterEach(cleanup)

beforeEach(() => {
  getModelValidationReport.mockResolvedValue({
    data: { data: legacyReport },
  })
  getShadowModelStatus.mockResolvedValue({
    data: { data: { shadowStatus: 'DISABLED_RESEARCH_GATE_FAILED' } },
  })
})

describe('HerdLab', () => {
  it('keeps the operating scope separate from closed legacy action research', async () => {
    render(<HerdLab />)

    expect(screen.getByText('State S1 관찰 운영 · 행동 모델 미채택')).toBeInTheDocument()
    const summary = await screen.findByText('v4 · v6.1 검증 기록')
    const archive = summary.closest('details')
    expect(archive).not.toHaveAttribute('open')

    fireEvent.click(summary)
    expect(archive).toHaveAttribute('open')
    expect(screen.getByText('HERD_v6.1 · Validated Progressive Action Layer')).toBeInTheDocument()
  })

  it('preserves the current operating scope when the legacy report fails', async () => {
    getModelValidationReport.mockRejectedValue(new Error('offline'))

    render(<HerdLab />)

    expect(screen.getByText('State S1 관찰 운영 · 행동 모델 미채택')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('과거 검증 리포트를 불러오지 못했습니다.')).toBeInTheDocument()
    })
  })
})

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getModelValidationReport,
  getProspectiveEvidenceStatus,
  getShadowModelStatus,
  getVNextModelStatus,
} from '../../api/herdApi'
import HerdLab from './HerdLab'

vi.mock('../../api/herdApi', () => ({
  getModelValidationReport: vi.fn(),
  getProspectiveEvidenceStatus: vi.fn(),
  getShadowModelStatus: vi.fn(),
  getVNextModelStatus: vi.fn(),
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
  getVNextModelStatus.mockResolvedValue({
    data: {
      data: {
        sourceContractAccepted: true,
        validationStatus: 'STATE_OBSERVATION_MVP_READY',
        adoptableCandidate: false,
        operationalActionRatio: 0,
        blindHoldoutOpened: false,
        promotionBlockers: [
          'PERSONAL_POLICY_PREHOLDOUT_FAILED',
          'BLIND_HOLDOUT_NOT_PASSED',
          'SURVIVORSHIP_SAFE_FALSE',
        ],
      },
    },
  })
  getProspectiveEvidenceStatus.mockResolvedValue({
    data: {
      data: {
        auditPassed: true,
        observationArchives: 1,
        firstObservationDate: '2026-07-24',
        latestObservationDate: '2026-07-24',
        observationRecords: 440,
        maturedOutcomes: 0,
        pendingOutcomes: 1320,
      },
    },
  })
})

describe('HerdLab', () => {
  it('keeps the operating scope separate from closed legacy action research', async () => {
    render(<HerdLab />)

    expect(screen.getByText('State S1 관찰 운영 · 행동 모델 미채택')).toBeInTheDocument()
    expect(await screen.findByText('사전 채택 기준 미통과')).toBeInTheDocument()
    expect(screen.getByText('Blind holdout 미통과')).toBeInTheDocument()
    expect(screen.getByText('생존자 편향 잔존')).toBeInTheDocument()
    expect(screen.getByText('전향 관찰 원장')).toBeInTheDocument()
    expect(screen.getByText('대기 1,320개')).toBeInTheDocument()
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

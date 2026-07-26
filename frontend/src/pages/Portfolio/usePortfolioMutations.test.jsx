import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  removeFromPortfolio,
  updateCashBalance,
  updateTargetWeight,
} from '../../api/herdApi'
import { usePortfolioMutations } from './usePortfolioMutations'

vi.mock('../../api/herdApi', () => ({
  removeFromPortfolio: vi.fn(),
  updateCashBalance: vi.fn(),
  updateTargetWeight: vi.fn(),
}))

function hookProps() {
  return {
    userId: 1,
    portfolio: [{ ticker: 'NVDA', avgPrice: 100, quantity: 2 }],
    setPortfolio: vi.fn(),
    setSummary: vi.fn(),
    priceMap: {},
    cashBalance: 0,
    setCashBalance: vi.fn(),
    cashDraft: '',
    setCashDraft: vi.fn(),
    setTargetWeights: vi.fn(),
    modalTicker: null,
    setModalTicker: vi.fn(),
    fetchData: vi.fn(),
    assetPanelOpen: false,
    fetchAssetHistory: vi.fn(),
    setRefreshNotice: vi.fn(),
  }
}

describe('usePortfolioMutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    removeFromPortfolio.mockResolvedValue({})
    updateCashBalance.mockResolvedValue({ data: { data: { cashAmount: 0 } } })
    updateTargetWeight.mockResolvedValue({})
  })

  it('stores a target percentage as the API decimal value', async () => {
    const props = hookProps()
    const { result } = renderHook(() => usePortfolioMutations(props))

    let saved
    await act(async () => {
      saved = await result.current.handleTargetWeightSave('NVDA', '35.5')
    })

    expect(saved).toBe(true)
    expect(updateTargetWeight).toHaveBeenCalledWith('NVDA', 0.355)
    expect(props.setPortfolio).toHaveBeenCalledOnce()
    expect(props.setTargetWeights).toHaveBeenCalledOnce()
    expect(props.setRefreshNotice).toHaveBeenCalledWith(
      'NVDA 목표 비중을 저장했습니다.',
    )
  })

  it('does not translate an empty target field into zero percent', async () => {
    const props = hookProps()
    const { result } = renderHook(() => usePortfolioMutations(props))

    let saved
    await act(async () => {
      saved = await result.current.handleTargetWeightSave('NVDA', ' ')
    })

    expect(saved).toBe(false)
    expect(updateTargetWeight).not.toHaveBeenCalled()
  })
})

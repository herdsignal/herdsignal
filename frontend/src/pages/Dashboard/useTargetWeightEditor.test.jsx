import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { updateTargetWeight } from '../../api/herdApi'
import { useTargetWeightEditor } from './useTargetWeightEditor'

vi.mock('../../api/herdApi', () => ({
  updateTargetWeight: vi.fn(),
}))

beforeEach(() => {
  vi.useFakeTimers()
  updateTargetWeight.mockResolvedValue({ data: { data: null } })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('useTargetWeightEditor', () => {
  it('persists only the final value after the debounce window', async () => {
    const { result } = renderHook(() => useTargetWeightEditor())

    act(() => {
      result.current.handleTargetWeightChange('NVDA', '40')
      result.current.handleTargetWeightChange('NVDA', '35')
      vi.advanceTimersByTime(400)
    })
    await act(async () => Promise.resolve())

    expect(result.current.targetWeights.NVDA).toBe('35')
    expect(updateTargetWeight).toHaveBeenCalledTimes(1)
    expect(updateTargetWeight).toHaveBeenCalledWith('NVDA', 0.35)
  })

  it('cancels pending writes when the dashboard unmounts', () => {
    const { result, unmount } = renderHook(() => useTargetWeightEditor())

    act(() => result.current.handleTargetWeightChange('TSLA', '20'))
    unmount()
    act(() => vi.advanceTimersByTime(400))

    expect(updateTargetWeight).not.toHaveBeenCalled()
  })
})

import { describe, expect, it } from 'vitest'
import { presentShadowStatus } from './shadowModelPresentation'

describe('presentShadowStatus', () => {
  it('does not expose a rejected candidate', () => {
    expect(presentShadowStatus({
      shadowStatus: 'DISABLED_RESEARCH_GATE_FAILED',
      candidateId: 'B3',
    })).toEqual({
      tone: 'blocked',
      label: '차세대 후보 없음',
      candidate: null,
    })
  })

  it('shows candidate only while shadow is active', () => {
    expect(presentShadowStatus({
      shadowStatus: 'SHADOW_ACTIVE',
      candidateId: 'B5',
    }).candidate).toBe('B5')
  })
})

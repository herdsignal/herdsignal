import { describe, expect, it } from 'vitest'
import { presentVNextStatus } from './vNextModelPresentation'

describe('vNext model status presentation', () => {
  it('presents accepted observation scope without action authority', () => {
    expect(presentVNextStatus({
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
    })).toMatchObject({
      observationLabel: 'State S1',
      actionLabel: '후보 없음',
      actionRatioLabel: '0%',
      holdoutLabel: '미개방',
      blockers: ['사전 채택 기준 미통과', 'Blind holdout 미통과', '생존자 편향 잔존'],
    })
  })

  it('fails closed when the source contract is unavailable', () => {
    expect(presentVNextStatus(null)).toMatchObject({
      observationLabel: '확인 불가',
      actionLabel: '차단',
      actionRatioLabel: '0%',
      holdoutLabel: '미개방',
      blockers: ['최신 판정 파일 없음'],
    })
  })
})

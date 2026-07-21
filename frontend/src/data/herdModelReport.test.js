import { describe, expect, it } from 'vitest'

import herdModelReport from './herdModelReport'

describe('herdModelReport action boundary', () => {
  it('does not expose an unadmitted Drift or Rush profit-take ratio', () => {
    const sellSide = herdModelReport.stages.filter(({ stage }) => ['Drift', 'Rush'].includes(stage))
    expect(sellSide).toHaveLength(2)
    sellSide.forEach((stage) => {
      expect(stage.ratio).toBe('행동 미채택')
      expect(stage.action).not.toContain('익절')
    })
  })
})

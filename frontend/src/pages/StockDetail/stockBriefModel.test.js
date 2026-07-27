import { describe, expect, it } from 'vitest'
import { buildStockBrief } from './stockBriefModel'

describe('stock brief model', () => {
  it('reports observed facts without inventing an action', () => {
    const brief = buildStockBrief({
      observation: {
        families: {
          priceExtension: 71,
          trendPosition: 82,
          participation: 55,
        },
      },
      fundamentalGuard: { label: '확인된 주요 경고 없음' },
      episodeStudy: {
        evidenceStatus: 'INSUFFICIENT_SAMPLE',
        summaries: [{ completedCount: 2 }],
      },
    })

    expect(brief[0]).toMatchObject({ value: '추세 위치', note: '82/100' })
    expect(brief[2].value).toBe('표본 부족')
    expect(JSON.stringify(brief)).not.toMatch(/매수|매도|익절|추천/)
  })
})

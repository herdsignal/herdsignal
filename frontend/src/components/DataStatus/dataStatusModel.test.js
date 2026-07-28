import { describe, expect, it } from 'vitest'
import {
  dataStatusViewModel,
  formatObservedDate,
  schedulerRunLabel,
} from './dataStatusModel'

describe('dataStatusViewModel', () => {
  it('compresses fresh collection metadata into factual labels', () => {
    const view = dataStatusViewModel({
      status: 'FRESH',
      latestPriceDate: '2026-07-24',
      latestObservationDate: '2026-07-18',
      expectedTickerCount: 55,
      latestRun: {
        status: 'SUCCESS',
        successCount: 55,
        failedCount: 0,
        skippedCount: 0,
        finishedAt: '2026-07-25T01:10:00Z',
      },
    })

    expect(view.label).toBe('데이터 최신')
    expect(view.tone).toBe('fresh')
    expect(view.priceDate).toBe('2026.07.24')
    expect(view.scoreDate).toBe('2026.07.18')
    expect(view.coverageLabel).toBe('55/55 종목')
    expect(view.runLabel).toContain('완료')
    expect(view.issueLabel).toBeNull()
  })

  it('surfaces collection and calculation gaps without action language', () => {
    const view = dataStatusViewModel({
      status: 'WARNING',
      expectedTickerCount: 55,
      missingPriceTickerCount: 2,
      missingObservationTickerCount: 3,
      latestRun: {
        status: 'PARTIAL_FAILURE',
        successCount: 50,
        failedCount: 2,
        skippedCount: 3,
      },
    })

    expect(view.label).toBe('일부 확인')
    expect(view.issueLabel).toBe('실패 2 · 제외 3 · S1 미산출 3')
    expect(view.coverageLabel).toBe('50/55 종목')
    expect(view.scheduleLabel).toBe('매일 16:30 ET')
  })

  it('fails closed when status cannot be loaded', () => {
    const view = dataStatusViewModel(null, { error: true })
    expect(view.label).toBe('상태 확인 불가')
    expect(view.runLabel).toBe('백엔드 연결 확인')
  })
})

describe('data status formatting', () => {
  it('formats observation dates and unknown values safely', () => {
    expect(formatObservedDate('2026-07-24')).toBe('2026.07.24')
    expect(formatObservedDate(null)).toBe('—')
  })

  it('keeps a running scheduler distinct from completed runs', () => {
    expect(schedulerRunLabel({ status: 'RUNNING' })).toBe('실행 중')
    expect(schedulerRunLabel(null)).toBe('실행 기록 없음')
  })
})

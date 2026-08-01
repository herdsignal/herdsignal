import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getDataStatus,
  requestDailySchedulerRun,
  requestSchedulerRun,
} from '../../api/herdApi'
import DataStatusIndicator from './DataStatusIndicator'

vi.mock('../../api/herdApi', () => ({
  getDataStatus: vi.fn(),
  requestDailySchedulerRun: vi.fn(),
  requestSchedulerRun: vi.fn(),
}))

afterEach(cleanup)

beforeEach(() => {
  getDataStatus.mockResolvedValue({
    data: {
      data: {
        status: 'FRESH',
        latestPriceDate: '2026-07-24',
        latestObservationDate: '2026-07-24',
        latestDailyObservationDate: '2026-07-24',
        dailyObservationStatus: 'FRESH',
        expectedDailyObservationTickerCount: 55,
        freshDailyObservationTickerCount: 55,
        expectedTickerCount: 55,
        schedulerCadence: {
          automationMode: 'EXTERNAL_DAEMON',
          requiresExternalProcess: true,
          daemonStatus: 'RUNNING',
          daemonRunning: true,
          lastHeartbeatAt: '2026-07-28T01:20:00Z',
          timezone: 'America/New_York',
          dailyTime: '16:30',
          nextScheduledAt: '2026-07-28T16:30:00-04:00',
          manualRunScope: 'FULL_TIER1',
        },
        latestRun: {
          status: 'SUCCESS',
          successCount: 55,
          failedCount: 0,
          skippedCount: 0,
          phases: [
            { code: 'PRICE_COLLECTION', status: 'SUCCESS', count: 55 },
            { code: 'DAILY_D1', status: 'SUCCESS', count: 55 },
          ],
        },
      },
    },
  })
  requestSchedulerRun.mockResolvedValue({ status: 202 })
  requestDailySchedulerRun.mockResolvedValue({ status: 202 })
})

describe('DataStatusIndicator', () => {
  it('keeps the top bar compact and reveals operational detail on demand', async () => {
    render(<DataStatusIndicator />)

    const trigger = await screen.findByRole('button', { name: '데이터 상태: 데이터 최신' })
    expect(screen.queryByRole('dialog', { name: '데이터 수집 상태' })).not.toBeInTheDocument()

    fireEvent.click(trigger)
    expect(screen.getByRole('dialog', { name: '데이터 수집 상태' })).toBeInTheDocument()
    expect(screen.getAllByText('2026.07.24')).toHaveLength(3)
    expect(screen.getByText('가격 데이터')).toBeInTheDocument()
    expect(screen.getByText('거래일마다')).toBeInTheDocument()
    expect(screen.getByText('State S1')).toBeInTheDocument()
    expect(screen.getByText('주 1회')).toBeInTheDocument()
    expect(screen.getByText('Daily D1')).toBeInTheDocument()
    expect(screen.getByText('잠정')).toBeInTheDocument()
    expect(screen.getByText('최신 · 55/55 종목')).toBeInTheDocument()
    expect(screen.getByText('미국장 마감 후 반영')).toBeInTheDocument()
    expect(screen.getByText('완료된 금요일 기준')).toBeInTheDocument()
    expect(screen.getByText('55/55 종목')).toBeInTheDocument()
    expect(screen.getByText('16:30 ET')).toBeInTheDocument()
    expect(screen.getByText(/다음 예정/)).toBeInTheDocument()
    expect(screen.getByText(/자동 실행 중 · 확인/)).toBeInTheDocument()
    expect(screen.getByText(/일간 갱신은 가격·D1만/)).toBeInTheDocument()
    expect(screen.getByRole('list', { name: '최근 실행 단계' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '상태 다시 확인' })).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: '데이터 수집 상태' })).not.toBeInTheDocument()
    })
    expect(trigger).toHaveFocus()
  })

  it('requests a lightweight daily scheduler run explicitly', async () => {
    render(<DataStatusIndicator />)
    fireEvent.click(await screen.findByRole('button', { name: '데이터 상태: 데이터 최신' }))
    fireEvent.click(screen.getByText('수동 실행'))
    fireEvent.click(screen.getByRole('button', { name: '일간 잠정 갱신' }))

    await waitFor(() => expect(requestDailySchedulerRun).toHaveBeenCalledOnce())
    expect(await screen.findByRole('status')).toHaveTextContent('일간 잠정 갱신을 시작했습니다.')
  })
})

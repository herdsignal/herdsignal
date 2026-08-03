import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ROUTER_FUTURE } from '../../routerConfig'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StockDetail from './StockDetail'
import * as api from '../../api/herdApi'

vi.mock('../../api/herdApi', () => ({
  getDailyHerdObservation: vi.fn(),
  getHerdObservation: vi.fn(),
  getHerdPriceTimeline: vi.fn(),
  getHerdEpisodeStudy: vi.fn(),
  getHistoricalS1Context: vi.fn(),
  addToPortfolio: vi.fn(),
  addToWatchlist: vi.fn(),
  getPortfolio: vi.fn(),
  getWatchlist: vi.fn(),
  getStockFinancials: vi.fn(),
  getSignalJournal: vi.fn(),
  createSignalJournal: vi.fn(),
  deleteSignalJournal: vi.fn(),
  getObjectiveOperatingReview: vi.fn(),
  getPersonalOperatingReview: vi.fn(),
  getOperatingReviewRecords: vi.fn(),
  recordOperatingReview: vi.fn(),
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { authenticated: true, id: 'user-1' } }),
}))

const response = (data) => Promise.resolve({ data: { data } })

beforeEach(() => {
  api.getPortfolio.mockReturnValue(response([]))
  api.getWatchlist.mockReturnValue(response([]))
  api.getHerdObservation.mockReturnValue(response({
    ticker: 'NVDA',
    companyName: 'NVIDIA Corp',
    availabilityStatus: 'AVAILABLE',
    freshnessStatus: 'FRESH',
    stateScore: 63,
    delta4w: 6,
    stage: 'DRIFT',
    observationDate: '2026-07-24',
    lastObservedSession: '2026-07-24',
    transition: 'NEUTRAL',
    families: {
      priceExtension: 70,
      trendPosition: 65,
      relativePosition: 60,
      participation: 57,
    },
    downsideRiskContext: 35,
  }))
  api.getDailyHerdObservation.mockReturnValue(response({
    ticker: 'NVDA',
    availabilityStatus: 'AVAILABLE',
    freshnessStatus: 'FRESH',
    stateModelVersion: 'HERD_DAILY_D1',
    stateScore: 76,
    stage: 'RUSH',
    observationDate: '2026-07-28',
    lastObservedSession: '2026-07-28',
  }))
  api.getSignalJournal.mockReturnValue(response([]))
  api.getHerdEpisodeStudy.mockReturnValue(response({
    availabilityStatus: 'AVAILABLE',
    evidenceStatus: 'INSUFFICIENT_SAMPLE',
    herdStage: 'DRIFT',
    minimumCompletedEpisodes: 5,
    episodeCount: 2,
    summaries: [],
  }))
  api.getHistoricalS1Context.mockReturnValue(response({
    availabilityStatus: 'AVAILABLE',
    contextScope: 'TICKER_HISTORY',
    herdStage: 'DRIFT',
    episodeCount: 7,
    summaries: [{
      horizonSessions: 21,
      completedEpisodes: 7,
      medianReturnPct: 2.4,
      positiveRatePct: 57.1,
      medianMfePct: 8.1,
      medianMaePct: -6.2,
    }],
  }))
  api.getHerdPriceTimeline.mockReturnValue(response({
    stateModelVersion: 'HERD_STATE_S1',
    priceField: 'ADJUSTED_CLOSE',
    observationCount: 4,
    pricedObservationCount: 4,
    points: [
    {
      observationDate: '2026-07-03',
      marketSession: '2026-07-03',
      adjustedClose: 148,
      herdScore: 55,
      herdStage: 'CALM',
      transition: 'NEUTRAL',
      transitionEvent: false,
    },
    {
      observationDate: '2026-07-10',
      marketSession: '2026-07-10',
      adjustedClose: 151,
      herdScore: 60,
      herdStage: 'DRIFT',
      transition: 'RECOVERING',
      transitionEvent: true,
    },
    {
      observationDate: '2026-07-17',
      marketSession: '2026-07-17',
      adjustedClose: 154,
      herdScore: 61,
      herdStage: 'DRIFT',
      transition: 'NEUTRAL',
      transitionEvent: false,
    },
    {
      observationDate: '2026-07-24',
      marketSession: '2026-07-24',
      adjustedClose: 157,
      herdScore: 63,
      herdStage: 'DRIFT',
      transition: 'NEUTRAL',
      transitionEvent: false,
    },
    ],
  }))
  api.getStockFinancials.mockReturnValue(response({
    marketCap: 5_000_000_000_000, trailingPe: 32, eps: 6.5,
    operatingMargin: 65, totalRevenue: 250_000_000_000,
  }))
  api.getPersonalOperatingReview.mockReturnValue(response({
    status: 'OBSERVE',
    objective: {
      evidencePacket: {
        facts: [
          {
            id: 'BUSINESS.PIT.REVENUE_YOY', area: 'BUSINESS_HEALTH',
            label: '매출 전년 대비', value: '0.25', quality: 'AVAILABLE',
            asOfDate: '2026-05-20',
          },
          {
            id: 'BUSINESS.PIT.NET_MARGIN', area: 'BUSINESS_HEALTH',
            label: '순이익률', value: '0.42', quality: 'AVAILABLE',
            asOfDate: '2026-05-20',
          },
          {
            id: 'BUSINESS.PIT.NET_MARGIN_YOY_CHANGE', area: 'BUSINESS_HEALTH',
            label: '순이익률 전년 대비 변화', value: '0.03', quality: 'AVAILABLE',
            asOfDate: '2026-05-20',
          },
          {
            id: 'BUSINESS.PIT.OPERATING_CASH_FLOW_YOY', area: 'BUSINESS_HEALTH',
            label: '영업현금흐름 전년 대비', value: '0.18', quality: 'AVAILABLE',
            asOfDate: '2026-05-20',
          },
          {
            id: 'BUSINESS.PIT.LIABILITIES_TO_ASSETS', area: 'BUSINESS_HEALTH',
            label: '부채/자산', value: '0.25', quality: 'AVAILABLE',
            asOfDate: '2026-05-20',
          },
          {
            id: 'BUSINESS.PIT.LIABILITIES_TO_ASSETS_YOY_CHANGE', area: 'BUSINESS_HEALTH',
            label: '부채/자산 전년 대비 변화', value: '-0.02', quality: 'AVAILABLE',
            asOfDate: '2026-05-20',
          },
          {
            id: 'EXPECTATION.GUIDANCE.revenue-fy2027', area: 'EXPECTATION_VALUATION',
            label: 'Revenue · FY2027 · NON_GAAP', value: '100–120 USD_M',
            quality: 'AVAILABLE', asOfDate: '2026-05-20',
          },
          {
            id: 'MARKET.SPY.RETURN_63', area: 'MARKET_SECTOR',
            label: 'SPY 63세션 수익률', value: '-0.08', quality: 'AVAILABLE',
            asOfDate: '2026-07-24',
          },
          {
            id: 'MARKET.SECTOR.RELATIVE_63', area: 'MARKET_SECTOR',
            label: '섹터 ETF 대 SPY 63세션 상대수익', value: '-0.02', quality: 'AVAILABLE',
            asOfDate: '2026-07-24',
          },
          {
            id: 'MARKET.ATTRIBUTION.CLASS', area: 'MARKET_SECTOR',
            label: '최근 약세 귀속', value: 'MARKET_COMMON', quality: 'AVAILABLE',
            asOfDate: '2026-07-24',
          },
        ],
      },
      assessments: [
        { area: 'BUSINESS_HEALTH', status: 'PARTIAL', headline: 'SEC PIT 재무 사실 확인' },
        { area: 'EXPECTATION_VALUATION', status: 'PARTIAL', headline: '경영진 가이던스 원문 1건 확인' },
        { area: 'MARKET_SECTOR', status: 'PARTIAL', headline: '최근 약세의 시장 공통 기여가 가장 큼' },
        { area: 'CHART_CROWD', status: 'AVAILABLE', headline: 'DRIFT · NEUTRAL' },
      ],
    },
    mandate: { timeHorizonYears: 10, effectiveActionRatioCap: 0 },
    portfolioFit: {
      currentTickerWeight: 0.2,
      currentCashRatio: 0.25,
      equityTargetGap: 0.05,
    },
    riskVeto: { actionBlocked: true },
    synthesis: {
      decision: 'OBSERVE',
      headline: '상태 관찰',
      limitations: ['채택된 방향성 정보 근거가 없습니다.'],
    },
  }))
  api.getOperatingReviewRecords.mockReturnValue(response([{
    id: 1,
    ticker: 'NVDA',
    referencePriceDate: '2026-01-02',
    referencePrice: 100,
    decisionCode: 'OBSERVE',
    actionAuthorized: false,
    actionRatio: 0,
    outcomes: [
      { horizonMonths: 1, status: 'AVAILABLE', measuredAt: '2026-02-02', priceReturnPct: -5 },
      { horizonMonths: 3, status: 'PENDING' },
      { horizonMonths: 6, status: 'UNAVAILABLE' },
    ],
  }]))
  api.getObjectiveOperatingReview.mockReturnValue(response(null))
})

afterEach(cleanup)

describe('StockDetail route', () => {
  it('renders the stock page after loading', async () => {
    render(
      <MemoryRouter initialEntries={['/stock/NVDA']} future={ROUTER_FUTURE}>
        <Routes>
          <Route path="/stock/:ticker" element={<StockDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('NVIDIA Corp')).toBeInTheDocument()
    expect(screen.getByText('HERD DAILY NOWCAST')).toBeInTheDocument()
    expect(screen.getByText('2026-07-28 일간 잠정')).toBeInTheDocument()
    expect(screen.getByText('63 · Drift')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '관찰 요약' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '종목 상세 구역' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '가격 · HERD 이력' })).toHaveAttribute(
      'href',
      '#stock-history',
    )
    expect(screen.getByRole('link', { name: '기업 정보' })).toHaveAttribute(
      'href',
      '#stock-records',
    )
    expect(screen.getByRole('link', { name: '장기 운용 검토' })).toHaveAttribute(
      'href',
      '#stock-operating-review',
    )
    expect(await screen.findByRole('heading', { name: '장기 운용 검토' })).toBeInTheDocument()
    expect(screen.getByText('행동 가능 비율')).toBeInTheDocument()
    expect(screen.getByText('채택된 방향성 정보 근거가 없습니다.')).toBeInTheDocument()
    expect(screen.getByText('매출 전년 대비')).toBeInTheDocument()
    expect(screen.getAllByText('25.0%')).toHaveLength(3)
    expect(screen.getByText('현금 비중')).toBeInTheDocument()
    expect(screen.getByText('주식 목표 차이')).toBeInTheDocument()
    expect(screen.getByText('+5.0%p')).toBeInTheDocument()
    expect(screen.getByText('현금창출')).toBeInTheDocument()
    expect(screen.getByText('재무구조')).toBeInTheDocument()
    expect(screen.getByText('순이익률 · 전년 대비 3.0%')).toBeInTheDocument()
    expect(screen.getByText('부채/자산 · 전년 대비 -2.0%')).toBeInTheDocument()
    expect(screen.getByText('2026-05-20 접수 기준')).toBeInTheDocument()
    expect(screen.getByText('컨센서스/PIT 밸류 미연결', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('MARKET CONTEXT')).toBeInTheDocument()
    expect(screen.getByText('시장 공통')).toBeInTheDocument()
    expect(screen.getByText('2026-07-24 종가 · 설명 전용')).toBeInTheDocument()
    expect(screen.getByText('저장 판단 이후 가격 경로')).toBeInTheDocument()
    expect(screen.getByText('-5.0%')).toBeInTheDocument()
    expect(screen.getByText('성공 판정 아님', { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '판단 기록' })).toHaveAttribute(
      'href',
      '#stock-journal',
    )
    expect(screen.getByText('현재 군중 상태')).toBeInTheDocument()
    expect(await screen.findByText('57 → 63')).toBeInTheDocument()
    expect(screen.getByText('2026-07-24 · 3주째')).toBeInTheDocument()
    expect(screen.getAllByText('군중 회복')).toHaveLength(2)
    expect(screen.getByRole('list', { name: 'HERD 상태 사건' })).toBeInTheDocument()
    expect(screen.getByText('HERD 구성')).toBeInTheDocument()
    expect(screen.getAllByText('수정 종가')).toHaveLength(2)
    expect(screen.getByText('4/4')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: '가격 · HERD 이력' }).compareDocumentPosition(
        screen.getByRole('heading', { name: 'HERD 구성' }),
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/익절 근거|매수 근거|추천/)
  })

  it('keeps company context and personal records available without a HERD observation', async () => {
    api.getHerdObservation.mockReturnValue(response({
      ticker: 'NVDA',
      companyName: 'NVIDIA Corp',
      availabilityStatus: 'PENDING',
    }))

    render(
      <MemoryRouter initialEntries={['/stock/NVDA']} future={ROUTER_FUTURE}>
        <Routes>
          <Route path="/stock/:ticker" element={<StockDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('HERD 관찰값 준비 중')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '기업 정보 · 판단 기록' }))
      .toBeInTheDocument()
    expect(screen.getByText('내 판단 기록')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '가격 · HERD 이력' }))
      .not.toBeInTheDocument()
  })
})

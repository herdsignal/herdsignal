const scoreDate = '2026-07-23'

export const user = {
  authenticated: true,
  id: 'visual-user',
  displayName: '백민수',
  email: 'visual@herdsignal.local',
  developmentMode: false,
}

export const spy = herdStock('SPY', {
  companyName: 'S&P 500',
  sector: 'Market',
  herdScore: 64,
  herdStage: 'Herd Drift',
  signal: 'HOLD',
  actionLabel: '시장 상태 관찰',
  actionScore: 51,
})

export const spyObservation = observation('SPY', 64, {
  scope: 'MARKET_AGGREGATE',
  label: 'S&P 500 군중 상태',
  claimCode: 'CROWD_STATE_NOT_SPY_PRICE_SCORE',
  referenceCoverageFraction: 0.982,
})

export const portfolio = [
  { ticker: 'NVDA', companyName: 'NVIDIA', avgPrice: 118, quantity: 32, targetWeight: 0.38 },
  { ticker: 'TSLA', companyName: 'Tesla', avgPrice: 284, quantity: 18, targetWeight: 0.26 },
  { ticker: 'IONQ', companyName: 'IonQ', avgPrice: 28, quantity: 70, targetWeight: 0.18 },
  { ticker: 'RKLB', companyName: 'Rocket Lab', avgPrice: 18, quantity: 60, targetWeight: 0.18 },
]

export const portfolioHerd = [
  herdStock('NVDA', { companyName: 'NVIDIA', herdScore: 78, herdStage: 'Herd Rush', signal: 'REDUCE', actionLabel: '익절 근거 검증 중', actionScore: 71 }),
  herdStock('TSLA', { companyName: 'Tesla', herdScore: 68, herdStage: 'Herd Drift', signal: 'HOLD', actionLabel: '보유 관찰', actionScore: 48 }),
  herdStock('IONQ', { companyName: 'IonQ', herdScore: 27, herdStage: 'Herd Scatter', signal: 'ADD', actionLabel: '추가매수 근거 검증 중', actionScore: 62 }),
  herdStock('RKLB', { companyName: 'Rocket Lab', herdScore: 43, herdStage: 'Herd Calm', signal: 'HOLD', actionLabel: '균형 구간', actionScore: 39 }),
]

export const watchlist = [
  herdStock('AMZN', { companyName: 'Amazon', herdScore: 24, herdStage: 'Herd Scatter', signal: 'ADD', actionLabel: '추가매수 관찰', actionScore: 76, actionRatio: 0.05 }),
  herdStock('GOOGL', { companyName: 'Alphabet', herdScore: 38, herdStage: 'Herd Scatter', signal: 'BUY', actionLabel: '신규 진입 관찰', actionScore: 69, actionRatio: 0.05 }),
  herdStock('META', { companyName: 'Meta', herdScore: 55, herdStage: 'Herd Calm', signal: 'HOLD', actionLabel: '대기', actionScore: 45 }),
  herdStock('AVGO', { companyName: 'Broadcom', herdScore: 81, herdStage: 'Herd Rush', signal: 'REDUCE', actionLabel: '과열 관찰', actionScore: 73 }),
]

export const trackedObservations = [...portfolioHerd, ...watchlist].map((item) => (
  observation(item.ticker, item.herdScore, {
    companyName: item.companyName,
    sector: item.sector,
    logoUrl: item.logoUrl,
  })
))

export const portfolioSummary = {
  invested_value: 22_880,
  cash_balance: 2_120,
  total_value: 25_000,
  total_asset_value: 25_000,
  total_cost: 20_200,
  total_return_pct: 13.27,
  daily_change_pct: -1.14,
  totalValue: 25_000,
  totalCost: 20_200,
  totalReturnPct: 13.27,
  dailyChangePct: -1.14,
  market_data_date: scoreDate,
  stocks: [
    priceRow('NVDA', 178, 5_696, 50.85, -1.2),
    priceRow('TSLA', 326, 5_868, 14.79, -2.1),
    priceRow('IONQ', 42, 2_940, 50.0, -0.8),
    priceRow('RKLB', 31, 1_860, 72.22, -0.4),
  ],
}

export const portfolioHistory = [
  assetPoint('2026-01-31', 18_400, 17_600, 800),
  assetPoint('2026-02-28', 19_250, 18_300, 950),
  assetPoint('2026-03-31', 17_900, 16_850, 1_050),
  assetPoint('2026-04-30', 20_300, 19_100, 1_200),
  assetPoint('2026-05-31', 22_100, 20_800, 1_300),
  assetPoint('2026-06-30', 23_750, 21_900, 1_850),
]

export const nvda = herdStock('NVDA', {
  companyName: 'NVIDIA',
  sector: 'Technology',
  herdScore: 78,
  herdStage: 'Herd Rush',
  signal: 'REDUCE',
  actionLabel: '과열 구간 관찰',
  actionScore: 71,
  monthlyRsi: 74.2,
  weeklyRsi: 71.4,
  position52w: 92.1,
  ma200Weekly: 86.3,
  ma200Deviation: 43.8,
  sectorMultiplier: 1.04,
  epsMultiplier: 0.95,
  signalDurationDays: 12,
  stageDurationDays: 18,
  actionReasons: ['장기 가격 확장', '주봉 모멘텀 상단'],
  actionWarnings: ['운영 비중은 아직 비활성화 상태입니다.'],
  oosValidationSummary: '가격 상태 관찰용 · 행동 증거 미채택',
})

export const nvdaObservation = observation('NVDA', 78, {
  companyName: 'NVIDIA',
  sector: 'Technology',
  scope: 'EQUITY',
  sectorEtf: 'XLK',
  transition: 'EXTENDING',
})

export const history = Array.from({ length: 18 }, (_, index) => ({
  date: `2026-${String(index < 6 ? 5 : index < 14 ? 6 : 7).padStart(2, '0')}-${String((index * 3) % 27 + 1).padStart(2, '0')}`,
  score: 48 + Math.round(index * 1.65),
}))

export const observationHistory = history.map((point) => ({
  observationDate: point.date,
  lastObservedSession: point.date,
  stateScore: point.score,
  stage: point.score >= 75 ? 'RUSH' : point.score >= 60 ? 'DRIFT' : 'CALM',
  transition: 'NEUTRAL',
  transitionEvent: false,
})).reverse()

export const journal = [
  {
    id: 1,
    ticker: 'NVDA',
    actionType: 'HOLD',
    actionLabel: '보유',
    herdScore: 74,
    signalLabel: '과열 관찰',
    recordedAt: '2026-07-21T03:20:00',
    memo: '다음 실적 발표 전까지 관찰',
  },
]

export const dataStatus = {
  status: 'FRESH',
  latestPriceDate: scoreDate,
  latestScoreDate: scoreDate,
  latestRun: {
    startedAt: '2026-07-24T00:45:00',
    finishedAt: '2026-07-24T00:52:00',
    successCount: 55,
    totalCount: 55,
    failedCount: 0,
    failedTickers: [],
  },
}

export const financials = {
  marketCap: 4_430_000_000_000,
  trailingPe: 37.8,
  eps: 4.89,
  operatingMargin: 61.4,
  totalRevenue: 165_200_000_000,
}

export const reliability = {
  fitScore: 73,
  reliabilityGrade: 'GOOD',
  reliabilityLabel: '참고 가능',
  fleeHitRate: 61,
  rushHitRate: 58,
  buySignalEdge: 3.8,
  sellSignalEdge: 2.6,
  buySignalEdgeLabel: 'NEUTRAL',
  sellSignalEdgeLabel: 'NEUTRAL',
  sampleQuality: 'MEDIUM',
  totalSignalSamples: 34,
  annualActions: 4.2,
}

function herdStock(ticker, overrides = {}) {
  return {
    ticker,
    companyName: ticker,
    sector: 'Technology',
    herdScore: 50,
    herdV4: overrides.herdScore ?? 50,
    herdStage: 'Herd Calm',
    signal: 'HOLD',
    scoreDate,
    qualityLevel: 'HIGH',
    qualityScore: 94,
    actionGrade: 'WATCH',
    actionLabel: '관찰',
    actionScore: 50,
    actionRatio: 0,
    actionModelVersion: 'HERD_v6.1',
    actionModelStatus: 'RESEARCH_VALIDATION',
    actionRegimeLabel: '장기 상태 관찰',
    signalDurationDays: 9,
    stageDurationDays: 16,
    monthlyRsi: 54,
    weeklyRsi: 57,
    position52w: 62,
    ma200Weekly: 64,
    ma200Deviation: 18,
    sectorMultiplier: 1,
    epsMultiplier: 1,
    ...overrides,
    herdV4: overrides.herdScore ?? overrides.herdV4 ?? 50,
  }
}

function observation(ticker, stateScore, overrides = {}) {
  return {
    availabilityStatus: 'AVAILABLE',
    freshnessStatus: 'FRESH',
    businessSessionsOld: 0,
    ticker,
    scope: 'EQUITY',
    schemaVersion: 'HERD_OBSERVATION_S1_SERVICE_V1',
    stateModelVersion: 'HERD_STATE_S1',
    transitionModelVersion: 'HERD_TRANSITION_S1',
    observationDate: scoreDate,
    lastObservedSession: scoreDate,
    generatedAt: '2026-07-24T00:52:00Z',
    stateScore,
    stage: stateScore >= 75 ? 'RUSH' : stateScore >= 60 ? 'DRIFT' : 'CALM',
    transition: 'NEUTRAL',
    rawTransition: 'NEUTRAL',
    transitionEvent: false,
    delta4w: 4.3,
    delta13w: 8.1,
    families: {
      priceExtension: Math.min(100, stateScore + 8),
      trendPosition: Math.min(100, stateScore + 4),
      relativePosition: Math.max(0, stateScore - 2),
      participation: Math.max(0, stateScore - 10),
    },
    downsideRiskContext: 32,
    sectorEtf: 'SPY',
    directionPrediction: false,
    operationalAction: 'HOLD',
    operationalActionRatio: 0,
    survivorshipSafe: false,
    ...overrides,
  }
}

function priceRow(ticker, currentPrice, marketValue, returnPct, dailyChangePct) {
  return {
    ticker,
    current_price: currentPrice,
    market_value: marketValue,
    return_pct: returnPct,
    daily_change_pct: dailyChangePct,
  }
}

function assetPoint(date, totalAssetValue, investedValue, cashBalance) {
  return {
    date,
    totalAssetValue,
    investedValue,
    cashBalance,
    totalValue: totalAssetValue,
  }
}

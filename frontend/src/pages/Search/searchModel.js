import { qualityReasonText, shouldShowQuality } from '../../utils/dataQuality'
import { normalizeStage } from '../../utils/herdStage'

export const STOCK_CANDIDATES = [
  { ticker: 'NVDA', name: 'NVIDIA Corporation', sector: 'Semiconductors' },
  { ticker: 'AAPL', name: 'Apple Inc.', sector: 'Consumer Technology' },
  { ticker: 'MSFT', name: 'Microsoft Corporation', sector: 'Software' },
  { ticker: 'META', name: 'Meta Platforms', sector: 'Communication Services' },
  { ticker: 'TSLA', name: 'Tesla, Inc.', sector: 'EV / Auto' },
  { ticker: 'GOOGL', name: 'Alphabet Inc.', sector: 'Communication Services' },
  { ticker: 'AMZN', name: 'Amazon.com, Inc.', sector: 'Consumer Discretionary' },
  { ticker: 'PLTR', name: 'Palantir Technologies', sector: 'Software' },
  { ticker: 'IONQ', name: 'IonQ, Inc.', sector: 'Quantum Computing' },
  { ticker: 'SNDK', name: 'Sandisk Corporation', sector: 'Semiconductors / Storage' },
  { ticker: 'BITX', name: '2x Bitcoin Strategy ETF', sector: 'Crypto ETF' },
  { ticker: 'SPY', name: 'S&P 500 ETF', sector: 'Benchmark ETF' },
  { ticker: 'QQQ', name: 'Nasdaq 100 ETF', sector: 'Benchmark ETF' },
]

export const TICKER_META =
  Object.fromEntries(STOCK_CANDIDATES.map((item) => [item.ticker, item]))
export const TICKER_NAMES =
  Object.fromEntries(STOCK_CANDIDATES.map((item) => [item.ticker, item.name]))

const RECENT_KEY = 'hs_recent_searches'

export function isTickerLike(value) {
  return /^[A-Z0-9.-]{1,10}$/.test(value)
}

export function toSearchCandidate(item) {
  return {
    ticker: item.ticker,
    name: item.name ?? item.ticker,
    sector: item.type ?? '미국 주식',
  }
}

export function candidateForTicker(ticker, matches = []) {
  return matches.find((item) => item.ticker === ticker) ?? TICKER_META[ticker] ?? {
    ticker,
    name: ticker,
    sector: '미국 주식',
  }
}

export function candidateMatches(item, normalized) {
  return item.ticker.includes(normalized) ||
    item.name.toUpperCase().includes(normalized)
}

export function stageDisplay(stage) {
  if (!stage) return 'Herd Calm'
  return stage.startsWith('Herd ') ? stage : `Herd ${stage}`
}

export function herdReadiness(data) {
  if (!data) {
    return { label: '계산 필요', tone: 'Pending', desc: 'HERD 계산 대기' }
  }
  if (shouldShowQuality(data)) {
    return {
      label: '데이터 부족',
      tone: 'Limited',
      desc: qualityReasonText(data),
    }
  }
  return {
    label: 'HERD 준비됨',
    tone: 'Ready',
    desc: data.scoreDate ?? '최신 점수',
  }
}

export function inclusionDecision(data) {
  if (!data) {
    return { label: '계산 대기', desc: 'HERD 계산 후 편입 가능', tone: 'Pending' }
  }
  if (herdReadiness(data).tone === 'Limited') {
    return { label: '보류', desc: '데이터 품질 확인 필요', tone: 'Limited' }
  }
  switch (normalizeStage(data.herdStage)) {
    case 'flee':
    case 'scatter':
      return { label: '이탈 관찰', desc: '기업 상태와 추세 확인 필요', tone: 'Ready' }
    case 'drift':
    case 'rush':
      return { label: '밀집 관찰', desc: '상태 변화 확인 필요', tone: 'Limited' }
    default:
      return { label: '관찰', desc: '보유/대기 판단 가능', tone: 'Neutral' }
  }
}

export function loadRecentSearches() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
  } catch {
    return []
  }
}

export function saveRecentSearch(ticker) {
  const list = loadRecentSearches().filter((savedTicker) => savedTicker !== ticker)
  list.unshift(ticker)
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 5)))
}

export function addButtonLabel(status, idleLabel) {
  if (status === 'loading') return '…'
  if (status === 'added') return '추가됨 ✓'
  if (status === 'exists') return '이미 추가됨'
  return idleLabel
}

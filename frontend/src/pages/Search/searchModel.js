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

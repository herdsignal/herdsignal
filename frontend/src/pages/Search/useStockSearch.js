import { useEffect, useState } from 'react'
import { getHerdObservation, searchStocks } from '../../api/herdApi'
import { observationToTrackedItem } from '../../utils/herdObservation'
import {
  STOCK_CANDIDATES,
  candidateForTicker,
  candidateMatches,
  isTickerLike,
  loadRecentSearches,
  saveRecentSearch,
  toSearchCandidate,
} from './searchModel'

export function localSearchCandidates(query) {
  const normalized = query.trim().toUpperCase()
  return normalized.length < 2
    ? []
    : STOCK_CANDIDATES.filter((item) => candidateMatches(item, normalized))
}

export function useStockSearch(query) {
  const [searchResult, setSearchResult] = useState(null)
  const [recentSearches, setRecentSearches] = useState(loadRecentSearches)

  useEffect(() => {
    const rawQuery = query.trim()
    if (rawQuery.length < 2) {
      setSearchResult(null)
      return undefined
    }

    const normalized = rawQuery.toUpperCase()
    const localMatches = localSearchCandidates(rawQuery)
    setSearchResult({ status: 'loading', matches: localMatches })
    let cancelled = false

    const timer = setTimeout(async () => {
      let candidates = localMatches
      try {
        const searchResponse = await searchStocks(rawQuery)
        const apiResults = searchResponse.data?.data?.results ?? []
        if (Array.isArray(apiResults) && apiResults.length > 0) {
          candidates = apiResults.map(toSearchCandidate)
        }
      } catch {
        // 검색 API가 실패해도 로컬 종목 사전과 정확한 티커 입력은 계속 지원한다.
      }

      const exact = candidates.find((item) => item.ticker === normalized)
      const ticker = exact?.ticker
        ?? candidates[0]?.ticker
        ?? (isTickerLike(normalized) ? normalized : null)
      if (!ticker) {
        if (!cancelled) setSearchResult({ status: 'not_found', matches: candidates })
        return
      }

      try {
        const response = await getHerdObservation(ticker)
        if (cancelled) return
        const observation = response.data?.data
        if (observation?.availabilityStatus === 'AVAILABLE') {
          const data = observationToTrackedItem(observation)
          setSearchResult({ status: 'found', data, matches: candidates })
          saveRecentSearch(ticker)
          setRecentSearches(loadRecentSearches())
          return
        }
      } catch {
        // 종목은 존재하지만 S1 관찰값이 아직 계산되지 않은 상태로 표시한다.
      }

      if (!cancelled) {
        setSearchResult({
          status: 'symbol_found',
          candidate: candidateForTicker(ticker, candidates),
          matches: candidates,
        })
      }
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query])

  return { searchResult, recentSearches }
}

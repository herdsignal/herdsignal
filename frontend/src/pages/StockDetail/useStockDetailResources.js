import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getPortfolio,
  getPortfolioSummary,
  getStockFinancials,
  getStockHerd,
  getStockHerdHistory,
  getStockHerdReliability,
} from '../../api/herdApi'
import { API_HOST } from './stockDetailModel'

export function useStockDetailResources(normalizedTicker, displayTicker) {
  const [herdData, setHerdData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [herdHistory, setHerdHistory] = useState([])
  const [historyPeriod, setHistoryPeriod] = useState('1y')
  const [historyLoading, setHistoryLoading] = useState(false)
  const [reliability, setReliability] = useState(null)
  const [reliabilityLoading, setReliabilityLoading] = useState(false)
  const [financials, setFinancials] = useState(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)
  const [portfolio, setPortfolio] = useState([])
  const [portfolioSummary, setPortfolioSummary] = useState(null)
  const herdRequest = useRef(0)

  useEffect(() => {
    setHerdData(null)
    setError(null)
  }, [normalizedTicker])

  const fetchData = useCallback(async () => {
    const requestId = ++herdRequest.current
    setLoading(true)
    setError(null)
    try {
      const response = await getStockHerd(normalizedTicker)
      const data = response.data?.data
      if (requestId !== herdRequest.current) return
      if (data) {
        setHerdData(data)
      } else {
        setError(
          `${displayTicker} 종목의 HERD 데이터가 없습니다.\nPython 스케줄러를 먼저 실행해주세요.`,
        )
      }
    } catch {
      if (requestId === herdRequest.current) {
        setError(`백엔드 서버에 연결할 수 없습니다.\n${API_HOST}이 실행 중인지 확인해주세요.`)
      }
    } finally {
      if (requestId === herdRequest.current) setLoading(false)
    }
  }, [displayTicker, normalizedTicker])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    let active = true
    Promise.allSettled([getPortfolio(), getPortfolioSummary()])
      .then(([portfolioResult, summaryResult]) => {
        if (!active) return
        if (portfolioResult.status === 'fulfilled') {
          const data = portfolioResult.value.data?.data
          setPortfolio(Array.isArray(data) ? data : [])
        }
        if (summaryResult.status === 'fulfilled') {
          setPortfolioSummary(summaryResult.value.data?.data ?? null)
        }
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    setHistoryLoading(true)
    setHerdHistory([])
    getStockHerdHistory(normalizedTicker, historyPeriod)
      .then((response) => {
        if (active) setHerdHistory(response.data?.data?.points ?? [])
      })
      .catch(() => {
        if (active) setHerdHistory([])
      })
      .finally(() => {
        if (active) setHistoryLoading(false)
      })
    return () => {
      active = false
    }
  }, [historyPeriod, normalizedTicker])

  useEffect(() => {
    let active = true
    setReliabilityLoading(true)
    setReliability(null)
    getStockHerdReliability(normalizedTicker, 3)
      .then((response) => {
        if (active) setReliability(response.data?.data ?? null)
      })
      .catch(() => {
        if (active) setReliability(null)
      })
      .finally(() => {
        if (active) setReliabilityLoading(false)
      })
    return () => {
      active = false
    }
  }, [normalizedTicker])

  useEffect(() => {
    let active = true
    setFinancialsLoading(true)
    setFinancials(null)
    getStockFinancials(normalizedTicker)
      .then((response) => {
        if (active) setFinancials(response.data?.data ?? null)
      })
      .catch(() => {
        if (active) setFinancials(null)
      })
      .finally(() => {
        if (active) setFinancialsLoading(false)
      })
    return () => {
      active = false
    }
  }, [normalizedTicker])

  return {
    herdData,
    loading,
    error,
    herdHistory,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    reliability,
    reliabilityLoading,
    financials,
    financialsLoading,
    portfolio,
    portfolioSummary,
    fetchData,
  }
}

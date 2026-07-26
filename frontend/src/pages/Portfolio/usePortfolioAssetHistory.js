import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getPortfolioHistory } from '../../api/herdApi'
import {
  ASSET_HISTORY_PERIODS,
  currentAssetPoint,
  fmtAxisDate,
  mergeCurrentAssetPoint,
  normalizeHistoryPoint,
} from './portfolioHistoryModel'

/**
 * 자산 히스토리 패널의 요청 상태와 차트 파생값을 캡슐화한다.
 */
export function usePortfolioAssetHistory(
  summary,
  cashBalance,
  { initiallyOpen = false } = {},
) {
  const [assetPanelOpen, setAssetPanelOpen] = useState(initiallyOpen)
  const [assetHistoryPeriod, setAssetHistoryPeriod] = useState('year')
  const [assetHistory, setAssetHistory] = useState([])
  const [assetHistoryLoading, setAssetHistoryLoading] = useState(false)
  const [assetHistoryError, setAssetHistoryError] = useState(null)
  const requestSequence = useRef(0)

  const fetchAssetHistory = useCallback(async () => {
    const requestId = ++requestSequence.current
    setAssetHistoryLoading(true)
    setAssetHistoryError(null)
    try {
      const response = await getPortfolioHistory(assetHistoryPeriod)
      const points = (response.data?.data?.points ?? []).map(normalizeHistoryPoint)
      if (requestId === requestSequence.current) setAssetHistory(points)
    } catch {
      if (requestId === requestSequence.current) {
        setAssetHistoryError('자산 히스토리를 불러올 수 없습니다.')
      }
    } finally {
      if (requestId === requestSequence.current) setAssetHistoryLoading(false)
    }
  }, [assetHistoryPeriod])

  useEffect(() => {
    if (assetPanelOpen) fetchAssetHistory()
  }, [assetPanelOpen, fetchAssetHistory])

  const metrics = useMemo(
    () => buildAssetHistoryMetrics(assetHistory, summary, cashBalance, assetHistoryPeriod),
    [assetHistory, summary, cashBalance, assetHistoryPeriod]
  )

  return {
    assetPanelOpen,
    setAssetPanelOpen,
    assetHistoryPeriod,
    setAssetHistoryPeriod,
    assetHistoryLoading,
    assetHistoryError,
    fetchAssetHistory,
    ...metrics,
  }
}

export function buildAssetHistoryMetrics(
  assetHistory,
  summary,
  cashBalance,
  period
) {
  const assetChartHistory = mergeCurrentAssetPoint(
    assetHistory,
    currentAssetPoint(summary, cashBalance)
  )
  const assetLatest = assetChartHistory.at(-1) ?? null
  const assetFirst = assetChartHistory[0] ?? null
  const assetStartValue = assetFirst?.totalAssetValue ?? null
  const investedStartValue = assetFirst?.investedValue ?? null
  const assetPeak = assetChartHistory.reduce((best, point) => (
    !best || Number(point.totalAssetValue) > Number(best.totalAssetValue)
      ? point
      : best
  ), null)

  const accountValueChangePct = ratioChange(assetLatest?.totalAssetValue, assetStartValue)
  const stockValueChangePct = ratioChange(assetLatest?.investedValue, investedStartValue)
  const accountValueDrawdownPct = ratioChange(
    assetLatest?.totalAssetValue,
    assetPeak?.totalAssetValue,
  )
  const assetValues = assetChartHistory
    .flatMap((point) => [Number(point.totalAssetValue), Number(point.investedValue)])
    .filter(Number.isFinite)
  if (assetStartValue) assetValues.push(assetStartValue)
  const assetMin = assetValues.length > 0 ? Math.min(...assetValues) : 0
  const assetMax = assetValues.length > 0 ? Math.max(...assetValues) : 1000
  const assetPadding = (assetMax - assetMin) * 0.08 || 100

  return {
    assetChartHistory,
    assetLatest,
    assetFirst,
    assetStartValue,
    accountValueChangePct,
    stockValueChangePct,
    accountValueDrawdownPct,
    assetYDomain: [Math.max(0, assetMin - assetPadding), assetMax + assetPadding],
    assetPeriodLabel:
      ASSET_HISTORY_PERIODS.find((item) => item.value === period)?.label ?? '선택 기간',
    assetStartLabel: assetFirst?.date ? fmtAxisDate(assetFirst.date) : '—',
  }
}

function ratioChange(current, base) {
  return current && base ? (current / base - 1) * 100 : null
}

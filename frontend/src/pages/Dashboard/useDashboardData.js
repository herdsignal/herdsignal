import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { useDashboardAssetHistory } from './useDashboardAssetHistory'
import { useDashboardMarketData } from './useDashboardMarketData'
import { useDashboardPortfolioData } from './useDashboardPortfolioData'
import { useDashboardPortfolioMutations } from './useDashboardPortfolioMutations'
import { useDashboardPreferences } from './useDashboardPreferences'
import { useDashboardSupportingData } from './useDashboardSupportingData'
import { usePortfolioViewModel } from './usePortfolioViewModel'
import { useTargetWeightEditor } from './useTargetWeightEditor'

export function useDashboardData() {
  const { user } = useAuth()
  const userId = user?.id
  const [modalTicker, setModalTicker] = useState(null)
  const [editMode, setEditMode] = useState(false)
  const refreshNoticeSetter = useRef(() => {})
  const market = useDashboardMarketData()
  const supportingData = useDashboardSupportingData()
  const {
    dataStatus,
    dataStatusError,
    fetchDataStatus,
    signalJournalSummary,
    recentSignalLogs,
  } = supportingData
  const handleTargetWeightError = useCallback((ticker) => {
    refreshNoticeSetter.current(`${ticker} 목표 비중 저장에 실패했습니다.`)
  }, [])
  const {
    targetWeights,
    setTargetWeights,
    handleTargetWeightChange,
  } = useTargetWeightEditor(handleTargetWeightError)
  const portfolioData = useDashboardPortfolioData({
    userId,
    setTargetWeights,
    updateSpyData: market.updateSpyData,
    fetchDataStatus,
  })
  const {
    portfolio,
    setPortfolio,
    summary,
    setSummary,
    herdMap,
    loading,
    error,
    refreshing,
    refreshNotice,
    setRefreshNotice,
    lastUpdated,
    cashBalance,
    setCashBalance,
    cashDraft,
    setCashDraft,
    fetchData,
    handleRefresh,
  } = portfolioData
  useEffect(() => {
    refreshNoticeSetter.current = setRefreshNotice
  }, [setRefreshNotice])
  const assetHistory = useDashboardAssetHistory(summary, cashBalance)
  const preferences = useDashboardPreferences(market.exchangeRate)
  const priceMap = useMemo(() => Object.fromEntries(
    (summary?.stocks ?? []).map((stock) => [stock.ticker, stock]),
  ), [summary])
  const mutations = useDashboardPortfolioMutations({
    userId,
    portfolio,
    setPortfolio,
    setSummary,
    priceMap,
    cashBalance,
    setCashBalance,
    cashDraft,
    setCashDraft,
    setTargetWeights,
    modalTicker,
    setModalTicker,
    fetchData,
    assetPanelOpen: assetHistory.assetPanelOpen,
    fetchAssetHistory: assetHistory.fetchAssetHistory,
    setRefreshNotice,
  })
  const viewModel = usePortfolioViewModel({
    portfolio,
    summary,
    herdMap,
    targetWeights,
    portfolioSort: preferences.portfolioSort,
    priceMap,
  })
  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })

  return {
    portfolio,
    summary,
    herdMap,
    dataStatus,
    dataStatusError,
    ...market,
    loading,
    error,
    modalTicker,
    setModalTicker,
    deletingTicker: mutations.deletingTicker,
    refreshing,
    refreshNotice,
    lastUpdated,
    currencyMode: preferences.currencyMode,
    editMode,
    setEditMode,
    portfolioSort: preferences.portfolioSort,
    targetWeights,
    cashBalance,
    cashDraft,
    setCashDraft,
    cashSaving: mutations.cashSaving,
    assetPanelOpen: assetHistory.assetPanelOpen,
    setAssetPanelOpen: assetHistory.setAssetPanelOpen,
    assetHistoryPeriod: assetHistory.assetHistoryPeriod,
    setAssetHistoryPeriod: assetHistory.setAssetHistoryPeriod,
    assetHistoryLoading: assetHistory.assetHistoryLoading,
    assetHistoryError: assetHistory.assetHistoryError,
    today,
    fetchData,
    priceMap,
    handleCurrencyToggle: preferences.handleCurrencyToggle,
    displayAmount: preferences.displayAmount,
    displayPnl: preferences.displayPnl,
    handleRefresh,
    handleCashSave: mutations.handleCashSave,
    handleDelete: mutations.handleDelete,
    handlePortfolioSortChange: preferences.handlePortfolioSortChange,
    signalJournalSummary,
    recentSignalLogs,
    handleModalSaved: mutations.handleModalSaved,
    modalStock: mutations.modalStock,
    ...viewModel,
    assetChartHistory: assetHistory.assetChartHistory,
    assetLatest: assetHistory.assetLatest,
    assetFirst: assetHistory.assetFirst,
    assetStartValue: assetHistory.assetStartValue,
    totalFlowPct: assetHistory.totalFlowPct,
    investedChangePct: assetHistory.investedChangePct,
    assetDrawdownPct: assetHistory.assetDrawdownPct,
    assetYDomain: assetHistory.assetYDomain,
    assetPeriodLabel: assetHistory.assetPeriodLabel,
    assetStartLabel: assetHistory.assetStartLabel,
    handleTargetWeightChange,
  }
}

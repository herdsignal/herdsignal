import { useCallback, useState } from 'react'
import {
  removeFromPortfolio,
  updateCashBalance,
} from '../../api/herdApi'
import {
  CACHE_KEY_REALTIME,
  clearPortfolioCaches,
  writeUserCache,
} from './dashboardModel'

export function useDashboardPortfolioMutations({
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
  assetPanelOpen,
  fetchAssetHistory,
  setRefreshNotice,
}) {
  const [deletingTicker, setDeletingTicker] = useState(null)
  const [cashSaving, setCashSaving] = useState(false)

  const handleCashSave = useCallback(async () => {
    const amount = Number(cashDraft || 0)
    if (!Number.isFinite(amount) || amount < 0 || cashSaving) return

    setCashSaving(true)
    try {
      const response = await updateCashBalance(amount)
      const saved = Number(response.data?.data?.cashAmount ?? amount)
      setCashBalance(saved)
      setCashDraft(saved > 0 ? String(saved) : '')
      setSummary((previous) => {
        if (!previous) return previous
        const investedValue = Number(previous.invested_value ?? previous.total_value ?? 0)
        const next = {
          ...previous,
          cash_balance: saved,
          total_value: investedValue + saved,
          total_asset_value: investedValue + saved,
        }
        writeUserCache(CACHE_KEY_REALTIME, userId, next)
        return next
      })
      if (assetPanelOpen) fetchAssetHistory()
      setRefreshNotice('현금 보유액을 저장했습니다.')
    } catch {
      setRefreshNotice('현금 보유액 저장에 실패했습니다. 입력값과 서버 상태를 확인해주세요.')
    } finally {
      setCashSaving(false)
    }
  }, [
    assetPanelOpen,
    cashDraft,
    cashSaving,
    fetchAssetHistory,
    setCashBalance,
    setCashDraft,
    setRefreshNotice,
    setSummary,
    userId,
  ])

  const handleDelete = useCallback(async (event, ticker) => {
    event.stopPropagation()
    if (deletingTicker) return
    setDeletingTicker(ticker)
    try {
      await removeFromPortfolio(ticker)
      setPortfolio((previous) => previous.filter((item) => item.ticker !== ticker))
      setTargetWeights((previous) => {
        const next = { ...previous }
        delete next[ticker]
        return next
      })
      clearPortfolioCaches(userId)
      await fetchData()
    } catch {
      setRefreshNotice(`${ticker} 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.`)
    } finally {
      setDeletingTicker(null)
    }
  }, [
    deletingTicker,
    fetchData,
    setPortfolio,
    setRefreshNotice,
    setTargetWeights,
    userId,
  ])

  const handleModalSaved = useCallback((newAvgPrice, newQuantity) => {
    const ticker = modalTicker
    setPortfolio((previous) => previous.map((item) => (
      item.ticker === ticker
        ? { ...item, avgPrice: newAvgPrice, quantity: newQuantity }
        : item
    )))

    const currentPrice = priceMap[ticker]?.current_price
    if (currentPrice == null) {
      fetchData()
      setModalTicker(null)
      return
    }

    const newMarketValue = currentPrice * newQuantity
    const newReturnPct = (currentPrice - newAvgPrice) / newAvgPrice * 100
    setSummary((previous) => {
      if (!previous) return previous
      const updatedStocks = (previous.stocks ?? []).map((stock) => (
        stock.ticker === ticker
          ? { ...stock, market_value: newMarketValue, return_pct: newReturnPct }
          : stock
      ))
      const oldMarketValue = priceMap[ticker]?.market_value ?? 0
      const investedValue = (
        (previous.invested_value ?? previous.total_value ?? 0)
        - oldMarketValue
        + newMarketValue
      )
      const cash = Number(previous.cash_balance ?? cashBalance ?? 0)
      const oldStock = portfolio.find((item) => item.ticker === ticker)
      const oldCost = (oldStock?.avgPrice ?? 0) * (oldStock?.quantity ?? 0)
      const totalCost = (previous.total_cost ?? 0) - oldCost + newAvgPrice * newQuantity
      const totalReturnPct = totalCost > 0
        ? (investedValue - totalCost) / totalCost * 100
        : 0
      const next = {
        ...previous,
        stocks: updatedStocks,
        invested_value: investedValue,
        total_value: investedValue + cash,
        total_asset_value: investedValue + cash,
        total_cost: totalCost,
        total_return_pct: totalReturnPct,
      }
      writeUserCache(CACHE_KEY_REALTIME, userId, next)
      return next
    })
    setModalTicker(null)
  }, [
    cashBalance,
    fetchData,
    modalTicker,
    portfolio,
    priceMap,
    setModalTicker,
    setPortfolio,
    setSummary,
    userId,
  ])

  const modalStock = portfolio.find((item) => item.ticker === modalTicker)

  return {
    deletingTicker,
    cashSaving,
    handleCashSave,
    handleDelete,
    handleModalSaved,
    modalStock,
  }
}

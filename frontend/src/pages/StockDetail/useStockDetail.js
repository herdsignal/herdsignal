import { useEffect, useMemo, useState } from 'react'
import { addToPortfolio, addToWatchlist } from '../../api/herdApi'
import { useAuth } from '../../auth/AuthContext'
import { clearPortfolioCaches } from '../../features/portfolio/portfolioCache'
import { getHerdMomentum } from '../../utils/herdMomentum'
import {
  isObservationAvailable,
  observationScore,
  observationStage,
} from '../../utils/herdObservation'
import { summarizeSignalJournal } from '../../utils/signalJournal'
import { evaluateFundamentalGuard } from './stockFundamentalModel'
import { journalActionLabel, stageColor } from './stockDetailModel'
import { useStockDetailResources } from './useStockDetailResources'
import { useStockSignalJournal } from './useStockSignalJournal'

export function useStockDetail(ticker) {
  const { user } = useAuth()
  const normalizedTicker = ticker.toUpperCase()
  const [portfolioStatus, setPortfolioStatus] = useState('idle')
  const [watchlistStatus, setWatchlistStatus] = useState('idle')
  const resources = useStockDetailResources(normalizedTicker, ticker)
  const journal = useStockSignalJournal(normalizedTicker)
  const {
    observation,
    loading,
    error,
    herdHistory,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    financials,
    financialsLoading,
    fetchData,
  } = resources

  useEffect(() => {
    setPortfolioStatus('idle')
    setWatchlistStatus('idle')
  }, [normalizedTicker])

  async function handleAddPortfolio() {
    if (portfolioStatus !== 'idle') return
    setPortfolioStatus('loading')
    journal.setActionError(null)
    try {
      await addToPortfolio(normalizedTicker)
      clearPortfolioCaches(user?.id)
      setPortfolioStatus('added')
    } catch (errorResponse) {
      if (errorResponse.response?.status === 409) {
        setPortfolioStatus('exists')
      } else {
        setPortfolioStatus('idle')
        journal.setActionError('포트폴리오에 추가하지 못했습니다. 잠시 후 다시 시도해주세요.')
      }
    }
  }

  async function handleAddWatchlist() {
    if (watchlistStatus !== 'idle') return
    setWatchlistStatus('loading')
    journal.setActionError(null)
    try {
      await addToWatchlist(normalizedTicker)
      setWatchlistStatus('added')
    } catch (errorResponse) {
      if (errorResponse.response?.status === 409) {
        setWatchlistStatus('exists')
      } else {
        setWatchlistStatus('idle')
        journal.setActionError('관심종목에 추가하지 못했습니다. 잠시 후 다시 시도해주세요.')
      }
    }
  }

  const observationAvailable = isObservationAvailable(observation)
  const herdScore = observationScore(observation)
  const herdStage = observationStage(observation)
  const stageDisp = herdStage ? `Herd ${herdStage}` : null
  const color = stageColor(herdStage)
  const fundamentalGuard = useMemo(
    () => evaluateFundamentalGuard(financials, null),
    [financials],
  )
  const journalSummary = useMemo(
    () => summarizeSignalJournal(journal.signalLogs),
    [journal.signalLogs],
  )
  const historyPoints = useMemo(() => {
    if (herdHistory.length > 0) return herdHistory
    if (!observationAvailable || !observation?.observationDate) return []
    return [{ date: observation.observationDate, score: herdScore }]
  }, [herdHistory, herdScore, observation, observationAvailable])
  const herdMomentum = useMemo(
    () => getHerdMomentum(historyPoints, herdScore, herdStage),
    [herdScore, herdStage, historyPoints],
  )

  async function handleJournalAction(actionType, details = {}) {
    await journal.saveSignalLog({
      ticker: normalizedTicker,
      actionType,
      actionLabel: journalActionLabel(actionType),
      scoreDate: observation?.observationDate,
      herdScore: Math.round(herdScore),
      herdStage: stageDisp,
      signal: 'HOLD',
      signalLabel: 'State S1 관찰',
      actionRatio: 0,
      signalDurationDays: null,
      stageDurationDays: null,
      price: details.price,
      quantity: details.quantity,
      amount: details.amount,
      profitPct: details.profitPct,
      memo: details.memo,
    })
  }

  return {
    observation,
    observationAvailable,
    loading,
    error,
    portfolioStatus,
    watchlistStatus,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    financials,
    financialsLoading,
    signalLogs: journal.signalLogs,
    journalAction: journal.journalAction,
    setJournalAction: journal.setJournalAction,
    actionError: journal.actionError,
    normalizedTicker,
    fetchData,
    handleAddPortfolio,
    handleAddWatchlist,
    herdScore,
    herdStage,
    stageDisp,
    color,
    fundamentalGuard,
    journalSummary,
    historyPoints,
    herdMomentum,
    handleJournalAction,
    handleJournalDelete: journal.removeSignalLog,
  }
}

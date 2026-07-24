import { useEffect, useMemo, useState } from 'react'
import { addToPortfolio, addToWatchlist } from '../../api/herdApi'
import { useAuth } from '../../auth/AuthContext'
import { clearPortfolioCaches } from '../../features/portfolio/portfolioCache'
import { qualityColor } from '../../utils/dataQuality'
import { buildDecision } from '../../utils/decision'
import { getHerdMomentum } from '../../utils/herdMomentum'
import { summarizeSignalJournal } from '../../utils/signalJournal'
import { evaluateFundamentalGuard } from './stockFundamentalModel'
import {
  buildSignalEvidence,
  journalActionLabel,
  signalStyle,
  stageColor,
} from './stockDetailModel'
import {
  actionTone,
  currentSignalReliability,
  reliabilityEvidenceItems,
} from './stockReliabilityModel'
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

  const herdScore = herdData?.herdV4 ?? herdData?.herdScore ?? 50
  const herdStage = herdData?.herdStage ?? 'Calm'
  const stageDisp = herdStage.startsWith('Herd ') ? herdStage : `Herd ${herdStage}`
  const color = stageColor(herdStage)
  const sigStyle = signalStyle(herdData?.signal)
  const qualityToneColor = qualityColor(herdData?.qualityLevel)
  const actionColor = actionTone(herdData?.actionGrade, herdData?.signal)
  const holding = portfolio.find((item) => item.ticker === normalizedTicker) ?? null
  const decision = useMemo(() => buildDecision({
    herdData: { ...herdData, ticker: normalizedTicker },
    holding,
    summary: portfolioSummary,
  }), [herdData, holding, normalizedTicker, portfolioSummary])
  const currentReliability = useMemo(
    () => currentSignalReliability(herdData, reliability),
    [herdData, reliability],
  )
  const reliabilityEvidence = useMemo(
    () => reliabilityEvidenceItems(reliability),
    [reliability],
  )
  const fundamentalGuard = useMemo(
    () => evaluateFundamentalGuard(financials, herdData),
    [financials, herdData],
  )
  const signalEvidence = useMemo(
    () => buildSignalEvidence(herdData),
    [herdData],
  )
  const journalSummary = useMemo(
    () => summarizeSignalJournal(journal.signalLogs),
    [journal.signalLogs],
  )
  const historyPoints = useMemo(() => {
    if (herdHistory.length > 0) return herdHistory
    if (!herdData?.scoreDate) return []
    return [{ date: herdData.scoreDate, score: herdScore }]
  }, [herdData, herdHistory, herdScore])
  const herdMomentum = useMemo(
    () => getHerdMomentum(historyPoints, herdScore, herdStage),
    [herdScore, herdStage, historyPoints],
  )

  async function handleJournalAction(actionType, details = {}) {
    await journal.saveSignalLog({
      ticker: normalizedTicker,
      actionType,
      actionLabel: journalActionLabel(actionType),
      scoreDate: herdData.scoreDate,
      herdScore: Math.round(herdScore),
      herdStage: stageDisp,
      signal: herdData.signal,
      signalLabel: herdData.actionLabel ?? decision.title,
      actionRatio: herdData.actionRatio,
      signalDurationDays: herdData.signalDurationDays,
      stageDurationDays: herdData.stageDurationDays,
      price: details.price,
      quantity: details.quantity,
      amount: details.amount,
      profitPct: details.profitPct,
      memo: details.memo,
    })
  }

  return {
    herdData,
    loading,
    error,
    portfolioStatus,
    watchlistStatus,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    reliability,
    reliabilityLoading,
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
    sigStyle,
    qualityToneColor,
    actionColor,
    decision,
    currentReliability,
    reliabilityEvidence,
    fundamentalGuard,
    signalEvidence,
    journalSummary,
    historyPoints,
    herdMomentum,
    handleJournalAction,
    handleJournalDelete: journal.removeSignalLog,
  }
}

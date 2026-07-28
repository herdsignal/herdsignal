import { useMemo } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { useTickerMembership } from '../Search/useTickerMembership'
import {
  isObservationAvailable,
  observationScore,
  observationStage,
} from '../../utils/herdObservation'
import { summarizeSignalJournal } from '../../utils/signalJournal'
import { evaluateFundamentalGuard } from './stockFundamentalModel'
import {
  buildStockStateSummary,
  journalActionLabel,
  stageColor,
} from './stockDetailModel'
import { useStockDetailResources } from './useStockDetailResources'
import { useStockSignalJournal } from './useStockSignalJournal'
import { buildStockBrief } from './stockBriefModel'

export function useStockDetail(ticker) {
  const { user } = useAuth()
  const authenticated = Boolean(user?.authenticated)
  const normalizedTicker = String(ticker ?? '').trim().toUpperCase()
  const resources = useStockDetailResources(normalizedTicker, ticker)
  const journal = useStockSignalJournal(normalizedTicker, {
    enabled: authenticated,
  })
  const membership = useTickerMembership({
    selectedTicker: normalizedTicker,
    userId: user?.id,
    enabled: authenticated,
  })
  const {
    observation,
    loading,
    error,
    herdHistory,
    herdTimeline,
    timelineMeta,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    financials,
    financialsLoading,
    episodeStudy,
    episodeLoading,
    fetchData,
  } = resources

  const observationAvailable = isObservationAvailable(observation)
  const herdScore = observationScore(observation)
  const herdStage = observationStage(observation)
  const stageDisp = herdStage ? `Herd ${herdStage}` : null
  const color = stageColor(herdStage)
  const fundamentalGuard = useMemo(
    () => evaluateFundamentalGuard(financials),
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
  const timelinePoints = useMemo(() => {
    if (herdTimeline.length > 0) return herdTimeline
    if (!observationAvailable || !observation?.observationDate) return []
    return [{
      date: observation.observationDate,
      lastObservedSession: observation.lastObservedSession,
      score: herdScore,
      stage: herdStage,
      transition: observation.transition,
      transitionEvent: observation.transitionEvent,
    }]
  }, [
    herdScore,
    herdStage,
    herdTimeline,
    observation,
    observationAvailable,
  ])
  const stateSummary = useMemo(
    () => buildStockStateSummary({
      observation,
      currentScore: herdScore,
      currentStage: herdStage,
      timeline: timelinePoints,
    }),
    [herdScore, herdStage, observation, timelinePoints],
  )
  const briefItems = useMemo(
    () => buildStockBrief({
      observation,
      fundamentalGuard,
      episodeStudy,
    }),
    [episodeStudy, fundamentalGuard, observation],
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
      stageDurationDays: stateSummary.stageDurationDays,
      price: details.price,
      quantity: details.quantity,
      amount: details.amount,
      profitPct: details.profitPct,
      memo: details.memo,
    })
  }

  return {
    authenticated,
    observation,
    observationAvailable,
    loading,
    error,
    portfolioStatus: membership.portfolioStatus,
    watchlistStatus: membership.watchlistStatus,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    financials,
    financialsLoading,
    signalLogs: journal.signalLogs,
    journalAction: journal.journalAction,
    setJournalAction: journal.setJournalAction,
    actionError: membership.addError || journal.actionError,
    normalizedTicker,
    fetchData,
    handleAddPortfolio: () => membership.handleAddPortfolio(normalizedTicker),
    handleAddWatchlist: () => membership.handleAddWatchlist(normalizedTicker),
    herdScore,
    herdStage,
    stageDisp,
    color,
    fundamentalGuard,
    journalSummary,
    historyPoints,
    timelineMeta,
    episodeStudy,
    episodeLoading,
    briefItems,
    stateSummary,
    handleJournalAction,
    handleJournalDelete: journal.removeSignalLog,
  }
}

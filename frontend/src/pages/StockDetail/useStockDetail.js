import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  getStockHerd, addToPortfolio, addToWatchlist,
  getStockFinancials, getStockHerdHistory, getStockHerdReliability,
  getPortfolio, getPortfolioSummary,
  getSignalJournal, createSignalJournal, deleteSignalJournal,
} from '../../api/herdApi'
import { useAuth } from '../../auth/AuthContext'
import { clearPortfolioCaches } from '../Dashboard/dashboardModel'
import { buildDecision } from '../../utils/decision'
import { qualityColor } from '../../utils/dataQuality'
import { getHerdMomentum } from '../../utils/herdMomentum'
import { summarizeSignalJournal } from '../../utils/signalJournal'
import {
  API_HOST,
  actionTone,
  buildSignalEvidence,
  currentSignalReliability,
  evaluateFundamentalGuard,
  journalActionLabel,
  reliabilityEvidenceItems,
  signalStyle,
  stageColor,
} from './stockDetailModel'

export function useStockDetail(ticker) {

  const { user } = useAuth()

  /* 상태 */
  const [herdData,         setHerdData]         = useState(null)
  const [loading,          setLoading]           = useState(true)
  const [error,            setError]             = useState(null)
  const [portfolioStatus,  setPortfolioStatus]   = useState('idle')
  const [watchlistStatus,  setWatchlistStatus]   = useState('idle')
  const [herdHistory,      setHerdHistory]       = useState([])
  const [historyPeriod,    setHistoryPeriod]     = useState('1y')
  const [historyLoading,   setHistoryLoading]    = useState(false)
  const [reliability,      setReliability]       = useState(null)
  const [reliabilityLoading, setReliabilityLoading] = useState(false)
  const [financials,       setFinancials]        = useState(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)
  const [portfolio,        setPortfolio]         = useState([])
  const [portfolioSummary, setPortfolioSummary]  = useState(null)
  const [signalLogs,       setSignalLogs]        = useState([])
  const [journalAction,    setJournalAction]     = useState(null)
  const [actionError,      setActionError]       = useState(null)
  const herdRequest = useRef(0)
  const journalRequest = useRef(0)

  const normalizedTicker = ticker.toUpperCase()

  useEffect(() => {
    setHerdData(null)
    setError(null)
    setPortfolioStatus('idle')
    setWatchlistStatus('idle')
    setActionError(null)
    setJournalAction(null)
  }, [normalizedTicker])

  const fetchSignalLogs = useCallback(async () => {
    const requestId = ++journalRequest.current
    try {
      const res = await getSignalJournal(normalizedTicker)
      if (requestId === journalRequest.current) {
        setSignalLogs((res.data?.data ?? []).slice(0, 5))
      }
    } catch {
      if (requestId === journalRequest.current) setSignalLogs([])
    }
  }, [normalizedTicker])

  useEffect(() => { fetchSignalLogs() }, [fetchSignalLogs])

  /* HERD 데이터 조회 */
  const fetchData = useCallback(async () => {
    const requestId = ++herdRequest.current
    setLoading(true)
    setError(null)
    try {
      const res  = await getStockHerd(normalizedTicker)
      const data = res.data?.data
      if (requestId !== herdRequest.current) return
      if (data) {
        setHerdData(data)
      } else {
        setError(
          `${ticker} 종목의 HERD 데이터가 없습니다.\nPython 스케줄러를 먼저 실행해주세요.`
        )
      }
    } catch {
      if (requestId === herdRequest.current) {
        setError(`백엔드 서버에 연결할 수 없습니다.\n${API_HOST}이 실행 중인지 확인해주세요.`)
      }
    } finally {
      if (requestId === herdRequest.current) setLoading(false)
    }
  }, [normalizedTicker, ticker])

  useEffect(() => { fetchData() }, [fetchData])

  /* 포트폴리오 컨텍스트 — 장기투자 판단 패널용. 실패해도 상세 화면은 유지. */
  useEffect(() => {
    Promise.allSettled([getPortfolio(), getPortfolioSummary()])
      .then(([portfolioRes, summaryRes]) => {
        if (portfolioRes.status === 'fulfilled') {
          const data = portfolioRes.value.data?.data
          setPortfolio(Array.isArray(data) ? data : [])
        }
        if (summaryRes.status === 'fulfilled') {
          setPortfolioSummary(summaryRes.value.data?.data ?? null)
        }
      })
  }, [])

  /* HERD 히스토리 — ticker 또는 기간 변경 시 재조회 */
  useEffect(() => {
    let active = true
    setHistoryLoading(true)
    setHerdHistory([])
    getStockHerdHistory(normalizedTicker, historyPeriod)
      .then((res) => { if (active) setHerdHistory(res.data?.data?.points ?? []) })
      .catch(() => { if (active) setHerdHistory([]) })
      .finally(() => { if (active) setHistoryLoading(false) })
    return () => { active = false }
  }, [normalizedTicker, historyPeriod])

  /* HERD 신호 신뢰도 — 저장된 HERD 히스토리와 가격 데이터 기반 */
  useEffect(() => {
    let active = true
    setReliabilityLoading(true)
    setReliability(null)
    getStockHerdReliability(normalizedTicker, 3)
      .then((res) => { if (active) setReliability(res.data?.data ?? null) })
      .catch(() => { if (active) setReliability(null) })
      .finally(() => { if (active) setReliabilityLoading(false) })
    return () => { active = false }
  }, [normalizedTicker])

  /* Fundamental Guard — HERD 판단을 막을 재무 경고만 확인 */
  useEffect(() => {
    let active = true
    setFinancialsLoading(true)
    setFinancials(null)
    getStockFinancials(normalizedTicker)
      .then((res) => { if (active) setFinancials(res.data?.data ?? null) })
      .catch(() => { if (active) setFinancials(null) })
      .finally(() => { if (active) setFinancialsLoading(false) })
    return () => { active = false }
  }, [normalizedTicker])

  /* 포트폴리오 추가 */
  async function handleAddPortfolio() {
    if (portfolioStatus !== 'idle') return
    setPortfolioStatus('loading')
    setActionError(null)
    try {
      await addToPortfolio(normalizedTicker)
      clearPortfolioCaches(user?.id)
      setPortfolioStatus('added')
    } catch (e) {
      if (e.response?.status === 409) {
        setPortfolioStatus('exists')
      } else {
        setPortfolioStatus('idle')
        setActionError('포트폴리오에 추가하지 못했습니다. 잠시 후 다시 시도해주세요.')
      }
    }
  }

  /* 관심종목 추가 */
  async function handleAddWatchlist() {
    if (watchlistStatus !== 'idle') return
    setWatchlistStatus('loading')
    setActionError(null)
    try {
      await addToWatchlist(normalizedTicker)
      setWatchlistStatus('added')
    } catch (e) {
      if (e.response?.status === 409) {
        setWatchlistStatus('exists')
      } else {
        setWatchlistStatus('idle')
        setActionError('관심종목에 추가하지 못했습니다. 잠시 후 다시 시도해주세요.')
      }
    }
  }

  /* HERD 데이터에서 사용할 변수들 */
  const herdScore  = herdData?.herdV4 ?? herdData?.herdScore ?? 50
  const herdStage  = herdData?.herdStage ?? 'Calm'
  /* 표시용 stage 이름: "Herd Scatter" → "Herd Scatter" (이미 올바른 형태) */
  const stageDisp  = herdStage.startsWith('Herd ') ? herdStage : `Herd ${herdStage}`
  const color      = stageColor(herdStage)
  const sigStyle   = signalStyle(herdData?.signal)
  const qualityToneColor = qualityColor(herdData?.qualityLevel)
  const actionColor = actionTone(herdData?.actionGrade, herdData?.signal)
  const holding    = portfolio.find((item) => item.ticker === normalizedTicker) ?? null
  const decision   = useMemo(() => buildDecision({
    herdData: { ...herdData, ticker: normalizedTicker },
    holding,
    summary: portfolioSummary,
  }), [herdData, holding, portfolioSummary, normalizedTicker])
  const currentReliability = useMemo(
    () => currentSignalReliability(herdData, reliability),
    [herdData, reliability]
  )
  const reliabilityEvidence = useMemo(
    () => reliabilityEvidenceItems(reliability),
    [reliability]
  )
  const fundamentalGuard = useMemo(
    () => evaluateFundamentalGuard(financials, herdData),
    [financials, herdData]
  )
  const signalEvidence = useMemo(
    () => buildSignalEvidence(herdData),
    [herdData]
  )
  const journalSummary = useMemo(
    () => summarizeSignalJournal(signalLogs),
    [signalLogs]
  )
  const historyPoints = useMemo(() => {
    if (herdHistory.length > 0) return herdHistory
    if (!herdData?.scoreDate) return []
    return [{ date: herdData.scoreDate, score: herdScore }]
  }, [herdHistory, herdData, herdScore])
  const herdMomentum = useMemo(
    () => getHerdMomentum(historyPoints, herdScore, herdStage),
    [historyPoints, herdScore, herdStage]
  )

  async function handleJournalAction(actionType, details = {}) {
    setActionError(null)
    try {
      const res = await createSignalJournal({
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
      const saved = res.data?.data
      if (saved) {
        setSignalLogs((prev) => [saved, ...prev].slice(0, 5))
      } else {
        await fetchSignalLogs()
      }
    } catch {
      await fetchSignalLogs()
      setActionError('판단 기록을 저장하지 못했습니다.')
    }
    setJournalAction(null)
  }

  async function handleJournalDelete(id) {
    setActionError(null)
    try {
      await deleteSignalJournal(id)
      setSignalLogs((prev) => prev.filter((log) => log.id !== id))
    } catch {
      await fetchSignalLogs()
      setActionError('판단 기록을 삭제하지 못했습니다.')
    }
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
    signalLogs,
    journalAction,
    setJournalAction,
    actionError,
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
    handleJournalDelete,
  }
}

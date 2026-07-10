import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  getStockHerd, addToPortfolio, addToWatchlist,
  getStockFinancials, getStockHerdHistory, getStockHerdReliability,
  getPortfolio, getPortfolioSummary,
  getSignalJournal, createSignalJournal, deleteSignalJournal,
} from '../../api/herdApi'
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

  const normalizedTicker = ticker.toUpperCase()

  const fetchSignalLogs = useCallback(async () => {
    try {
      const res = await getSignalJournal(normalizedTicker)
      setSignalLogs((res.data?.data ?? []).slice(0, 5))
    } catch {
      setSignalLogs([])
    }
  }, [normalizedTicker])

  useEffect(() => { fetchSignalLogs() }, [fetchSignalLogs])

  /* HERD 데이터 조회 */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res  = await getStockHerd(normalizedTicker)
      const data = res.data?.data
      if (data) {
        setHerdData(data)
      } else {
        setError(
          `${ticker} 종목의 HERD 데이터가 없습니다.\nPython 스케줄러를 먼저 실행해주세요.`
        )
      }
    } catch {
      setError(`백엔드 서버에 연결할 수 없습니다.\n${API_HOST}이 실행 중인지 확인해주세요.`)
    } finally {
      setLoading(false)
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
    setHistoryLoading(true)
    setHerdHistory([])
    getStockHerdHistory(normalizedTicker, historyPeriod)
      .then((res) => { setHerdHistory(res.data?.data?.points ?? []) })
      .catch(() => { setHerdHistory([]) })
      .finally(() => { setHistoryLoading(false) })
  }, [normalizedTicker, historyPeriod])

  /* HERD 신호 신뢰도 — 저장된 HERD 히스토리와 가격 데이터 기반 */
  useEffect(() => {
    setReliabilityLoading(true)
    setReliability(null)
    getStockHerdReliability(normalizedTicker, 3)
      .then((res) => { setReliability(res.data?.data ?? null) })
      .catch(() => { setReliability(null) })
      .finally(() => { setReliabilityLoading(false) })
  }, [normalizedTicker])

  /* Fundamental Guard — HERD 판단을 막을 재무 경고만 확인 */
  useEffect(() => {
    setFinancialsLoading(true)
    setFinancials(null)
    getStockFinancials(normalizedTicker)
      .then((res) => { setFinancials(res.data?.data ?? null) })
      .catch(() => { setFinancials(null) })
      .finally(() => { setFinancialsLoading(false) })
  }, [normalizedTicker])

  /* 포트폴리오 추가 */
  async function handleAddPortfolio() {
    if (portfolioStatus !== 'idle') return
    setPortfolioStatus('loading')
    try {
      await addToPortfolio(normalizedTicker)
      setPortfolioStatus('added')
    } catch (e) {
      setPortfolioStatus(e.response?.status === 409 ? 'exists' : 'idle')
    }
  }

  /* 관심종목 추가 */
  async function handleAddWatchlist() {
    if (watchlistStatus !== 'idle') return
    setWatchlistStatus('loading')
    try {
      await addToWatchlist(normalizedTicker)
      setWatchlistStatus('added')
    } catch (e) {
      setWatchlistStatus(e.response?.status === 409 ? 'exists' : 'idle')
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
    }
    setJournalAction(null)
  }

  async function handleJournalDelete(id) {
    try {
      await deleteSignalJournal(id)
      setSignalLogs((prev) => prev.filter((log) => log.id !== id))
    } catch {
      await fetchSignalLogs()
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


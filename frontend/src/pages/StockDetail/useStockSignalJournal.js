import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createSignalJournal,
  deleteSignalJournal,
  getSignalJournal,
} from '../../api/herdApi'

export function useStockSignalJournal(normalizedTicker) {
  const [signalLogs, setSignalLogs] = useState([])
  const [journalAction, setJournalAction] = useState(null)
  const [actionError, setActionError] = useState(null)
  const journalRequest = useRef(0)

  useEffect(() => {
    setSignalLogs([])
    setJournalAction(null)
    setActionError(null)
  }, [normalizedTicker])

  const fetchSignalLogs = useCallback(async () => {
    const requestId = ++journalRequest.current
    try {
      const response = await getSignalJournal(normalizedTicker)
      if (requestId === journalRequest.current) {
        setSignalLogs((response.data?.data ?? []).slice(0, 5))
      }
    } catch {
      if (requestId === journalRequest.current) setSignalLogs([])
    }
  }, [normalizedTicker])

  useEffect(() => {
    fetchSignalLogs()
  }, [fetchSignalLogs])

  const saveSignalLog = useCallback(async (entry) => {
    setActionError(null)
    try {
      const response = await createSignalJournal(entry)
      const saved = response.data?.data
      if (saved) {
        setSignalLogs((previous) => [saved, ...previous].slice(0, 5))
      } else {
        await fetchSignalLogs()
      }
      return true
    } catch {
      await fetchSignalLogs()
      setActionError('판단 기록을 저장하지 못했습니다.')
      return false
    } finally {
      setJournalAction(null)
    }
  }, [fetchSignalLogs])

  const removeSignalLog = useCallback(async (id) => {
    setActionError(null)
    try {
      await deleteSignalJournal(id)
      setSignalLogs((previous) => previous.filter((log) => log.id !== id))
      return true
    } catch {
      await fetchSignalLogs()
      setActionError('판단 기록을 삭제하지 못했습니다.')
      return false
    }
  }, [fetchSignalLogs])

  return {
    signalLogs,
    journalAction,
    setJournalAction,
    actionError,
    setActionError,
    saveSignalLog,
    removeSignalLog,
  }
}

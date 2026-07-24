import { useCallback, useEffect, useMemo, useState } from 'react'
import { getDataStatus, getSignalJournal } from '../../api/herdApi'
import { summarizeSignalJournal } from '../../utils/signalJournal'

/**
 * 대시보드 핵심 포트폴리오 조회와 독립적으로 실패할 수 있는 보조 데이터를 관리한다.
 */
export function useDashboardSupportingData() {
  const [signalLogs, setSignalLogs] = useState([])
  const [dataStatus, setDataStatus] = useState(null)
  const [dataStatusError, setDataStatusError] = useState(false)

  const fetchDataStatus = useCallback(async () => {
    try {
      const response = await getDataStatus()
      setDataStatus(response.data?.data ?? null)
      setDataStatusError(false)
    } catch {
      setDataStatusError(true)
    }
  }, [])

  const fetchSignalLogs = useCallback(async () => {
    try {
      const response = await getSignalJournal()
      setSignalLogs(response.data?.data ?? [])
    } catch {
      setSignalLogs([])
    }
  }, [])

  useEffect(() => {
    fetchDataStatus()
  }, [fetchDataStatus])

  useEffect(() => {
    fetchSignalLogs()
    window.addEventListener('focus', fetchSignalLogs)
    return () => window.removeEventListener('focus', fetchSignalLogs)
  }, [fetchSignalLogs])

  return {
    dataStatus,
    dataStatusError,
    fetchDataStatus,
    signalJournalSummary: useMemo(
      () => summarizeSignalJournal(signalLogs),
      [signalLogs]
    ),
    recentSignalLogs: useMemo(() => signalLogs.slice(0, 3), [signalLogs]),
  }
}

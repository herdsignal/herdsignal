import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getObjectiveOperatingReview,
  getOperatingReviewRecords,
  getPersonalOperatingReview,
  recordOperatingReview,
} from '../../api/herdApi'

export function useOperatingReview(ticker, authenticated) {
  const [review, setReview] = useState(null)
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [recording, setRecording] = useState(false)
  const [error, setError] = useState(null)
  const requestRef = useRef(0)

  const load = useCallback(async () => {
    const requestId = ++requestRef.current
    setLoading(true)
    setRecording(false)
    setError(null)
    try {
      let response
      if (authenticated) {
        try {
          response = await getPersonalOperatingReview(ticker)
        } catch {
          response = await getObjectiveOperatingReview(ticker)
        }
      } else {
        response = await getObjectiveOperatingReview(ticker)
      }
      const activeReview = response.data?.data ?? null
      if (requestId !== requestRef.current) return null
      setReview(activeReview)
      if (authenticated) {
        try {
          const history = await getOperatingReviewRecords(ticker)
          if (requestId === requestRef.current) {
            setRecords(history.data?.data ?? [])
          }
        } catch {
          if (requestId === requestRef.current) setRecords([])
        }
      } else {
        setRecords([])
      }
      return activeReview
    } catch {
      if (requestId === requestRef.current) {
        setReview(null)
        setRecords([])
        setError('장기 운용 검토를 불러오지 못했습니다.')
      }
    } finally {
      if (requestId === requestRef.current) setLoading(false)
    }
    return null
  }, [authenticated, ticker])

  useEffect(() => {
    load()
  }, [load])

  const record = useCallback(async () => {
    if (!authenticated || recording) return
    const requestId = requestRef.current
    setRecording(true)
    setError(null)
    try {
      const response = await recordOperatingReview(ticker)
      const saved = response.data?.data
      if (saved && requestId === requestRef.current) {
        setRecords((current) => [saved, ...current])
      }
    } catch {
      if (requestId === requestRef.current) {
        setError('판단 기록을 저장하지 못했습니다.')
      }
    } finally {
      if (requestId === requestRef.current) setRecording(false)
    }
  }, [authenticated, recording, ticker])

  return { review, records, loading, recording, error, record, reload: load }
}

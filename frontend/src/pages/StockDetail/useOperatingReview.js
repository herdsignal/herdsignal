import { useCallback, useEffect, useState } from 'react'
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

  const load = useCallback(async () => {
    setLoading(true)
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
      setReview(activeReview)
      if (authenticated) {
        try {
          const history = await getOperatingReviewRecords(ticker)
          setRecords(history.data?.data ?? [])
        } catch {
          setRecords([])
        }
      } else {
        setRecords([])
      }
      return activeReview
    } catch {
      setReview(null)
      setRecords([])
      setError('장기 운용 검토를 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
    return null
  }, [authenticated, ticker])

  useEffect(() => {
    load()
  }, [load])

  const record = useCallback(async () => {
    if (!authenticated || recording) return
    setRecording(true)
    setError(null)
    try {
      const response = await recordOperatingReview(ticker)
      const saved = response.data?.data
      if (saved) setRecords((current) => [saved, ...current])
    } catch {
      setError('판단 기록을 저장하지 못했습니다.')
    } finally {
      setRecording(false)
    }
  }, [authenticated, recording, ticker])

  return { review, records, loading, recording, error, record, reload: load }
}

import { useEffect, useState } from 'react'
import {
  getDailyHerdObservation,
  getHerdObservation,
} from '../../api/herdApi'
import {
  readMarketObservationCache,
  writeMarketObservationCache,
} from '../../features/market/marketCache'

export function useMarketHomeData() {
  const [observation, setObservation] = useState(
    () => readMarketObservationCache(),
  )
  const [dailyObservation, setDailyObservation] = useState(null)
  const [loading, setLoading] = useState(() => observation == null)
  const [observationError, setObservationError] = useState(false)

  useEffect(() => {
    let active = true

    Promise.allSettled([
      getHerdObservation('SPY'),
      getDailyHerdObservation('SPY'),
    ]).then(([confirmedResult, dailyResult]) => {
      if (!active) return
      if (confirmedResult.status === 'fulfilled') {
        const nextObservation = confirmedResult.value.data?.data ?? null
        setObservation(nextObservation)
        writeMarketObservationCache(nextObservation)
      }
      if (dailyResult.status === 'fulfilled') {
        setDailyObservation(dailyResult.value.data?.data ?? null)
      }
      setObservationError(confirmedResult.status === 'rejected')
    }).finally(() => {
      if (!active) return
      setLoading(false)
    })

    return () => {
      active = false
    }
  }, [])

  return {
    observation,
    dailyObservation,
    loading,
    observationError,
  }
}

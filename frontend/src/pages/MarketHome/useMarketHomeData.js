import { useEffect, useState } from 'react'
import { getHerdObservation } from '../../api/herdApi'
import {
  readMarketObservationCache,
  writeMarketObservationCache,
} from '../../features/market/marketCache'

export function useMarketHomeData() {
  const [observation, setObservation] = useState(
    () => readMarketObservationCache(),
  )
  const [loading, setLoading] = useState(() => observation == null)
  const [observationError, setObservationError] = useState(false)

  useEffect(() => {
    let active = true

    getHerdObservation('SPY').then((response) => {
      if (!active) return

      const nextObservation = response.data?.data ?? null
      setObservation(nextObservation)
      writeMarketObservationCache(nextObservation)
      setObservationError(false)
    }).catch(() => {
      if (!active) return
      setObservationError(true)
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
    loading,
    observationError,
  }
}

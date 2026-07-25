import { useEffect, useState } from 'react'
import {
  getDataStatus,
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
  const [dataStatus, setDataStatus] = useState(null)
  const [loading, setLoading] = useState(() => observation == null)
  const [observationError, setObservationError] = useState(false)
  const [statusError, setStatusError] = useState(false)

  useEffect(() => {
    let active = true

    Promise.allSettled([
      getHerdObservation('SPY'),
      getDataStatus(),
    ]).then(([observationResult, statusResult]) => {
      if (!active) return

      if (observationResult.status === 'fulfilled') {
        const nextObservation = observationResult.value.data?.data ?? null
        setObservation(nextObservation)
        writeMarketObservationCache(nextObservation)
        setObservationError(false)
      } else {
        setObservationError(true)
      }

      if (statusResult.status === 'fulfilled') {
        setDataStatus(statusResult.value.data?.data ?? null)
        setStatusError(false)
      } else {
        setStatusError(true)
      }

      setLoading(false)
    })

    return () => {
      active = false
    }
  }, [])

  return {
    observation,
    dataStatus,
    loading,
    observationError,
    statusError,
  }
}


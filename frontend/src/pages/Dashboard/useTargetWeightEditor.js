import { useCallback, useEffect, useRef, useState } from 'react'
import { updateTargetWeight } from '../../api/herdApi'

export function useTargetWeightEditor(onSaveError) {
  const [targetWeights, setTargetWeights] = useState({})
  const timers = useRef({})

  useEffect(() => () => {
    Object.values(timers.current).forEach(clearTimeout)
  }, [])

  const handleTargetWeightChange = useCallback((ticker, value) => {
    setTargetWeights((current) => {
      const next = { ...current }
      if (value === '') {
        delete next[ticker]
      } else {
        const number = Number(value)
        if (!Number.isFinite(number)) return current
        next[ticker] = String(Math.min(100, Math.max(0, number)))
      }
      return next
    })

    clearTimeout(timers.current[ticker])
    timers.current[ticker] = setTimeout(() => {
      const targetWeight = value === '' ? 0 : Number(value) / 100
      updateTargetWeight(ticker, targetWeight).catch(() => onSaveError?.(ticker))
      delete timers.current[ticker]
    }, 400)
  }, [onSaveError])

  return {
    targetWeights,
    setTargetWeights,
    handleTargetWeightChange,
  }
}

import {
  readCache,
  writeCache,
} from '../portfolio/portfolioCache'

export const CACHE_KEY_SPY = 'hs_spy_observation_s1'
export const CACHE_KEY_SPY_HISTORY = 'hs_spy_observation_history'
export const CACHE_KEY_SPY_HISTORY_VERSION = 's1-v1'

export function readMarketObservationCache() {
  return readCache(CACHE_KEY_SPY)
}

export function writeMarketObservationCache(observation) {
  writeCache(CACHE_KEY_SPY, observation)
}

export function spyHistoryCacheKey(period) {
  return `${CACHE_KEY_SPY_HISTORY}_${period}_${CACHE_KEY_SPY_HISTORY_VERSION}`
}


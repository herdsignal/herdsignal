import {
  readCache,
  writeCache,
} from '../portfolio/portfolioCache'

export const CACHE_KEY_SPY = 'hs_spy_observation_s1'

export function readMarketObservationCache() {
  return readCache(CACHE_KEY_SPY)
}

export function writeMarketObservationCache(observation) {
  writeCache(CACHE_KEY_SPY, observation)
}

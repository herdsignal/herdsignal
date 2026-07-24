export const CACHE_KEY_REALTIME = 'hs_portfolio_realtime'
export const CACHE_KEY_HERD = 'hs_portfolio_herd'
export const CACHE_KEY_HERD_TIME = 'hs_portfolio_herd_time'
export const CACHE_KEY_TIME = 'hs_cache_time'

const PORTFOLIO_CACHE_KEYS = [
  CACHE_KEY_REALTIME,
  CACHE_KEY_HERD,
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_TIME,
]

export function readCache(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function writeCache(key, data) {
  try {
    localStorage.setItem(key, JSON.stringify(data))
  } catch {
    // 저장소 접근 실패는 다음 API 조회로 복구한다.
  }
}

export function userCacheKey(key, userId) {
  return `${key}:${userId || 'anonymous'}`
}

export function readUserCache(key, userId) {
  return readCache(userCacheKey(key, userId))
}

export function writeUserCache(key, userId, data) {
  writeCache(userCacheKey(key, userId), data)
}

export function clearPortfolioCaches(userId) {
  try {
    PORTFOLIO_CACHE_KEYS.forEach((key) => {
      localStorage.removeItem(userCacheKey(key, userId))
    })
  } catch {
    // 저장소 접근 실패는 다음 API 조회로 복구한다.
  }
}

export function clearAllPortfolioCaches() {
  try {
    const prefixes = PORTFOLIO_CACHE_KEYS.map((key) => `${key}:`)
    Object.keys(localStorage).forEach((key) => {
      if (PORTFOLIO_CACHE_KEYS.includes(key)
        || prefixes.some((prefix) => key.startsWith(prefix))) {
        localStorage.removeItem(key)
      }
    })
  } catch {
    // 브라우저 정책으로 저장소 열람이 불가능하면 API 재조회에 맡긴다.
  }
}

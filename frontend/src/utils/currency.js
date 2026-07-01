/**
 * utils/currency.js — 환율 조회 및 USD→KRW 변환 유틸리티
 *
 * frankfurter.app: 유럽중앙은행 기준 무료 환율 API.
 * 갱신 주기 약 하루 1회 (장 마감 기준). "15분 지연"은 yfinance 주가 기준.
 */

/** API 실패 시 반환할 기본 환율 (최근 평균) */
const FALLBACK_RATE = 1350

/**
 * USD/KRW 환율 조회.
 * 실패 시 FALLBACK_RATE(1350) 반환.
 *
 * @returns {Promise<number>} USD/KRW 환율 (예: 1380.5)
 */
export async function fetchExchangeRate() {
  try {
    const res = await fetch('https://api.frankfurter.dev/v1/latest?from=USD&to=KRW')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const rate = data?.rates?.KRW
    if (!rate || typeof rate !== 'number') throw new Error('KRW 환율 데이터 없음')
    return rate
  } catch (e) {
    console.warn('[currency] 환율 조회 실패 — 기본값 사용:', e.message)
    return FALLBACK_RATE
  }
}

/**
 * USD 금액을 원화로 변환해 포맷 문자열 반환.
 *
 * @param {number} usdAmount — 달러 금액
 * @param {number} rate      — USD/KRW 환율
 * @returns {string}          — "₩19,336,560" 형식
 */
export function formatKRW(usdAmount, rate) {
  if (usdAmount == null || rate == null) return null
  const krw = Math.round(Number(usdAmount) * rate)
  return `${krw.toLocaleString('ko-KR')}원`
}

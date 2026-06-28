/**
 * api/herdApi.js — Spring Boot REST API 호출 모듈
 * 모든 API 호출은 이 파일에서만 관리한다.
 * BASE_URL은 환경변수(.env)로 관리하며 기본값은 localhost:8080.
 */

import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'

/** axios 인스턴스 — 공통 설정 적용 */
const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

/* ── 포트폴리오 ─────────────────────────────── */

/** 포트폴리오 전체 HERD 점수 조회 */
export const getPortfolioHerd = () => api.get('/api/portfolio/herd')

/** 포트폴리오 종목 추가 */
export const addToPortfolio = (ticker) => api.post('/api/portfolio', { ticker })

/** 포트폴리오 종목 삭제 */
export const removeFromPortfolio = (ticker) => api.delete(`/api/portfolio/${ticker}`)

/** 포트폴리오 목록 조회 */
export const getPortfolio = () => api.get('/api/portfolio')

/* ── 관심 종목 ──────────────────────────────── */

/** 관심 종목 전체 HERD 점수 조회 */
export const getWatchlistHerd = () => api.get('/api/watchlist/herd')

/** 관심 종목 추가 */
export const addToWatchlist = (ticker, memo) => api.post('/api/watchlist', { ticker, memo })

/** 관심 종목 삭제 */
export const removeFromWatchlist = (ticker) => api.delete(`/api/watchlist/${ticker}`)

/* ── 개별 종목 ──────────────────────────────── */

/** 특정 종목 HERD 점수 + 지표 분해값 조회 */
export const getStockHerd = (ticker) => api.get(`/api/stocks/${ticker}/herd`)

export default api

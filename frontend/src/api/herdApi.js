/**
 * api/herdApi.js — Spring Boot REST API 호출 모듈
 * 모든 API 호출은 이 파일에서만 관리한다.
 * BASE_URL은 환경변수(.env)로 관리하며 기본값은 localhost:8080.
 */

import axios from 'axios'

/*
 * 개발: Vite proxy(/api → localhost:8080)를 통해 같은 origin으로 요청 → CORS 불필요.
 * 프로덕션: VITE_API_BASE_URL 환경변수에 실제 API 서버 URL 지정.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

/** axios 인스턴스 — 공통 설정 적용 */
const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

/* ── 포트폴리오 ─────────────────────────────── */

/** 포트폴리오 전체 HERD 점수 조회 */
export const getPortfolioHerd = () => api.get('/api/portfolio/herd')

/** 포트폴리오 전체 HERD 점수 강제 갱신 */
export const refreshPortfolioHerd = () =>
  api.post('/api/portfolio/herd/refresh', null, { timeout: 180_000 })

/** 포트폴리오 종목 추가 */
export const addToPortfolio = (ticker) => api.post('/api/portfolio', { ticker })

/** 포트폴리오 종목 삭제 */
export const removeFromPortfolio = (ticker) => api.delete(`/api/portfolio/${ticker}`)

/** 포트폴리오 목록 조회 */
export const getPortfolio = () => api.get('/api/portfolio')

/* ── 관심 종목 ──────────────────────────────── */

/** 관심 종목 전체 HERD 점수 조회 */
export const getWatchlistHerd = () => api.get('/api/watchlist/herd')

/** 관심 종목 목록 조회 */
export const getWatchlist = () => api.get('/api/watchlist')

/** 관심 종목 추가 */
export const addToWatchlist = (ticker, memo) => api.post('/api/watchlist', { ticker, memo })

/** 관심 종목 삭제 */
export const removeFromWatchlist = (ticker) => api.delete(`/api/watchlist/${ticker}`)

/* ── 포트폴리오 평가금액 ─────────────────────── */

/** 포트폴리오 현재 평가 요약 (총액·수익률·일일등락·종목별 현재가) */
export const getPortfolioSummary = () => api.get('/api/portfolio/summary')

/** yfinance 실시간 현재가 기반 포트폴리오 (Python ProcessBuilder 경유 — 약 3~5초) */
export const getPortfolioRealtime = () =>
  api.get('/api/portfolio/realtime', { timeout: 40_000 })

/** 포트폴리오 자산 히스토리 시계열 */
export const getPortfolioHistory = (period) =>
  api.get(`/api/portfolio/history?period=${period}`)

/** 현재 현금 보유액 조회 */
export const getCashBalance = () => api.get('/api/portfolio/cash')

/** 현재 현금 보유액 수정 */
export const updateCashBalance = (cashAmount) =>
  api.put('/api/portfolio/cash', { cashAmount })

/** 보유 종목의 평균 매수가·수량 수정 */
export const updateAvgPrice = (ticker, avgPrice, quantity) =>
  api.patch(`/api/portfolio/${ticker}/avg-price`, { avgPrice, quantity })

/* ── HERD 판단 기록 ────────────────────────── */

/** 전체 또는 특정 종목 HERD 판단 기록 조회 */
export const getSignalJournal = (ticker) =>
  api.get('/api/journal', { params: ticker ? { ticker } : {} })

/** HERD 판단 기록 저장 */
export const createSignalJournal = (entry) => api.post('/api/journal', entry)

/** HERD 판단 기록 삭제 */
export const deleteSignalJournal = (id) => api.delete(`/api/journal/${id}`)

/* ── 개별 종목 ──────────────────────────────── */

/** 회사명/티커 기반 종목 검색 */
export const searchStocks = (query) =>
  api.get(`/api/stocks/search?q=${encodeURIComponent(query)}`)

/** 특정 종목 HERD 점수 + 지표 분해값 조회 */
export const getStockHerd = (ticker) => api.get(`/api/stocks/${ticker}/herd`)

/** 특정 종목 HERD 점수 강제 갱신 */
export const refreshStockHerd = (ticker) =>
  api.post(`/api/stocks/${ticker}/herd/refresh`, null, { timeout: 60_000 })

/** 특정 종목 재무 가드용 핵심 재무정보 조회 */
export const getStockFinancials = (ticker) =>
  api.get(`/api/stocks/${ticker}/financials`, { timeout: 40_000 })

/** 특정 종목 HERD 히스토리 조회 (기본 3y) */
export const getStockHerdHistory = (ticker, period = '3y') =>
  api.get(`/api/stocks/${ticker}/herd/history?period=${period}`)

/** 특정 종목 HERD 신호 신뢰도 조회 */
export const getStockHerdReliability = (ticker, years = 3) =>
  api.get(`/api/stocks/${ticker}/herd/reliability?years=${years}`, { timeout: 70_000 })

/** SPY HERD 히스토리 조회 (기본 3y) */
export const getSpyHerdHistory = (period = '3y') =>
  getStockHerdHistory('SPY', period)

/* ── 모델 검증 ─────────────────────────────── */

/** 최신 전체 백테스트 리포트의 HERD Lab용 요약 조회 */
export const getModelValidationReport = () => api.get('/api/model/validation')

export default api

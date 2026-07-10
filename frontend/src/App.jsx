/**
 * App.jsx — 라우터 진입점
 * Layout 컴포넌트 안에 모든 페이지를 중첩 라우트로 구성한다.
 */

import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout     from './components/Layout/Layout'

const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard'))
const StockDetail = lazy(() => import('./pages/StockDetail/StockDetail'))
const Search = lazy(() => import('./pages/Search/Search'))
const Watchlist = lazy(() => import('./pages/Watchlist/Watchlist'))
const History = lazy(() => import('./pages/History/History'))
const AiRebalance = lazy(() => import('./pages/AiRebalance/AiRebalance'))
const HerdFlowPreview = lazy(() => import('./pages/HerdFlowPreview/HerdFlowPreview'))
const HerdLab = lazy(() => import('./pages/HerdLab/HerdLab'))
const Journal = lazy(() => import('./pages/Journal/Journal'))

function RouteFallback() {
  return (
    <div role="status" style={{ padding: '32px', color: 'var(--text-2)' }}>
      화면 불러오는 중…
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          {/* Layout이 사이드바 + <Outlet>으로 모든 페이지를 감싼다 */}
          <Route element={<Layout />}>
            <Route path="/"              element={<Dashboard />} />
            <Route path="/stock/:ticker" element={<StockDetail />} />
            <Route path="/search"        element={<Search />} />
            <Route path="/watchlist"     element={<Watchlist />} />
            <Route path="/history"       element={<History />} />
            <Route path="/herd-lab"      element={<HerdLab />} />
            <Route path="/journal"       element={<Journal />} />
            <Route path="/ai"            element={<AiRebalance />} />
            <Route path="/herd-flow"     element={<HerdFlowPreview />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

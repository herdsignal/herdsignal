/**
 * App.jsx — 라우터 진입점
 * Layout 컴포넌트 안에 모든 페이지를 중첩 라우트로 구성한다.
 */

import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout     from './components/Layout/Layout'
import RouteErrorBoundary from './components/RouteErrorBoundary/RouteErrorBoundary'
import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import { ROUTER_FUTURE } from './routerConfig'

const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard'))
const MarketHome = lazy(() => import('./pages/MarketHome/MarketHome'))
const PublicHome = lazy(() => import('./pages/PublicHome/PublicHome'))
const Login = lazy(() => import('./pages/Login/Login'))
const StockDetail = lazy(() => import('./pages/StockDetail/StockDetail'))
const Search = lazy(() => import('./pages/Search/Search'))
const Watchlist = lazy(() => import('./pages/Watchlist/Watchlist'))
const History = lazy(() => import('./pages/History/History'))
const HerdLab = lazy(() => import('./pages/HerdLab/HerdLab'))
const Journal = lazy(() => import('./pages/Journal/Journal'))
const Settings = lazy(() => import('./pages/Settings/Settings'))

function RouteFallback() {
  return (
    <div role="status" style={{ padding: '32px', color: 'var(--text-2)' }}>
      화면 불러오는 중…
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter future={ROUTER_FUTURE}>
      <AuthProvider>
      <RouteErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
          <Route path="/" element={<PublicHome />} />
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
          {/* Layout이 공통 탐색 + <Outlet>으로 모든 보호 페이지를 감싼다 */}
          <Route element={<Layout />}>
            <Route path="/app"           element={<MarketHome />} />
            <Route path="/portfolio"     element={<Dashboard />} />
            <Route path="/stock/:ticker" element={<StockDetail />} />
            <Route path="/search"        element={<Search />} />
            <Route path="/watchlist"     element={<Watchlist />} />
            <Route path="/history"       element={<History />} />
            <Route path="/herd-lab"      element={<HerdLab />} />
            <Route path="/journal"       element={<Journal />} />
            <Route path="/settings"      element={<Settings />} />
          </Route>
          </Route>
          </Routes>
        </Suspense>
      </RouteErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  )
}

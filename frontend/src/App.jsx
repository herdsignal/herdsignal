/**
 * App.jsx — 라우터 진입점
 * Layout 컴포넌트 안에 모든 페이지를 중첩 라우트로 구성한다.
 */

import { Component, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout     from './components/Layout/Layout'
import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'

const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard'))
const PublicHome = lazy(() => import('./pages/PublicHome/PublicHome'))
const Login = lazy(() => import('./pages/Login/Login'))
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

class RouteErrorBoundary extends Component {
  state = { failed: false, message: '' }

  static getDerivedStateFromError(error) {
    return { failed: true, message: error?.message ?? '' }
  }

  componentDidCatch(error) {
    console.error('페이지 렌더링 오류', error)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" style={{ padding: '32px', color: 'var(--text-1)' }}>
        <p>화면을 표시하는 중 오류가 발생했습니다.</p>
        {this.state.message && <p style={{ color: 'var(--text-3)' }}>{this.state.message}</p>}
        <button type="button" onClick={() => window.location.reload()}>새로고침</button>
      </div>
    )
  }
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <RouteErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
          <Route path="/" element={<PublicHome />} />
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
          {/* Layout이 사이드바 + <Outlet>으로 모든 페이지를 감싼다 */}
          <Route element={<Layout />}>
            <Route path="/app"           element={<Dashboard />} />
            <Route path="/stock/:ticker" element={<StockDetail />} />
            <Route path="/search"        element={<Search />} />
            <Route path="/watchlist"     element={<Watchlist />} />
            <Route path="/history"       element={<History />} />
            <Route path="/herd-lab"      element={<HerdLab />} />
            <Route path="/journal"       element={<Journal />} />
            <Route path="/ai"            element={<AiRebalance />} />
            <Route path="/herd-flow"     element={<HerdFlowPreview />} />
          </Route>
          </Route>
          </Routes>
        </Suspense>
      </RouteErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  )
}

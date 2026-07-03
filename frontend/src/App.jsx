/**
 * App.jsx — 라우터 진입점
 * Layout 컴포넌트 안에 모든 페이지를 중첩 라우트로 구성한다.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout     from './components/Layout/Layout'
import Dashboard  from './pages/Dashboard/Dashboard'
import StockDetail from './pages/StockDetail/StockDetail'
import Search     from './pages/Search/Search'
import Watchlist  from './pages/Watchlist/Watchlist'
import History    from './pages/History/History'
import AiRebalance from './pages/AiRebalance/AiRebalance'
import HerdFlowPreview from './pages/HerdFlowPreview/HerdFlowPreview'
import HerdLab from './pages/HerdLab/HerdLab'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Layout이 사이드바 + <Outlet>으로 모든 페이지를 감싼다 */}
        <Route element={<Layout />}>
          <Route path="/"              element={<Dashboard />} />
          <Route path="/stock/:ticker" element={<StockDetail />} />
          <Route path="/search"        element={<Search />} />
          <Route path="/watchlist"     element={<Watchlist />} />
          <Route path="/history"       element={<History />} />
          <Route path="/herd-lab"      element={<HerdLab />} />
          <Route path="/ai"            element={<AiRebalance />} />
          <Route path="/herd-flow"     element={<HerdFlowPreview />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

import { Component } from 'react'
import { useLocation } from 'react-router-dom'

export class RouteErrorBoundary extends Component {
  state = { failed: false, message: '' }

  static getDerivedStateFromError(error) {
    return { failed: true, message: error?.message ?? '' }
  }

  componentDidCatch(error) {
    console.error('페이지 렌더링 오류', error)
  }

  componentDidUpdate(previousProps) {
    if (
      this.state.failed
      && previousProps.resetKey !== this.props.resetKey
    ) {
      this.setState({ failed: false, message: '' })
    }
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

export default function RouteErrorBoundaryForLocation({ children }) {
  const location = useLocation()
  return (
    <RouteErrorBoundary resetKey={location.pathname}>
      {children}
    </RouteErrorBoundary>
  )
}

import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import herdSignalMark from '../../assets/brand/herdsignal-mark.svg'
import { useAuth } from '../../auth/AuthContext'
import ActionNotifications from '../ActionNotifications/ActionNotifications'
import styles from './Layout.module.css'

const PRIMARY_NAVIGATION = [
  { to: '/app', label: '시장', end: true },
  { to: '/portfolio', label: '포트폴리오' },
  { to: '/search', label: '종목' },
  { to: '/herd-lab', label: '연구' },
]

const SECONDARY_NAVIGATION = [
  { to: '/watchlist', label: '관찰 종목' },
  { to: '/history', label: '자산 히스토리' },
  { to: '/journal', label: '판단 기록' },
  { to: '/settings', label: '설정' },
]

const PAGE_TITLES = {
  '/app': '시장',
  '/portfolio': '포트폴리오',
  '/search': '종목 찾기',
  '/watchlist': '관심종목',
  '/history': '자산 히스토리',
  '/journal': '판단 기록',
  '/herd-lab': 'HERD 연구실',
  '/settings': '투자 프로필',
}

export function titleForPath(pathname) {
  if (pathname.startsWith('/stock/')) return '종목 상세 · HerdSignal'
  const title = PAGE_TITLES[pathname]
  return title ? `${title} · HerdSignal` : 'HerdSignal'
}

function Navigation({ className, label }) {
  return (
    <nav className={className} aria-label={label}>
      {PRIMARY_NAVIGATION.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            `${styles.navItem} ${isActive ? styles.active : ''}`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}
export default function Layout() {
  const { user, signOut } = useAuth()
  const location = useLocation()
  const accountRef = useRef(null)
  const accountTriggerRef = useRef(null)
  const mainRef = useRef(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const [isDark, setIsDark] = useState(() => {
    return localStorage.getItem('herdsignal_theme') !== 'light'
  })

  useEffect(() => {
    document.body.classList.toggle('light', !isDark)
    localStorage.setItem('herdsignal_theme', isDark ? 'dark' : 'light')
  }, [isDark])

  useEffect(() => {
    setAccountOpen(false)
  }, [location.pathname])

  useEffect(() => {
    document.title = titleForPath(location.pathname)
    mainRef.current?.focus({ preventScroll: true })
  }, [location.pathname])

  useEffect(() => {
    if (!accountOpen) return undefined

    const closeOutside = (event) => {
      if (!accountRef.current?.contains(event.target)) setAccountOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        setAccountOpen(false)
        accountTriggerRef.current?.focus()
      }
    }

    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [accountOpen])

  const userInitial = (user?.displayName || user?.email || 'U').slice(0, 1)

  return (
    <div className={styles.wrapper}>
      <a className={styles.skipLink} href="#main-content">본문으로 건너뛰기</a>
      <header className={styles.topbar}>
        <NavLink className={styles.brand} to="/app" aria-label="HerdSignal 시장 홈">
          <img src={herdSignalMark} alt="" aria-hidden="true" />
          <span>HerdSignal</span>
        </NavLink>

        <Navigation className={styles.desktopNav} label="주요 메뉴" />

        <div className={styles.account} ref={accountRef}>
          <NavLink className={styles.watchlistLink} to="/watchlist">
            관찰
          </NavLink>
          <button
            ref={accountTriggerRef}
            type="button"
            className={styles.accountTrigger}
            aria-label={accountOpen ? '계정 메뉴 닫기' : '계정 메뉴 열기'}
            aria-expanded={accountOpen}
            aria-controls="account-panel"
            aria-haspopup="true"
            onClick={() => setAccountOpen((open) => !open)}
          >
            {user?.profileImageUrl
              ? (
                <img
                  src={user.profileImageUrl}
                  alt=""
                  referrerPolicy="no-referrer"
                />
                )
              : <span>{userInitial}</span>}
          </button>

          {accountOpen && (
            <aside id="account-panel" className={styles.accountPanel} aria-label="계정 메뉴">
              <div className={styles.userSummary}>
                <strong>{user?.displayName || 'HerdSignal 사용자'}</strong>
                <span>{user?.developmentMode ? '개발 모드' : user?.email}</span>
              </div>
              <ActionNotifications placement="menu" />
              <nav className={styles.secondaryNav} aria-label="보조 메뉴">
                {SECONDARY_NAVIGATION.map((item) => (
                  <NavLink key={item.to} to={item.to}>
                    {item.label}
                  </NavLink>
                ))}
              </nav>
              <div className={styles.panelActions}>
                <button type="button" onClick={() => setIsDark((dark) => !dark)}>
                  {isDark ? '라이트 모드' : '다크 모드'}
                </button>
                {!user?.developmentMode && (
                  <button type="button" onClick={signOut}>로그아웃</button>
                )}
              </div>
            </aside>
          )}
        </div>
      </header>

      <main
        id="main-content"
        ref={mainRef}
        className={styles.main}
        tabIndex="-1"
      >
        <Outlet />
      </main>

      <Navigation className={styles.mobileNav} label="모바일 주요 메뉴" />
    </div>
  )
}

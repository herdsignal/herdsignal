/**
 * Layout.jsx — 사이드바 + 메인 영역 래퍼
 * wireframes/wireframe-home-v4.html 사이드바 구조 기준으로 구현.
 * 다크/라이트 모드 토글은 body 클래스 방식으로 관리.
 */

import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import herdSignalMark from '../../assets/brand/herdsignal-mark.svg'
import { useAuth } from '../../auth/AuthContext'
import ActionNotifications from '../ActionNotifications/ActionNotifications'
import styles from './Layout.module.css'

export default function Layout() {
  const { user, signOut } = useAuth()
  /* body.light 클래스로 라이트모드 전환 */
  const [isDark, setIsDark] = useState(() => {
    return localStorage.getItem('herdsignal_theme') !== 'light'
  })

  useEffect(() => {
    document.body.classList.toggle('light', !isDark)
    localStorage.setItem('herdsignal_theme', isDark ? 'dark' : 'light')
  }, [isDark])

  return (
    <div className={styles.wrapper}>
      {/* ── 사이드바 ── */}
      <aside className={styles.sidebar}>
        <div className={styles.logo}>
          <img src={herdSignalMark} alt="" className={styles.logoMark} aria-hidden="true" />
          <span className={styles.logoText}>
            Herd<em>Signal</em>
          </span>
        </div>

        {/* 포트폴리오 섹션 */}
        <nav className={styles.navGroup}>
          <div className={styles.navLabel}>포트폴리오</div>
          <NavLink
            to="/app"
            end
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.active : ''}`
            }
          >
            <span className={styles.navIcon}>⌂</span><span>대시보드</span>
          </NavLink>
          <NavLink
            to="/watchlist"
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.active : ''}`
            }
          >
            <span className={styles.navIcon}>◎</span><span>대기열</span>
          </NavLink>
        </nav>

        {/* 분석 섹션 */}
        <nav className={styles.navGroup}>
          <div className={styles.navLabel}>분석</div>
          <NavLink
            to="/search"
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.active : ''}`
            }
          >
            <span className={styles.navIcon}>⌕</span><span>검색</span>
          </NavLink>
          <NavLink
            to="/herd-lab"
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.active : ''}`
            }
          >
            <span className={styles.navIcon}>◇</span><span>HERD Lab</span>
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.active : ''}`
            }
          >
            <span className={styles.navIcon}>⚙</span><span>설정</span>
          </NavLink>
        </nav>

        {/* 하단 — 테마 토글 */}
        <div className={styles.sidebarBottom}>
          <ActionNotifications />
          <div className={styles.userSummary}>
            {user?.profileImageUrl
              ? <img src={user.profileImageUrl} alt="" referrerPolicy="no-referrer" />
              : <span>{(user?.displayName || 'U').slice(0, 1)}</span>}
            <div><strong>{user?.displayName}</strong><em>{user?.developmentMode ? '개발 모드' : user?.email}</em></div>
          </div>
          {!user?.developmentMode && <button className={styles.logoutBtn} onClick={signOut}>로그아웃</button>}
          <button
            className={styles.themeBtn}
            onClick={() => setIsDark((d) => !d)}
          >
            {isDark ? '라이트 모드' : '다크 모드'}
          </button>
        </div>
      </aside>

      {/* ── 메인 영역 — 페이지가 여기 렌더 ── */}
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}

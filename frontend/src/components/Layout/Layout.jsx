/**
 * Layout.jsx — 사이드바 + 메인 영역 래퍼
 * wireframes/wireframe-home-v4.html 사이드바 구조 기준으로 구현.
 * 다크/라이트 모드 토글은 body 클래스 방식으로 관리.
 */

import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import styles from './Layout.module.css'

export default function Layout() {
  /* body.light 클래스로 라이트모드 전환 */
  const [isDark, setIsDark] = useState(true)

  useEffect(() => {
    document.body.classList.toggle('light', !isDark)
  }, [isDark])

  return (
    <div className={styles.wrapper}>
      {/* ── 사이드바 ── */}
      <aside className={styles.sidebar}>
        {/* 로고: Herd는 흰색, Signal은 --flee 색 */}
        <div className={styles.logo}>
          Herd<em className={styles.logoEm}>Signal</em>
        </div>

        {/* 포트폴리오 섹션 */}
        <nav className={styles.navGroup}>
          <div className={styles.navLabel}>포트폴리오</div>
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.active : ''}`
            }
          >
            대시보드
          </NavLink>
          <NavLink
            to="/watchlist"
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.active : ''}`
            }
          >
            관심 종목
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
            종목 검색
          </NavLink>
          <NavLink
            to="/herd-lab"
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.active : ''}`
            }
          >
            HERD Lab
          </NavLink>
        </nav>

        {/* 하단 — 테마 토글 */}
        <div className={styles.sidebarBottom}>
          <button
            className={styles.themeBtn}
            onClick={() => setIsDark((d) => !d)}
          >
            {isDark ? '☀ 라이트 모드' : '● 다크 모드'}
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

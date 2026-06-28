/**
 * Dashboard.jsx — 포트폴리오 대시보드 (/)
 * 보유 종목별 HERD 점수 카드 목록.
 * 다음 단계에서 getPortfolioHerd() API 연동 예정.
 */

import styles from './Dashboard.module.css'

export default function Dashboard() {
  /* 오늘 날짜 포맷 */
  const today = new Date().toLocaleDateString('ko-KR', {
    year:    'numeric',
    month:   'long',
    day:     'numeric',
    weekday: 'long',
  })

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className={styles.header}>
        <div>
          <div className={styles.date}>{today}</div>
          <h1 className={styles.title}>포트폴리오</h1>
        </div>
        <button className={styles.btnPrimary}>종목 추가</button>
      </div>

      {/* 빈 상태 안내 */}
      <div className={styles.empty}>
        <p className={styles.emptyText}>보유 종목이 없습니다.</p>
        <p className={styles.emptyHint}>
          종목 검색에서 포트폴리오에 추가하세요.
        </p>
      </div>
    </div>
  )
}

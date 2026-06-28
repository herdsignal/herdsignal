/**
 * Watchlist.jsx — 관심 종목 페이지 (/watchlist)
 * 다음 단계에서 getWatchlistHerd() API 연동 예정.
 */

import styles from './Watchlist.module.css'

export default function Watchlist() {
  return (
    <div>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>관심 종목</h1>
        </div>
        <button className={styles.btnPrimary}>종목 추가</button>
      </div>

      <div className={styles.empty}>
        <p className={styles.emptyText}>관심 종목이 없습니다.</p>
        <p className={styles.emptyHint}>종목 검색에서 관심 종목에 추가하세요.</p>
      </div>
    </div>
  )
}

/**
 * Search.jsx — 종목 검색 페이지 (/search)
 * 다음 단계에서 getStockHerd() + 포트폴리오/관심종목 추가 기능 연동 예정.
 */

import styles from './Search.module.css'

export default function Search() {
  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>종목 검색</h1>
      </div>

      <div className={styles.searchWrap}>
        <input
          className={styles.searchInput}
          type="text"
          placeholder="티커 심볼 입력 (예: AAPL, NVDA)"
        />
      </div>

      <div className={styles.empty}>
        <p className={styles.emptyText}>검색어를 입력하세요.</p>
      </div>
    </div>
  )
}

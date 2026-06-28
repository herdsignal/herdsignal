/**
 * StockDetail.jsx — 종목 상세 페이지 (/stock/:ticker)
 * 다음 단계에서 getStockHerd() + 지표 분해 차트 연동 예정.
 */

import { useParams } from 'react-router-dom'
import styles from './StockDetail.module.css'

export default function StockDetail() {
  const { ticker } = useParams()

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>{ticker}</h1>
      </div>
      <p className={styles.desc}>종목 상세 — 다음 단계에서 구현 예정</p>
    </div>
  )
}

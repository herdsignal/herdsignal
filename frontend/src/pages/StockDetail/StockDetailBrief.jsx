import styles from './StockDetail.module.css'

export default function StockDetailBrief({ items }) {
  return (
    <section className={styles.briefSection} aria-labelledby="stock-brief-title">
      <div className={styles.briefTitle}>
        <h2 id="stock-brief-title">관찰 요약</h2>
        <span>주간 관찰 · 행동 신호 없음</span>
      </div>
      <dl className={styles.briefGrid}>
        {items.map((item) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
            <small>{item.note}</small>
          </div>
        ))}
      </dl>
    </section>
  )
}

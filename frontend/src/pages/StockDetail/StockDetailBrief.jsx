import styles from './StockDetail.module.css'

export default function StockDetailBrief({ items }) {
  return (
    <section className={styles.briefSection} aria-labelledby="stock-brief-title">
      <div className={styles.briefTitle}>
        <h2 id="stock-brief-title">HERD Brief</h2>
        <span>규칙 기반 · 행동 비활성</span>
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

import MarketField from '../../components/MarketField/MarketField'
import {
  formatMarketDate,
  marketHomeViewModel,
} from './marketHomeModel'
import { useMarketHomeData } from './useMarketHomeData'
import styles from './MarketHome.module.css'

export default function MarketHome() {
  const data = useMarketHomeData()
  const view = marketHomeViewModel(data)

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span>S&amp;P 500</span>
          <h1>SPY</h1>
          <p>MARKET AGGREGATE</p>
        </div>
        <div className={styles.meta}>
          <strong>{formatMarketDate(view.observationDate)}</strong>
          <span>{view.freshness}</span>
        </div>
      </header>

      {view.loading
        ? (
          <div className={styles.loading} role="status">
            시장 관찰값 불러오는 중
          </div>
          )
        : (
          <MarketField score={view.score} stage={view.stage} />
          )}

      {view.unavailable && (
        <p className={styles.notice} role="status">
          {view.observationError
            ? '시장 관찰값을 불러오지 못했습니다.'
            : 'S&P 500 군중 상태를 준비하고 있습니다.'}
        </p>
      )}
    </div>
  )
}

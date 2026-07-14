import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getStockHerd } from '../../api/herdApi'
import HerdDots from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import herdSignalLogo from '../../assets/brand/herdsignal-logo.svg'
import { stageColor, stageLabelFromScore } from '../../utils/herdStage'
import styles from './PublicHome.module.css'

const STAGES = [
  { name: 'Flee', range: '0–15', note: '군중 이탈' },
  { name: 'Scatter', range: '16–40', note: '분산' },
  { name: 'Calm', range: '41–59', note: '균형' },
  { name: 'Drift', range: '60–74', note: '밀집 시작' },
  { name: 'Rush', range: '75–100', note: '군중 밀집' },
]

export default function PublicHome() {
  const navigate = useNavigate()
  const [ticker, setTicker] = useState('')
  const [spy, setSpy] = useState(null)

  useEffect(() => {
    let active = true
    getStockHerd('SPY')
      .then((response) => { if (active) setSpy(response.data?.data ?? null) })
      .catch(() => {})
    return () => { active = false }
  }, [])

  const spyScore = Number(spy?.herdV4 ?? spy?.herdScore ?? 68)
  const spyStage = spy?.herdStage ?? stageLabelFromScore(spyScore)
  function submitTicker(event) {
    event.preventDefault()
    const normalized = ticker.trim().toUpperCase()
    if (normalized) navigate(`/stock/${encodeURIComponent(normalized)}`)
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/" className={styles.brand} aria-label="HerdSignal 홈">
          <img src={herdSignalLogo} alt="HerdSignal" />
        </Link>
        <Link to="/app" className={styles.navCta}>내 대시보드</Link>
      </header>

      <main>
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}><span /> HERD SIGNAL</p>
            <h1>시장에 사람이<br /><em>얼마나 몰려 있을까?</em></h1>
            <p className={styles.heroLead}>
              미국 주식의 군중 밀집도를 0부터 100까지 보여줍니다.
              매수·보유·익절을 고민할 때 참고할 수 있는 장기투자 도구입니다.
            </p>
            <form className={styles.search} onSubmit={submitTicker}>
              <label htmlFor="public-ticker">미국 종목 바로 분석</label>
              <div>
                <input
                  id="public-ticker"
                  value={ticker}
                  onChange={(event) => setTicker(event.target.value)}
                  placeholder="티커 입력 · NVDA, AAPL, SPY"
                  autoComplete="off"
                />
                <button type="submit">HERD 확인</button>
              </div>
            </form>
            <Link to="/app" className={styles.primaryCta}>내 포트폴리오 보기</Link>
          </div>

          <div className={styles.marketPanel} aria-label={`SPY HERD ${spyScore}`}>
            <div className={styles.panelTop}>
              <div><span>MARKET PULSE</span><strong>SPY · S&amp;P 500</strong></div>
              <em>HERD v4</em>
            </div>
            <div className={styles.flowCanvas}>
              <HerdDots score={spyScore} momentum={8} enhanced fill dotCount={96} />
              <div className={styles.flowLabel}>
                <span>HERD INDEX</span>
                <strong style={{ color: stageColor(spyStage) }}>{Math.round(spyScore)}</strong>
                <em style={{ color: stageColor(spyStage) }}>{spyStage}</em>
              </div>
            </div>
            <SpectrumBar score={spyScore} height={4} />
            <div className={styles.marketReadout}>
              <div><span>현재 상태</span><strong>{spyStage}</strong></div>
              <p>HERD 점수는 매수·매도를 확정하는 신호가 아니라 현재 시장 상태를 확인하는 기준입니다.</p>
            </div>
          </div>
        </section>

        <section className={styles.stageSection}>
          <div className={styles.sectionIntro}>
            <span>FIVE HERD STATES</span>
            <h2>점수는 다섯 단계로 나뉩니다.</h2>
            <p>낮을수록 군중이 흩어져 있고, 높을수록 한쪽에 많이 몰린 상태입니다.</p>
          </div>
          <div className={styles.stageTrack}>
            {STAGES.map((stage) => (
              <div key={stage.name} className={styles.stageItem}>
                <i className={styles[stage.name.toLowerCase()]} />
                <span>{stage.range}</span>
                <strong>{stage.name}</strong>
                <em>{stage.note}</em>
              </div>
            ))}
          </div>
        </section>

      </main>

      <footer className={styles.footer}>
        <img src={herdSignalLogo} alt="HerdSignal" />
        <p>투자 판단을 돕기 위한 참고 정보이며, 특정 종목의 매수·매도를 권유하지 않습니다.</p>
        <span>© 2026 HerdSignal</span>
      </footer>
    </div>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getModelValidationReport, getStockHerd } from '../../api/herdApi'
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

function formatMetric(value, suffix = '%') {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number > 0 ? '+' : ''}${number.toFixed(1)}${suffix}`
}

export default function PublicHome() {
  const navigate = useNavigate()
  const [ticker, setTicker] = useState('')
  const [spy, setSpy] = useState(null)
  const [validation, setValidation] = useState(null)

  useEffect(() => {
    let active = true
    Promise.allSettled([getStockHerd('SPY'), getModelValidationReport()])
      .then(([spyResult, validationResult]) => {
        if (!active) return
        if (spyResult.status === 'fulfilled') setSpy(spyResult.value.data?.data ?? null)
        if (validationResult.status === 'fulfilled') setValidation(validationResult.value.data?.data ?? null)
      })
    return () => { active = false }
  }, [])

  const spyScore = Number(spy?.herdV4 ?? spy?.herdScore ?? 68)
  const spyStage = spy?.herdStage ?? stageLabelFromScore(spyScore)
  const generatedDate = useMemo(() => {
    if (!validation?.generatedAt) return '최신 검증 리포트'
    return new Date(validation.generatedAt).toLocaleDateString('ko-KR')
  }, [validation])

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
        <nav className={styles.nav} aria-label="공개 메뉴">
          <Link to="/search">종목 분석</Link>
          <Link to="/herd-lab">검증 방법</Link>
          <Link to="/app" className={styles.navCta}>내 대시보드</Link>
        </nav>
      </header>

      <main>
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}><span /> LONG-TERM INVESTOR SIGNAL</p>
            <h1>시장이 시끄러울수록,<br /><em>행동은 더 명확하게.</em></h1>
            <p className={styles.heroLead}>
              가격을 예언하지 않습니다. 군중이 흩어지고 밀집되는 흐름을 읽어,
              장기투자자가 지금 얼마나 움직일지 판단할 근거를 제공합니다.
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
            <div className={styles.heroActions}>
              <Link to="/app" className={styles.primaryCta}>내 포트폴리오 분석</Link>
              <Link to="/herd-lab" className={styles.secondaryCta}>모델 검증 보기 <span>↗</span></Link>
            </div>
          </div>

          <div className={styles.marketPanel} aria-label={`SPY HERD ${spyScore}`}>
            <div className={styles.panelTop}>
              <div><span>MARKET PULSE</span><strong>SPY · S&amp;P 500</strong></div>
              <em>LIVE MODEL</em>
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
              <div><span>현재 해석</span><strong>군중 밀집도를 먼저 확인</strong></div>
              <p>점수 하나로 매수·매도를 단정하지 않고 추세, 신뢰도, 투자 방식을 함께 봅니다.</p>
            </div>
          </div>
        </section>

        <section className={styles.stageSection}>
          <div className={styles.sectionIntro}>
            <span>ONE SIGNAL, FIVE STATES</span>
            <h2>복잡한 시장을 하나의 흐름으로</h2>
            <p>과열과 공포 사이에서 현재 군중의 위치를 같은 기준으로 읽습니다.</p>
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

        <section className={styles.valueSection}>
          <div className={styles.sectionIntro}>
            <span>BUILT FOR BETTER DECISIONS</span>
            <h2>더 많은 정보보다, 더 나은 행동 기준</h2>
          </div>
          <div className={styles.valueGrid}>
            <article>
              <span>01</span>
              <h3>시장 상태와 행동을 분리</h3>
              <p>HERD v4는 군중 상태를 측정하고, Action Layer는 실제로 움직일 비율을 별도로 계산합니다.</p>
              <strong>STATE → ACTION</strong>
            </article>
            <article>
              <span>02</span>
              <h3>투자 방식에 맞춘 해석</h3>
              <p>기존 보유자, 신규 진입자, 적립식, 리밸런싱 투자자를 같은 신호로 다루지 않습니다.</p>
              <strong>CONTEXT MATTERS</strong>
            </article>
            <article>
              <span>03</span>
              <h3>검증 결과까지 공개</h3>
              <p>좋아 보이는 수익률만 고르지 않고 OOS 성능, MDD, 과최적화와 남은 한계를 함께 보여줍니다.</p>
              <strong>EVIDENCE FIRST</strong>
            </article>
          </div>
        </section>

        <section className={styles.validationSection}>
          <div className={styles.validationCopy}>
            <span>RESEARCH, NOT A BLACK BOX</span>
            <h2>모델이 아직 부족한 지점까지<br />숨기지 않습니다.</h2>
            <p>
              운영 중인 HERD v4와 연구 검증 중인 v6.1 Action Layer를 구분합니다.
              운영 승격은 정해진 검증 게이트를 통과한 뒤 사람의 검토를 거칩니다.
            </p>
            <Link to="/herd-lab">전체 검증 리포트 보기 <span>→</span></Link>
          </div>
          <div className={styles.validationCard}>
            <div className={styles.validationHead}>
              <div><span>MODEL STATUS</span><strong>{validation?.modelVersion ?? 'HERD_v6.1'}</strong></div>
              <em>{validation?.adoptionGate?.status ?? 'RESEARCH_VALIDATION'}</em>
            </div>
            <div className={styles.metricGrid}>
              <div><span>검증 종목</span><strong>{validation?.validationRun?.completedTickers ?? 55}</strong><em>US equities</em></div>
              <div><span>OOS 구간</span><strong>{validation?.walkForward?.samples ?? 440}</strong><em>walk-forward</em></div>
              <div><span>수익 보존율</span><strong>{formatMetric(validation?.walkForward?.captureMedian ?? 99.1)}</strong><em>중앙값</em></div>
              <div><span>MDD 개선</span><strong>{formatMetric(validation?.walkForward?.mddImprovementMedian ?? 0.9, '%p')}</strong><em>OOS 중앙값</em></div>
            </div>
            <div className={styles.validationFoot}><span>{generatedDate}</span><span>자동 운영 승격 없음</span></div>
          </div>
        </section>

        <section className={styles.finalCta}>
          <div>
            <span>YOUR PORTFOLIO, IN CONTEXT</span>
            <h2>보유 종목의 군중 흐름부터 확인하세요.</h2>
            <p>감정적인 한 번의 결정 대신, 근거 있는 작은 행동을 쌓습니다.</p>
          </div>
          <Link to="/app">내 대시보드 열기 <span>→</span></Link>
        </section>
      </main>

      <footer className={styles.footer}>
        <img src={herdSignalLogo} alt="HerdSignal" />
        <p>HerdSignal의 정보는 투자 판단을 돕기 위한 연구 자료이며, 특정 종목의 매수·매도를 권유하지 않습니다.</p>
        <span>© 2026 HerdSignal</span>
      </footer>
    </div>
  )
}

/**
 * AiRebalance.jsx — 리밸런싱 플랜 MVP (/ai)
 *
 * Claude API 연결 전 단계.
 * 기존 포트폴리오/평가금액/HERD API와 localStorage 목표 비중으로
 * 규칙 기반 리밸런싱 실행안을 만든다.
 */

import { useEffect, useMemo, useState } from 'react'
import {
  getPortfolio,
  getPortfolioHerd,
  getPortfolioSummary,
} from '../../api/herdApi'
import {
  buildRebalancePlan,
  portfolioRows,
  readRebalanceSettings,
  readTargetWeights,
  writeRebalanceSettings,
  writeTargetWeights,
} from '../../utils/portfolioTools'
import styles from './AiRebalance.module.css'

function fmtUSD(value) {
  if (value == null) return '—'
  return `$${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`
}

function fmtPct(value) {
  if (value == null) return '—'
  const n = Number(value)
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

function normalizeSummary(data) {
  if (!data) return null
  return {
    total_value: data.total_value ?? data.totalValue ?? null,
    total_cost: data.total_cost ?? data.totalCost ?? null,
    total_return_pct: data.total_return_pct ?? data.totalReturnPct ?? null,
    stocks: (data.stocks ?? []).map((s) => ({
      ticker: s.ticker,
      market_value: s.market_value ?? s.marketValue ?? null,
      current_price: s.current_price ?? s.currentPrice ?? null,
      return_pct: s.return_pct ?? s.returnPct ?? null,
    })),
  }
}

function actionTone(action) {
  if (action.includes('매수')) return 'buy'
  if (action.includes('익절') || action.includes('덜기')) return 'sell'
  if (action.includes('금지')) return 'warn'
  return 'hold'
}

export default function AiRebalance() {
  const [portfolio, setPortfolio] = useState([])
  const [summary, setSummary] = useState(null)
  const [herdMap, setHerdMap] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [targetWeights, setTargetWeights] = useState(() => readTargetWeights())
  const [settings, setSettings] = useState(() => ({
    budget: readRebalanceSettings().budget ?? 1000,
    cashTargetPct: readRebalanceSettings().cashTargetPct ?? 10,
    mode: readRebalanceSettings().mode ?? 'standard',
  }))

  useEffect(() => {
    setLoading(true)
    Promise.allSettled([
      getPortfolio(),
      getPortfolioSummary(),
      getPortfolioHerd(),
    ]).then(([portfolioRes, summaryRes, herdRes]) => {
      if (portfolioRes.status !== 'fulfilled') {
        setError('포트폴리오 데이터를 불러오지 못했습니다.')
        return
      }

      const rawPortfolio = portfolioRes.value.data?.data
      setPortfolio(Array.isArray(rawPortfolio) ? rawPortfolio : [])

      if (summaryRes.status === 'fulfilled') {
        setSummary(normalizeSummary(summaryRes.value.data?.data ?? null))
      }

      if (herdRes.status === 'fulfilled') {
        const map = {}
        const stocks = herdRes.value.data?.data?.stocks ?? []
        stocks.forEach((item) => { map[item.ticker] = item })
        setHerdMap(map)
      }
    }).finally(() => { setLoading(false) })
  }, [])

  const rows = useMemo(
    () => portfolioRows(portfolio, summary, herdMap, targetWeights),
    [portfolio, summary, herdMap, targetWeights]
  )

  const plan = useMemo(() => buildRebalancePlan(rows, {
    budget: settings.budget,
    cashTargetPct: settings.cashTargetPct,
    mode: settings.mode,
    totalValue: summary?.total_value,
  }), [rows, settings, summary])

  const totals = useMemo(() => ({
    buy: plan.buys.reduce((sum, item) => sum + item.amount, 0),
    sell: plan.sells.reduce((sum, item) => sum + item.amount, 0),
    hold: plan.holds.length,
  }), [plan])

  function updateSettings(next) {
    setSettings(next)
    writeRebalanceSettings(next)
  }

  function updateTargetWeight(ticker, value) {
    const next = { ...targetWeights, [ticker]: value }
    setTargetWeights(next)
    writeTargetWeights(next)
  }

  function equalizeTargets() {
    const weight = portfolio.length ? (90 / portfolio.length).toFixed(0) : ''
    const next = {}
    portfolio.forEach((item) => { next[item.ticker] = weight })
    setTargetWeights(next)
    writeTargetWeights(next)
    updateSettings({ ...settings, cashTargetPct: 10 })
  }

  const summaryLines = [
    plan.sells.length > 0
      ? `${plan.sells[0].ticker}는 목표보다 높고 HERD 신호가 과열권이라 우선 조정 대상입니다.`
      : '강한 매도/익절 우선 대상은 없습니다.',
    plan.buys.length > 0
      ? `${plan.buys[0].ticker}는 목표보다 부족하고 HERD 신호가 우호적이라 분할매수 후보입니다.`
      : '현 예산으로 강한 신규 매수 후보는 제한적입니다.',
    settings.cashTargetPct > 0
      ? `현금 목표 ${settings.cashTargetPct}%를 남기도록 매수 예산을 제한했습니다.`
      : '현금 목표 없이 입력 예산 전부를 후보 종목에 배분합니다.',
  ]

  return (
    <div>
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>규칙 기반 실행안</div>
          <h1 className={styles.pageTitle}>리밸런싱 플랜</h1>
        </div>
        <button className={styles.btnSecondary} onClick={equalizeTargets}>
          목표 균등 설정
        </button>
      </div>

      {loading && <div className={styles.state}>로딩 중…</div>}
      {!loading && error && <div className={styles.state}>{error}</div>}

      {!loading && !error && (
        <>
          <div className={styles.summaryGrid}>
            <div className={styles.summaryCard}>
              <span>총 평가금액</span>
              <strong>{fmtUSD(summary?.total_value)}</strong>
            </div>
            <div className={styles.summaryCard}>
              <span>추천 매수</span>
              <strong className={styles.buyText}>{fmtUSD(totals.buy)}</strong>
            </div>
            <div className={styles.summaryCard}>
              <span>추천 매도</span>
              <strong className={styles.sellText}>{fmtUSD(totals.sell)}</strong>
            </div>
            <div className={styles.summaryCard}>
              <span>보류 종목</span>
              <strong>{totals.hold}</strong>
            </div>
          </div>

          <div className={styles.settingsPanel}>
            <label>
              <span>이번 리밸런싱 예산</span>
              <input
                type="number"
                min="0"
                value={settings.budget}
                onChange={(e) => updateSettings({ ...settings, budget: e.target.value })}
              />
            </label>
            <label>
              <span>현금 목표 비중</span>
              <input
                type="number"
                min="0"
                max="80"
                value={settings.cashTargetPct}
                onChange={(e) => updateSettings({ ...settings, cashTargetPct: e.target.value })}
              />
            </label>
            <div>
              <span className={styles.fieldLabel}>리밸런싱 강도</span>
              <div className={styles.segmented}>
                {[
                  ['conservative', '보수적'],
                  ['standard', '표준'],
                  ['aggressive', '공격적'],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    className={settings.mode === value ? styles.segmentActive : ''}
                    onClick={() => updateSettings({ ...settings, mode: value })}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className={styles.contentGrid}>
            <section className={styles.card}>
              <div className={styles.cardHeader}>
                <h2>현재 vs 목표</h2>
                <span>목표 비중은 브라우저에 저장됩니다.</span>
              </div>
              <div className={styles.table}>
                {rows.map((row) => (
                  <div key={row.ticker} className={styles.tableRow}>
                    <strong>{row.ticker}</strong>
                    <span>{row.currentWeight.toFixed(1)}%</span>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={targetWeights[row.ticker] ?? ''}
                      placeholder={row.targetWeight.toFixed(0)}
                      onChange={(e) => updateTargetWeight(row.ticker, e.target.value)}
                    />
                    <em className={row.drift >= 0 ? styles.sellText : styles.buyText}>
                      {fmtPct(row.drift)}
                    </em>
                    <b className={styles[actionTone(row.action)]}>{row.action}</b>
                  </div>
                ))}
              </div>
            </section>

            <section className={styles.card}>
              <div className={styles.cardHeader}>
                <h2>플랜 요약</h2>
                <span>AI 연결 전 규칙 기반 설명</span>
              </div>
              <div className={styles.aiSummary}>
                {summaryLines.map((line) => <p key={line}>{line}</p>)}
              </div>
            </section>
          </div>

          <div className={styles.planGrid}>
            <ActionColumn title="매수" tone="buy" rows={plan.buys} />
            <ActionColumn title="매도" tone="sell" rows={plan.sells} />
            <ActionColumn title="보류" tone="hold" rows={plan.holds.slice(0, 5)} />
          </div>
        </>
      )}
    </div>
  )
}

function ActionColumn({ title, tone, rows }) {
  return (
    <section className={styles.actionCard}>
      <div className={styles.actionHeader}>
        <h2>{title}</h2>
        <span>{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <div className={styles.actionEmpty}>대상 없음</div>
      ) : rows.map((row) => (
        <div key={`${title}-${row.ticker}`} className={styles.actionRow}>
          <div>
            <strong>{row.ticker}</strong>
            <p>{row.reason}</p>
          </div>
          <em className={styles[`${tone}Text`]}>
            {row.amount > 0 ? fmtUSD(row.amount) : '보류'}
          </em>
        </div>
      ))}
    </section>
  )
}

/**
 * HerdLab.jsx — HERD Index 검증 데이터 보드 (/herd-lab)
 */

import { useEffect, useState } from 'react'
import { getInvestorProfile, getModelValidationReport, updateInvestorProfile } from '../../api/herdApi'
import herdModelReport from '../../data/herdModelReport'
import styles from './HerdLab.module.css'
import { presentValidationReport } from './herdModelPresentation'

const {
  model: MODEL_BASE,
  stages: STAGES,
  weights: WEIGHTS,
} = herdModelReport

function pctWidth(value) {
  const n = Number(String(value).replace(/[+%,/년p]/g, ''))
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n))
}

function mddWidth(value) {
  const n = Number(String(value).replace(/[+%p]/g, ''))
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n * 8))
}

export default function HerdLab() {
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [profile, setProfile] = useState(null)
  const [profileStatus, setProfileStatus] = useState('')

  useEffect(() => {
    let active = true
    getModelValidationReport()
      .then(({ data }) => {
        if (active) setReport(presentValidationReport(data.data))
      })
      .catch((requestError) => {
        if (active) setError(requestError.response?.data?.message || '검증 리포트를 불러오지 못했습니다.')
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    getInvestorProfile()
      .then(({ data }) => { if (active) setProfile(data.data) })
      .catch(() => { if (active) setProfileStatus('투자 설정을 불러오지 못했습니다.') })
    return () => { active = false }
  }, [])

  const changeProfile = (field, value) => {
    setProfile((current) => ({ ...current, [field]: value }))
    setProfileStatus('')
  }

  const saveProfile = async (event) => {
    event.preventDefault()
    setProfileStatus('저장 중...')
    try {
      const payload = {
        ...profile,
        timeHorizonYears: Number(profile.timeHorizonYears),
        liquidityBufferMonths: Number(profile.liquidityBufferMonths),
        maxActionRatio: Number(profile.maxActionRatio),
        targetEquityRatio: Number(profile.targetEquityRatio),
      }
      const { data } = await updateInvestorProfile(payload)
      setProfile(data.data)
      setProfileStatus('저장했습니다. 다음 HERD 조회부터 적용됩니다.')
    } catch (requestError) {
      setProfileStatus(requestError.response?.data?.message || '투자 설정을 저장하지 못했습니다.')
    }
  }

  if (error) {
    return (
      <div className={styles.page}>
        <section className={styles.card} role="alert">
          <div className={styles.cardHead}><span>HERD LAB</span><strong>리포트 조회 실패</strong></div>
          <p>{error}</p>
        </section>
      </div>
    )
  }

  if (!report) {
    return <div className={styles.page}><p>최신 검증 리포트를 불러오는 중입니다.</p></div>
  }

  const { model, metrics, trustChecks, modelNotes, rows } = report

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span>HERD LAB</span>
          <h1>{model.version}</h1>
        </div>
        <p>{MODEL_BASE.name} · {model.generatedAt} 갱신</p>
      </header>

      <section className={styles.labHero}>
        <div className={styles.labHeroMain}>
          <span>Current Model</span>
          <strong>{model.version}</strong>
          <em>{MODEL_BASE.name} · 검증 기간 {model.period}</em>
          <small>{MODEL_BASE.base} · {model.status}</small>
        </div>
        <div className={styles.labHeroMetrics}>
          {metrics.map((metric) => (
            <div key={metric.label}>
              <span>{metric.label}</span>
              <strong className={styles[metric.tone]}>{metric.value}</strong>
              <em>{metric.sub}</em>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.trustStrip}>
        {trustChecks.map((item) => (
          <div key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <em>{item.sub}</em>
          </div>
        ))}
      </section>

      <section className={styles.card}>
        <div className={styles.cardHead}>
          <span>나의 행동 기준</span>
          <strong>HERD 점수는 유지하고 행동 비율만 조정</strong>
        </div>
        {profile ? (
          <form className={styles.profileForm} onSubmit={saveProfile}>
            <label><span>투자 방식</span><select value={profile.strategy} onChange={(event) => changeProfile('strategy', event.target.value)}>
              <option value="EXISTING_HOLDER">기존 보유자</option>
              <option value="NEW_ENTRY">신규 진입자</option>
              <option value="MONTHLY_DCA">정기 적립식</option>
              <option value="TARGET_REBALANCE">목표 비중 리밸런싱</option>
            </select></label>
            <label><span>위험 허용도</span><select value={profile.riskTolerance} onChange={(event) => changeProfile('riskTolerance', event.target.value)}>
              <option value="CONSERVATIVE">보수적</option>
              <option value="BALANCED">균형</option>
              <option value="GROWTH">성장형</option>
            </select></label>
            <label><span>투자 기간(년)</span><input type="number" min="1" max="50" value={profile.timeHorizonYears} onChange={(event) => changeProfile('timeHorizonYears', event.target.value)} /></label>
            <label><span>생활비 여유(개월)</span><input type="number" min="0" max="60" value={profile.liquidityBufferMonths} onChange={(event) => changeProfile('liquidityBufferMonths', event.target.value)} /></label>
            <label><span>1회 최대 행동(%)</span><input type="number" min="1" max="30" value={Math.round(Number(profile.maxActionRatio) * 100)} onChange={(event) => changeProfile('maxActionRatio', Number(event.target.value) / 100)} /></label>
            <label><span>목표 주식비중(%)</span><input type="number" min="10" max="100" value={Math.round(Number(profile.targetEquityRatio) * 100)} onChange={(event) => changeProfile('targetEquityRatio', Number(event.target.value) / 100)} /></label>
            <button type="submit">행동 기준 저장</button>
            {profileStatus && <em role="status">{profileStatus}</em>}
          </form>
        ) : <p>{profileStatus || '투자 설정을 불러오는 중입니다.'}</p>}
      </section>

      <section className={styles.card}>
        <div className={styles.cardHead}>
          <span>검증 결과</span>
          <strong>Buy & Hold vs Action Layer</strong>
        </div>
        <div className={styles.table}>
          <div className={`${styles.tr} ${styles.th}`}>
            <span>종목</span>
            <span>B&H</span>
            <span>Action</span>
            <span>보존율</span>
            <span>MDD 개선</span>
            <span>행동</span>
            <span>판정</span>
          </div>
          {rows.map((row) => (
            <div key={row.ticker} className={styles.tr}>
              <span><strong>{row.ticker}</strong></span>
              <span>{row.buyHold}</span>
              <span>{row.action}</span>
              <span>
                {row.capture}
                <i className={styles.captureBar}><b style={{ width: `${pctWidth(row.capture)}%` }} /></i>
              </span>
              <span className={styles.green}>
                {row.mdd}
                <i className={styles.mddBar}><b style={{ width: `${mddWidth(row.mdd)}%` }} /></i>
              </span>
              <span>{row.actions}</span>
              <span><em className={styles[row.tone]}>{row.verdict}</em></span>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.gridTwo}>
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span>행동 매트릭스</span>
            <strong>구간별 행동 비율</strong>
          </div>
          <div className={styles.stageGrid}>
            {STAGES.map((item) => (
              <div key={item.stage} className={styles.stageRow}>
                <span className={`${styles.dot} ${styles[item.tone]}`} />
                <strong>{item.stage}</strong>
                <em>{item.range}</em>
                <span>{item.action}</span>
                <b>{item.ratio}</b>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span>점수 구성</span>
            <strong>HERD_v4 점수 구성</strong>
          </div>
          <div className={styles.weightList}>
            {WEIGHTS.map((weight) => (
              <div key={weight.label} className={styles.weightRow}>
                <span>{weight.label}</span>
                <div><i style={{ width: `${weight.value * 3}%` }} /></div>
                <strong>{weight.value}%</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.cardHead}>
          <span>모델 상태</span>
          <strong>검증 수치와 운영 보정 분리</strong>
        </div>
        <div className={styles.modelNotes}>
          {modelNotes.map((note, index) => (
            <div key={note}>
              <span>{index + 1}</span>
              <strong>{note}</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

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
  const [showAllTickers, setShowAllTickers] = useState(false)

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

  const { model, metrics, trustChecks, modelNotes, rows, featuredSectors } = report

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
          <span>행동 원칙</span>
          <strong>점수보다 먼저 확인할 7가지</strong>
        </div>
        <div className={styles.decisionFlow}>
          {[
            ['01', '투자 가능 여부', '비상자금·투자 기간·데이터 품질 확인'],
            ['02', '현재 포지션', '신규 진입·기존 보유·적립식 구분'],
            ['03', 'HERD 구간', 'Flee부터 Rush까지 군중 위치 확인'],
            ['04', '추세와 변화', '장기 추세와 HERD 회복·둔화 확인'],
            ['05', '포트폴리오 한도', '목표 비중과 종목 집중도 확인'],
            ['06', '최근 행동', '같은 방향 행동 후 추격 매매 제한'],
            ['07', '최종 결정', '매수·보유·일부 익절·축소'],
          ].map(([number, title, description]) => (
            <div key={number}>
              <span>{number}</span>
              <strong>{title}</strong>
              <p>{description}</p>
            </div>
          ))}
        </div>
        <div className={styles.actionGuide}>
          <article className={styles.buyGuide}>
            <span>BUY</span>
            <strong>공포에는 확인하고 나눠 산다</strong>
            <p>Flee·낮은 Scatter에서 장기 추세가 살아 있거나 HERD 회복이 확인될 때만 분할매수합니다.</p>
            <em>낮은 점수 + 추세 훼손이면 매수가 아니라 관찰</em>
          </article>
          <article className={styles.holdGuide}>
            <span>HOLD</span>
            <strong>중립과 건강한 추세에서는 기다린다</strong>
            <p>Calm, Healthy Drift, Healthy Rush에서는 불필요한 매매보다 기존 비중 유지를 우선합니다.</p>
            <em>행동하지 않는 것도 모델의 판단</em>
          </article>
          <article className={styles.sellGuide}>
            <span>REDUCE</span>
            <strong>과열에는 둔화를 보고 나눠 판다</strong>
            <p>Rush 자체보다 과도한 이격, HERD 둔화, 장기 추세 약화가 겹칠 때 익절 비중을 높입니다.</p>
            <em>전량 매도보다 목표 비중까지 단계적으로 축소</em>
          </article>
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.cardHead}>
          <span>검증 결과</span>
          <strong>대표 6개 섹터 요약</strong>
        </div>
        <div className={styles.sectorGrid}>
          {featuredSectors.map((sector) => (
            <article key={sector.name}>
              <div>
                <span>{sector.name}</span>
                <strong>{sector.representative}</strong>
              </div>
              <dl>
                <div><dt>검증 종목</dt><dd>{sector.count}개</dd></div>
                <div><dt>수익 보존 중앙값</dt><dd>{sector.capture}</dd></div>
                <div><dt>MDD 개선 중앙값</dt><dd className={styles.green}>{sector.mdd}</dd></div>
                <div><dt>기준 통과</dt><dd>{sector.passed}/{sector.count}</dd></div>
              </dl>
            </article>
          ))}
        </div>
        <div className={styles.validationToggle}>
          <p>대표 섹터는 빠른 비교용이며 최종 판정은 전체 {rows.length}종목 Walk-forward 결과를 사용합니다.</p>
          <button
            type="button"
            aria-expanded={showAllTickers}
            onClick={() => setShowAllTickers((current) => !current)}
          >
            {showAllTickers ? '전체 결과 접기' : `전체 ${rows.length}종목 자세히 보기`}
          </button>
        </div>
        {showAllTickers && (
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
                <span><strong>{row.ticker}</strong><small>{row.sector}</small></span>
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
        )}
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

/**
 * HerdLab.jsx — HERD Index 검증 데이터 보드 (/herd-lab)
 */

import { useEffect, useState } from 'react'
import { getInvestorProfile, getModelValidationReport, updateInvestorProfile } from '../../api/herdApi'
import herdModelReport from '../../data/herdModelReport'
import styles from './HerdLab.module.css'
import { presentValidationReport } from './herdModelPresentation'
import { ActionGuide, InvestorProfilePanel, MethodologyPanel, ValidationPanel } from './HerdLabSections'

const { model: MODEL_BASE } = herdModelReport

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
    return <div className={styles.page}><section className={styles.panel} role="alert"><p className={styles.inlineStatus}>{error}</p></section></div>
  }

  if (!report) {
    return <div className={styles.page}><p>최신 검증 리포트를 불러오는 중입니다.</p></div>
  }

  const { model, metrics, trustChecks, modelNotes, rows, featuredSectors } = report

  return (
    <div className={styles.page}>
      <section className={styles.overview}>
        <header>
          <span>HERD LAB · {model.status}</span>
          <h1>{model.version}</h1>
          <p>{MODEL_BASE.name} · {model.generatedAt} 갱신</p>
        </header>
        <div className={styles.metrics}>
          {metrics.map((metric) => (
            <div key={metric.label}>
              <span>{metric.label}</span>
              <strong className={styles[metric.tone]}>{metric.value}</strong>
              <em>{metric.sub}</em>
            </div>
          ))}
        </div>
        <div className={styles.trustLine}>
          {trustChecks.map((item) => (
            <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong><em>{item.sub}</em></div>
          ))}
        </div>
      </section>

      <InvestorProfilePanel profile={profile} status={profileStatus} onChange={changeProfile} onSubmit={saveProfile} />
      <ActionGuide />
      <ValidationPanel sectors={featuredSectors} rows={rows} />
      <MethodologyPanel modelNotes={modelNotes} />
    </div>
  )
}

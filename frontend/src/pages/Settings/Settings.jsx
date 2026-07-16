import { useEffect, useState } from 'react'
import { getInvestorProfile, updateInvestorProfile } from '../../api/herdApi'
import { ActionGuide, InvestorProfilePanel } from '../HerdLab/HerdLabSections'
import styles from './Settings.module.css'

export default function Settings() {
  const [profile, setProfile] = useState(null)
  const [status, setStatus] = useState('')

  useEffect(() => {
    let active = true
    getInvestorProfile()
      .then(({ data }) => { if (active) setProfile(data.data) })
      .catch(() => { if (active) setStatus('투자 설정을 불러오지 못했습니다.') })
    return () => { active = false }
  }, [])

  const changeProfile = (field, value) => {
    setProfile((current) => ({ ...current, [field]: value }))
    setStatus('')
  }

  const saveProfile = async (event) => {
    event.preventDefault()
    setStatus('저장 중...')
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
      setStatus('저장했습니다. 다음 HERD 조회부터 적용됩니다.')
    } catch (requestError) {
      setStatus(requestError.response?.data?.message || '투자 설정을 저장하지 못했습니다.')
    }
  }

  return (
    <div className={styles.page}>
      <header>
        <span>PERSONAL SETTINGS</span>
        <h1>나의 투자 기준</h1>
        <p>HERD 점수는 그대로 두고 행동 강도와 목표 비중에만 반영됩니다.</p>
      </header>
      <InvestorProfilePanel
        profile={profile}
        status={status}
        onChange={changeProfile}
        onSubmit={saveProfile}
      />
      <ActionGuide />
    </div>
  )
}

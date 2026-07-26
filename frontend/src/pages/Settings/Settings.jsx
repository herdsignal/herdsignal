import { useEffect, useState } from 'react'
import { getInvestorProfile, updateInvestorProfile } from '../../api/herdApi'
import InvestorProfilePanel from './InvestorProfilePanel'
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
      setStatus('저장했습니다. 현재 State S1 관찰값에는 영향을 주지 않습니다.')
    } catch (requestError) {
      setStatus(requestError.response?.data?.message || '투자 설정을 저장하지 못했습니다.')
    }
  }

  return (
    <div className={styles.page}>
      <header>
        <span>INVESTOR PROFILE</span>
        <h1>투자 프로필</h1>
        <p>투자 방식과 목표 비중을 기록합니다. State S1 계산에는 사용하지 않습니다.</p>
      </header>
      <InvestorProfilePanel
        profile={profile}
        status={status}
        onChange={changeProfile}
        onSubmit={saveProfile}
      />
    </div>
  )
}

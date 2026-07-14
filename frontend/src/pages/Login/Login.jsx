import { Link, useLocation } from 'react-router-dom'
import { googleLoginUrl } from '../../api/herdApi'
import herdSignalLogo from '../../assets/brand/herdsignal-logo.svg'
import styles from './Login.module.css'

export default function Login() {
  const location = useLocation()
  const failed = new URLSearchParams(location.search).get('error') === 'oauth'

  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <Link to="/" aria-label="HerdSignal 홈"><img src={herdSignalLogo} alt="HerdSignal" /></Link>
        <h1>내 포트폴리오 보기</h1>
        <p>포트폴리오와 투자 설정을 저장하려면 Google 계정으로 로그인하세요.</p>
        {failed && <div className={styles.error} role="alert">로그인을 완료하지 못했습니다. 다시 시도해 주세요.</div>}
        <a className={styles.googleButton} href={googleLoginUrl()}>
          <span>G</span> Google로 계속하기
        </a>
        <Link className={styles.back} to="/">홈으로 돌아가기</Link>
      </section>
    </main>
  )
}

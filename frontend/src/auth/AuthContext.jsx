import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { getCurrentUser, logout as requestLogout, prepareCsrf } from '../api/herdApi'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [authError, setAuthError] = useState(null)

  useEffect(() => {
    let active = true
    prepareCsrf()
      .catch(() => null)
      .then(() => getCurrentUser())
      .then(({ data }) => { if (active) setUser(data.data) })
      .catch(() => {
        if (active) {
          setUser({ authenticated: false })
          setAuthError('로그인 상태를 확인하지 못했습니다.')
        }
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function signOut() {
    setAuthError(null)
    try {
      await requestLogout()
      setUser({ authenticated: false })
    } catch (error) {
      setAuthError('로그아웃하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      throw error
    }
  }

  const value = useMemo(() => ({ user, loading, authError, signOut }), [user, loading, authError])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth는 AuthProvider 안에서 사용해야 합니다.')
  return context
}

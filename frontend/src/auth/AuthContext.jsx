import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { getCurrentUser, logout as requestLogout, prepareCsrf } from '../api/herdApi'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    prepareCsrf()
      .catch(() => null)
      .then(() => getCurrentUser())
      .then(({ data }) => { if (active) setUser(data.data) })
      .catch(() => { if (active) setUser({ authenticated: false }) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function signOut() {
    await requestLogout()
    setUser({ authenticated: false })
  }

  const value = useMemo(() => ({ user, loading, signOut }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth는 AuthProvider 안에서 사용해야 합니다.')
  return context
}

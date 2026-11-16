import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  ApiRequestError,
  fetchMe,
  loginRequest,
  logoutRequest,
  setCsrfToken,
} from '@/lib/api'
import type { User } from '@/lib/types'

type AuthContextValue = {
  user: User | null
  loading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchMe()
      .then((current) => {
        if (!controller.signal.aborted) setUser(current)
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            caught instanceof ApiRequestError
              ? caught.message
              : 'The session could not be checked.',
          )
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setError(null)
    const current = await loginRequest(email, password)
    setUser(current)
  }, [])

  const logout = useCallback(async () => {
    await logoutRequest()
    setCsrfToken(null)
    setUser(null)
  }, [])

  const refresh = useCallback(async () => {
    const current = await fetchMe()
    setUser(current)
  }, [])

  const value = useMemo(
    () => ({ user, loading, error, login, logout, refresh }),
    [user, loading, error, login, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

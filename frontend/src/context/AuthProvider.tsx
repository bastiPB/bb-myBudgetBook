import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { getMe } from '../api/auth'
import type { UserRead } from '../types/user'
import { AuthContext } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  return (
    <AuthContext.Provider value={{ user, setUser, loading }}>
      {children}
    </AuthContext.Provider>
  )
}
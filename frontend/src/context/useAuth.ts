import { useContext } from 'react'

import { AuthContext } from './AuthContext'

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth() muss innerhalb von <AuthProvider> verwendet werden')
  return ctx
}
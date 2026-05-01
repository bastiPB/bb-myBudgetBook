import { createContext } from 'react'

import type { UserRead } from '../types/user'

export interface AuthContextType {
  user: UserRead | null
  setUser: (user: UserRead | null) => void
  loading: boolean
}

export const AuthContext = createContext<AuthContextType | null>(null)
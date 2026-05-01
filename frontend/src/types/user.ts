// Spiegelt die Backend-Schemas (schemas/user.py) als TypeScript-Typen.
// Wenn sich das Backend ändert, müssen diese Typen mitgepflegt werden.

export type UserRole = 'admin' | 'editor' | 'default'
export type UserStatus = 'pending' | 'active'

export interface UserRead {
  id: string
  email: string
  role: UserRole
  status: UserStatus
}

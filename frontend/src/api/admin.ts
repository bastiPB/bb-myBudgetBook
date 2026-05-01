// admin.ts — API-Aufrufe für den Admin-Bereich.
// Nur erreichbar für User mit Rolle "admin" (Backend prüft das).
import type { UserRead, UserRole } from '../types/user'

// Dieselbe Hilfsfunktion wie in auth.ts und subscriptions.ts.
// fetch + Fehlerbehandlung + JSON-Parsing.
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? `HTTP ${response.status}`)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

// Einen neuen User direkt anlegen (sofort active, Admin wählt Rolle und Passwort).
export async function createUser(email: string, password: string, role: UserRole): Promise<UserRead> {
  return apiFetch<UserRead>('/admin/users', {
    method: 'POST',
    body: JSON.stringify({ email, password, role }),
  })
}

// Alle registrierten User laden (sortiert nach Registrierungsdatum).
export async function getUsers(): Promise<UserRead[]> {
  return apiFetch<UserRead[]>('/admin/users')
}

// Einen pending User freigeben → status wechselt zu "active".
export async function approveUser(userId: string): Promise<UserRead> {
  return apiFetch<UserRead>(`/admin/users/${userId}/approve`, { method: 'POST' })
}

// Die Rolle eines Users ändern (admin / editor / default).
export async function updateUserRole(userId: string, role: UserRole): Promise<UserRead> {
  return apiFetch<UserRead>(`/admin/users/${userId}/role`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  })
}

// Einen User unwiderruflich löschen (inkl. aller seiner Abos).
export async function deleteUser(userId: string): Promise<void> {
  return apiFetch<void>(`/admin/users/${userId}`, { method: 'DELETE' })
}

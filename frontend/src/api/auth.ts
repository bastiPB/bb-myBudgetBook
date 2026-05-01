// Alle API-Aufrufe rund um Authentifizierung.
// Nur diese Datei darf fetch() für /auth-Endpunkte aufrufen — nirgendwo sonst.
import type { UserRead } from '../types/user'

// Hilfsfunktion: fetch + JSON + Fehlerbehandlung in einem.
// Alle API-Aufrufe gehen durch diese Funktion.
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    // credentials: 'include' ist PFLICHT — ohne das schickt der Browser keine Cookies mit!
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })

  if (!response.ok) {
    // Fehlermeldung aus dem Backend-JSON lesen (Feld "detail"), sonst generischer Text
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? `HTTP ${response.status}`)
  }

  // HTTP 204 No Content (z.B. Logout) hat keinen Body — undefined zurückgeben
  if (response.status === 204) return undefined as T

  return response.json()
}

// Neuen Account registrieren — kein Cookie, da Account zuerst auf Admin-Freigabe wartet.
// Gibt eine Statusmeldung zurück (kein UserRead, da noch pending).
export async function registerUser(email: string, password: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

// Benutzer einloggen — der Browser speichert den Session-Cookie automatisch.
export async function loginUser(email: string, password: string): Promise<UserRead> {
  return apiFetch<UserRead>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

// Benutzer ausloggen — löscht den Session-Cookie.
export async function logoutUser(): Promise<void> {
  return apiFetch<void>('/auth/logout', { method: 'POST' })
}

// Prüft ob man noch eingeloggt ist und gibt die User-Daten zurück.
// Nützlich beim Seitenreload: war ich vorher eingeloggt?
export async function getMe(): Promise<UserRead> {
  return apiFetch<UserRead>('/auth/me')
}

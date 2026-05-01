// Alle API-Aufrufe rund um systemweite Einstellungen.
// Nur diese Datei darf fetch() für /settings-Endpunkte aufrufen.

// Typ-Definition: was das Backend zurückgibt (entspricht AppSettingsRead im Backend)
export interface SystemSettings {
  id: string
  email_signup_enabled: boolean
  // Welche Module systemweit verfügbar sind — Key = Modul-Key, Value = true/false
  modules: Record<string, boolean>
}

// Typ-Definition: was bei PATCH mitgeschickt wird (entspricht AppSettingsUpdate im Backend)
// Alle Felder optional — nur die mitgeschickten werden geändert
export interface SystemSettingsUpdate {
  email_signup_enabled?: boolean
  modules?: Record<string, boolean>
}

// Dieselbe Hilfsfunktion wie in auth.ts — fetch + JSON + Fehlerbehandlung.
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

// Systemweite Einstellungen lesen (GET /settings).
// Wird im ModulesProvider für Stufe 1 der Zwei-Stufen-Sichtbarkeit verwendet.
export async function fetchSystemSettings(): Promise<SystemSettings> {
  return apiFetch<SystemSettings>('/settings')
}

// Systemweite Einstellungen aktualisieren (PATCH /settings) — nur Admin.
// Wird auf der Admin-Settings-Seite verwendet (Schritt 7).
export async function patchSystemSettings(payload: SystemSettingsUpdate): Promise<SystemSettings> {
  return apiFetch<SystemSettings>('/settings', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

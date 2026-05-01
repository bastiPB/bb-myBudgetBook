// Alle API-Aufrufe rund um persönliche Profil-Einstellungen.
// Nur diese Datei darf fetch() für /profile-Endpunkte aufrufen.

// Typ-Definition: was das Backend zurückgibt (entspricht ProfileSettingsRead im Backend)
export interface ProfileSettings {
  display_name: string | null
  avatar_url: string | null
  // Persönliche Modul-Auswahl — Key = Modul-Key, Value = true/false
  modules: Record<string, boolean>
}

// Typ-Definition: was bei PATCH mitgeschickt wird (entspricht ProfileSettingsUpdate im Backend)
// Alle Felder optional — nur die mitgeschickten werden geändert
export interface ProfileSettingsUpdate {
  display_name?: string | null
  avatar_url?: string | null
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

// Persönliche Einstellungen lesen (GET /profile/settings).
// Wird im ModulesProvider für Stufe 2 der Zwei-Stufen-Sichtbarkeit verwendet.
// Legt die Profil-Zeile lazy an, falls sie noch nicht existiert (get_or_create im Backend).
export async function fetchProfileSettings(): Promise<ProfileSettings> {
  return apiFetch<ProfileSettings>('/profile/settings')
}

// Persönliche Einstellungen aktualisieren (PATCH /profile/settings).
// Wird auf der Profile-Settings-Seite verwendet (Schritt 8).
export async function patchProfileSettings(payload: ProfileSettingsUpdate): Promise<ProfileSettings> {
  return apiFetch<ProfileSettings>('/profile/settings', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

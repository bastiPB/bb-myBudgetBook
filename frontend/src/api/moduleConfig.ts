// Alle API-Aufrufe rund um Modul-Konfigurationen.
// Nur diese Datei darf fetch() für /profile/module-config aufrufen.

import type { UserModuleConfig, UserModuleConfigUpdate } from '../types/moduleConfig'

// Hilfsfunktion: fetch + JSON-Parsing + Fehlerbehandlung.
// Gleiches Muster wie in anderen api/-Dateien.
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body?.detail ?? `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

// Gibt die aktuelle Modul-Konfiguration des eingeloggten Users zurück.
export function getModuleConfig(): Promise<UserModuleConfig> {
  return apiFetch<UserModuleConfig>('/profile/module-config')
}

// Aktualisiert einzelne Felder der Modul-Konfiguration (PATCH-Semantik).
// Nur mitgeschickte Felder werden geändert.
export function updateModuleConfig(data: UserModuleConfigUpdate): Promise<UserModuleConfig> {
  return apiFetch<UserModuleConfig>('/profile/module-config', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

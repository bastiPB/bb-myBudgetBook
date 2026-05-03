// Alle API-Aufrufe rund um Abos.
import type {
  OverviewRead,
  PriceHistoryEntry,
  SubscriptionCreate,
  SubscriptionDetail,
  SubscriptionRead,
  SubscriptionUpdate,
  SuspendPayload,
} from '../types/subscription'

// Dieselbe Hilfsfunktion wie in auth.ts — fetch + JSON + Fehlerbehandlung.
// (Später könnten wir das in eine gemeinsame api/client.ts auslagern.)
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

// Alle Abos des eingeloggten Users laden.
export async function getSubscriptions(): Promise<SubscriptionRead[]> {
  return apiFetch<SubscriptionRead[]>('/subscriptions')
}

// Ein einzelnes Abo mit Kostenkennzahlen laden (Detailansicht — Slice C).
export async function getSubscription(id: string): Promise<SubscriptionDetail> {
  return apiFetch<SubscriptionDetail>(`/subscriptions/${id}`)
}

// Übersicht: Gesamtbetrag + demnächst fällige Abos.
export async function getOverview(): Promise<OverviewRead> {
  return apiFetch<OverviewRead>('/subscriptions/overview')
}

// Neues Abo anlegen.
export async function createSubscription(data: SubscriptionCreate): Promise<SubscriptionRead> {
  return apiFetch<SubscriptionRead>('/subscriptions', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Bestehendes Abo bearbeiten — nur die Felder die sich ändern.
export async function updateSubscription(id: string, data: SubscriptionUpdate): Promise<SubscriptionRead> {
  return apiFetch<SubscriptionRead>(`/subscriptions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

// Abo pausieren (Soft-Lifecycle: bleibt in der DB erhalten).
// access_until: optional — bis wann die Leistung noch nutzbar ist.
export async function suspendSubscription(id: string, payload: SuspendPayload): Promise<SubscriptionRead> {
  return apiFetch<SubscriptionRead>(`/subscriptions/${id}/suspend`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// Pausiertes Abo wieder fortsetzen — setzt Status zurück auf active.
export async function resumeSubscription(id: string): Promise<SubscriptionRead> {
  return apiFetch<SubscriptionRead>(`/subscriptions/${id}/resume`, { method: 'POST' })
}

// Abo löschen (Hard Delete).
export async function deleteSubscription(id: string): Promise<void> {
  return apiFetch<void>(`/subscriptions/${id}`, { method: 'DELETE' })
}

// Preishistorie eines Abos laden (Slice E) — neuester Eintrag zuerst.
export async function getPriceHistory(id: string): Promise<PriceHistoryEntry[]> {
  return apiFetch<PriceHistoryEntry[]>(`/subscriptions/${id}/price-history`)
}

// Baut die vollständige URL zu einem Logo aus dem relativen Pfad der DB.
// Beispiel: "logos/abc-123.png" → "/api/uploads/logos/abc-123.png"
// /api wird vom Vite-Dev-Proxy (und Nginx in Prod) zum Backend weitergeleitet,
// der den Pfad als /uploads/logos/abc-123.png an StaticFiles weitergibt.
export function getLogoUrl(logoUrl: string | null): string | null {
  if (!logoUrl) return null
  return `/api/uploads/${logoUrl}`
}

// Lädt ein Logo für ein Abo hoch (Multipart-Upload, Slice D).
// Gibt das aktualisierte Abo zurück — logo_url ist dann befüllt.
export async function uploadSubscriptionLogo(id: string, file: File): Promise<SubscriptionRead> {
  const fd = new FormData()
  fd.append('logo', file)
  // Kein Content-Type Header — Browser setzt multipart/form-data mit boundary automatisch.
  // apiFetch würde application/json setzen, daher hier direkt fetch verwenden.
  const response = await fetch(`/api/subscriptions/${id}/logo`, {
    method: 'POST',
    credentials: 'include',
    body: fd,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${response.status}`)
  }
  return response.json() as Promise<SubscriptionRead>
}

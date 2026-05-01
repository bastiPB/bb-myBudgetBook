// Alle API-Aufrufe rund um Abos.
import type { OverviewRead, SubscriptionCreate, SubscriptionRead, SubscriptionUpdate } from '../types/subscription'

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

// Abo löschen.
export async function deleteSubscription(id: string): Promise<void> {
  return apiFetch<void>(`/subscriptions/${id}`, { method: 'DELETE' })
}

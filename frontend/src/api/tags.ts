// Alle API-Aufrufe rund um Subscription Tags (v0.2.7).
import type { TagAssignRequest, TagCreate, TagRead, TagUpdate } from '../types/tag'

// Dieselbe Hilfsfunktion wie in subscriptions.ts — fetch + JSON + Fehlerbehandlung.
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

// Alle Tags des eingeloggten Users laden (alphabetisch sortiert).
export async function getTags(): Promise<TagRead[]> {
  return apiFetch<TagRead[]>('/subscriptions/tags')
}

// Neuen Tag anlegen.
// Gibt HTTP 409 wenn der Name bereits existiert.
export async function createTag(data: TagCreate): Promise<TagRead> {
  return apiFetch<TagRead>('/subscriptions/tags', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Tag umbenennen und/oder Farbe ändern.
// Nur gesendete Felder werden geändert (PATCH-Semantik).
export async function updateTag(id: string, data: TagUpdate): Promise<TagRead> {
  return apiFetch<TagRead>(`/subscriptions/tags/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

// Tag löschen — alle Zuweisungen zu Abos werden automatisch mitgelöscht.
export async function deleteTag(id: string): Promise<void> {
  return apiFetch<void>(`/subscriptions/tags/${id}`, { method: 'DELETE' })
}

// Tags eines Abos komplett setzen (PUT-Semantik: immer die vollständige aktuelle Auswahl senden).
// Leere tag_ids → alle Tags vom Abo entfernen.
export async function setSubscriptionTags(
  subscriptionId: string,
  data: TagAssignRequest,
): Promise<TagRead[]> {
  return apiFetch<TagRead[]>(`/subscriptions/${subscriptionId}/tags`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

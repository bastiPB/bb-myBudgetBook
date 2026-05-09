// API-Aufrufe für Sparfächer — nur diese Datei spricht /savings/boxes an.

import type {
  SavingsBookingCreate,
  SavingsBookingRead,
  SavingsBookingUpdate,
  SavingsBoxCloseRequest,
  SavingsBoxCreate,
  SavingsBoxDetail,
  SavingsBoxRead,
  SavingsBoxUpdate,
  SavingsTermRead,
} from '../types/savingsBox'

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

export async function listBoxes(): Promise<SavingsBoxRead[]> {
  return apiFetch<SavingsBoxRead[]>('/savings/boxes')
}

export async function getBoxDetail(id: string): Promise<SavingsBoxDetail> {
  return apiFetch<SavingsBoxDetail>(`/savings/boxes/${id}`)
}

export async function createBox(data: SavingsBoxCreate): Promise<SavingsBoxDetail> {
  return apiFetch<SavingsBoxDetail>('/savings/boxes', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateBox(id: string, data: SavingsBoxUpdate): Promise<SavingsBoxRead> {
  return apiFetch<SavingsBoxRead>(`/savings/boxes/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function closeBox(id: string, data: SavingsBoxCloseRequest): Promise<SavingsBoxDetail> {
  return apiFetch<SavingsBoxDetail>(`/savings/boxes/${id}/close`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function reopenBox(id: string): Promise<SavingsBoxDetail> {
  return apiFetch<SavingsBoxDetail>(`/savings/boxes/${id}/reopen`, { method: 'POST' })
}

export async function getBoxTerms(boxId: string): Promise<SavingsTermRead[]> {
  return apiFetch<SavingsTermRead[]>(`/savings/boxes/${boxId}/terms`)
}

export async function refreshTerms(boxId: string): Promise<void> {
  return apiFetch<void>(`/savings/boxes/${boxId}/terms/refresh`, { method: 'POST' })
}

export async function getBoxBookings(boxId: string): Promise<SavingsBookingRead[]> {
  return apiFetch<SavingsBookingRead[]>(`/savings/boxes/${boxId}/bookings`)
}

export async function createBooking(
  boxId: string,
  data: SavingsBookingCreate,
): Promise<SavingsBookingRead> {
  return apiFetch<SavingsBookingRead>(`/savings/boxes/${boxId}/bookings`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateBooking(
  boxId: string,
  bookingId: string,
  data: SavingsBookingUpdate,
): Promise<SavingsBookingRead> {
  return apiFetch<SavingsBookingRead>(`/savings/boxes/${boxId}/bookings/${bookingId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteBooking(boxId: string, bookingId: string): Promise<void> {
  return apiFetch<void>(`/savings/boxes/${boxId}/bookings/${bookingId}`, { method: 'DELETE' })
}

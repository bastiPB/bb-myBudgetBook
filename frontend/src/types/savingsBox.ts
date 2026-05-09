// Spiegelt backend/app/schemas/savings_box.py — Decimal im JSON typischerweise als String.

export type SavingsInterval = 'weekly' | 'biweekly' | 'monthly'
export type SavingsBoxStatus = 'active' | 'closed'
export type SavingsTermStatus = 'open' | 'fulfilled' | 'missed'
export type SavingsBookingType = 'deposit' | 'penalty' | 'manual'

export const SAVINGS_INTERVAL_LABELS: Record<SavingsInterval, string> = {
  weekly: 'Wöchentlich',
  biweekly: 'Zweiwöchentlich',
  monthly: 'Monatlich',
}

export const SAVINGS_BOX_STATUS_LABELS: Record<SavingsBoxStatus, string> = {
  active: 'Aktiv',
  closed: 'Abgeschlossen',
}

export const SAVINGS_TERM_STATUS_LABELS: Record<SavingsTermStatus, string> = {
  open: 'Offen',
  fulfilled: 'Erledigt',
  missed: 'Verpasst',
}

export const SAVINGS_BOOKING_TYPE_LABELS: Record<SavingsBookingType, string> = {
  deposit: 'Einzahlung',
  penalty: 'Strafgebühr',
  manual: 'Manuell',
}

export interface BoxSummary {
  total_deposited: string
  total_penalties: string
  net_amount: string
  target_amount: string | null
  personal_amount_per_term: string | null
  progress_pct: string | null
  terms_open: number
  terms_fulfilled: number
  terms_missed: number
}

export interface SavingsTermRead {
  id: string
  due_date: string
  expected_amount: string
  status: SavingsTermStatus
}

export interface SavingsBookingRead {
  id: string
  savings_term_id: string | null
  booking_type: SavingsBookingType
  amount: string
  booking_date: string
  note: string | null
}

export interface SavingsBoxRead {
  id: string
  name: string
  location: string | null
  box_number: string | null
  start_date: string
  end_date: string
  interval: SavingsInterval
  min_amount_per_term: string
  penalty_amount: string | null
  status: SavingsBoxStatus
  next_open_due_date: string | null
  summary: BoxSummary
}

export interface SavingsBoxDetail extends SavingsBoxRead {
  terms: SavingsTermRead[]
  bookings: SavingsBookingRead[]
  closed_at: string | null
  closing_actual_amount: string | null
  closing_expected_amount: string | null
  closing_note: string | null
}

export interface SavingsBoxCreate {
  name: string
  location?: string | null
  box_number?: string | null
  start_date: string
  end_date: string
  interval: SavingsInterval
  min_amount_per_term: number
  penalty_amount?: number | null
  target_amount?: number | null
  personal_amount_per_term?: number | null
}

export interface SavingsBoxUpdate {
  name?: string
  location?: string | null
  box_number?: string | null
  target_amount?: number | null
  personal_amount_per_term?: number | null
}

export interface SavingsBoxCloseRequest {
  actual_amount: number
  note?: string | null
}

export interface SavingsBookingCreate {
  savings_term_id?: string | null
  booking_type: SavingsBookingType
  amount: number
  booking_date: string
  note?: string | null
}

export interface SavingsBookingUpdate {
  amount?: number
  booking_date?: string
  note?: string | null
}

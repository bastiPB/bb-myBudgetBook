// Spiegelt die Backend-Schemas (schemas/subscription.py) als TypeScript-Typen.

// Die vier möglichen Abrechnungsintervalle — exakt wie im Backend-Enum
export type BillingInterval = 'monthly' | 'quarterly' | 'yearly' | 'biennial'

// Lebenszyklus-Status eines Abos (v0.2.2)
export type SubscriptionStatus = 'active' | 'suspended' | 'canceled'

// Deutsche Beschriftungen für die Anzeige im UI
export const INTERVAL_LABELS: Record<BillingInterval, string> = {
  monthly:   'Monatlich',
  quarterly: 'Vierteljährlich',
  yearly:    'Jährlich',
  biennial:  'Alle 2 Jahre',
}

// Deutsche Status-Beschriftungen für Badges
export const STATUS_LABELS: Record<SubscriptionStatus, string> = {
  active:    'Aktiv',
  suspended: 'Pausiert',
  canceled:  'Beendet',
}

// Betrag aus API-String (z. B. "9.99") in deutsches Format umwandeln (z. B. "9,99")
export function formatAmount(amount: string): string {
  const num = parseFloat(amount)
  if (isNaN(num)) return amount
  return num.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Betrag aus Formulareingabe parsen — akzeptiert Komma oder Punkt als Dezimaltrennzeichen
export function parseAmount(value: string): number {
  // "9,99" → "9.99" damit parseFloat funktioniert
  return parseFloat(value.replace(',', '.'))
}

export interface SubscriptionRead {
  id: string
  name: string
  amount: string           // Decimal kommt vom Backend als String (z. B. "9.99")
  next_due_date: string    // ISO-Datum "YYYY-MM-DD"
  interval: BillingInterval
  // v0.2.2: neue Felder
  status: SubscriptionStatus
  started_on: string
  notes: string | null
  logo_url: string | null
  suspended_at: string | null
  access_until: string | null
}

export interface SubscriptionCreate {
  name: string
  amount: number
  next_due_date: string
  interval: BillingInterval
  started_on?: string | null
  notes?: string | null
}

export interface SubscriptionUpdate {
  name?: string
  amount?: number
  next_due_date?: string
  interval?: BillingInterval
  notes?: string | null
}

export interface SuspendPayload {
  access_until?: string | null
}

export interface OverviewRead {
  monthly_total: string   // auf Monatsbasis normiert
  upcoming: SubscriptionRead[]
}

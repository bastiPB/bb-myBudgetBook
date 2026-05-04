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

// Detailansicht — SubscriptionRead + berechnete Kostenkennzahlen (Slice C)
export interface SubscriptionDetail extends SubscriptionRead {
  monthly_cost_normalized: string   // Betrag auf Monatsbasis (Decimal als String)
  yearly_cost_normalized: string    // monthly × 12
  total_paid_estimate: string       // Schätzung bisheriger Gesamtkosten
}

// Datum von ISO-Format ("2026-05-03") in deutsches Format ("03.05.2026") umwandeln
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${day}.${month}.${year}`
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

// Preishistorie-Eintrag (Slice E): "ab valid_from gilt amount"
export interface PriceHistoryEntry {
  id: string
  subscription_id: string
  amount: string       // Decimal als String, z. B. "9.99"
  valid_from: string   // ISO-Datum "YYYY-MM-DD"
}

// Status einer Soll-Buchung (Slice G)
export type PaymentStatus = 'pending' | 'matched' | 'missed'

// Soll-Buchung für ein Abo (Slice G): täglich vom Scheduler erzeugt
export interface ScheduledPaymentEntry {
  id: string
  subscription_id: string
  due_date: string       // ISO-Datum "YYYY-MM-DD"
  amount: string         // Betrag zum Zeitpunkt der Generierung
  status: PaymentStatus
}

// Deutsche Beschriftungen für Payment-Status
export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  pending: 'Offen',
  matched: 'Bezahlt',
  missed:  'Verpasst',
}

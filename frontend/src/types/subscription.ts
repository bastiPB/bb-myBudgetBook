// Spiegelt die Backend-Schemas (schemas/subscription.py) als TypeScript-Typen.

// Die fünf möglichen Abrechnungsintervalle — exakt wie im Backend-Enum (v0.2.3: semiannual neu)
export type BillingInterval = 'monthly' | 'quarterly' | 'semiannual' | 'yearly' | 'biennial'

// Lebenszyklus-Status eines Abos (v0.2.2)
export type SubscriptionStatus = 'active' | 'suspended' | 'canceled'

// Deutsche Beschriftungen für die Anzeige im UI
export const INTERVAL_LABELS: Record<BillingInterval, string> = {
  monthly:    'Monatlich',
  quarterly:  'Vierteljährlich',
  semiannual: 'Halbjährlich',
  yearly:     'Jährlich',
  biennial:   'Alle 2 Jahre',
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
  amount: string             // Decimal kommt vom Backend als String (z. B. "9.99")
  next_due_date: string | null  // berechnetes Fälligkeitsdatum — null bei Zukunfts-Abos
  interval: BillingInterval
  status: SubscriptionStatus
  started_on: string
  notes: string | null
  logo_url: string | null
  // suspended_at + access_until entfernt in v0.2.3 — stehen jetzt in PauseHistoryEntry
}

// Detailansicht — SubscriptionRead + vier berechnete Kostenkennzahlen (v0.2.3)
export interface SubscriptionDetail extends SubscriptionRead {
  monatlich: string           // Betrag auf Monatsbasis normiert (z. B. "7.49" bei jährlichem Abo)
  tatsaechlich: string        // Summe aller tatsächlich gezahlten Perioden (Pauses ausgenommen)
  intervalle: number          // Anzahl Zahlungsperioden seit Abo-Beginn (als Zahl, kein String)
  dieses_kalenderjahr: string // Jahreskosten inkl. angekündigter Preisänderungen
}

// Datum von ISO-Format ("2026-05-03") in deutsches Format ("03.05.2026") umwandeln
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${day}.${month}.${year}`
}

export interface SubscriptionCreate {
  name: string
  amount: number
  interval: BillingInterval
  started_on?: string | null  // optional — Backend setzt default auf heute
  notes?: string | null
  // next_due_date entfernt in v0.2.3 — wird serverseitig aus started_on berechnet
}

export interface SubscriptionUpdate {
  name?: string
  interval?: BillingInterval
  notes?: string | null
  // amount + next_due_date entfernt in v0.2.3 — Preisänderungen via /price-change
}

// Preisänderung mit Wirkungsdatum — valid_from darf Vergangenheit, heute oder Zukunft sein
export interface PriceChangeRequest {
  amount: number
  valid_from: string  // ISO-Datum "YYYY-MM-DD"
}

// Einzel-Eintrag aus der Pause-Historie eines Abos (v0.2.3)
export interface PauseHistoryEntry {
  paused_at: string
  resumed_at: string | null
  access_until: string | null
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

// Status einer Soll-Buchung (Slice G) — v0.2.3: paused neu
export type PaymentStatus = 'pending' | 'paused' | 'matched' | 'missed'

// Soll-Buchung für ein Abo (Slice G): vom Scheduler erzeugt
export interface ScheduledPaymentEntry {
  id: string
  subscription_id: string
  due_date: string        // ISO-Datum "YYYY-MM-DD"
  amount: string | null   // null wenn das Abo in dieser Periode pausiert war
  status: PaymentStatus
}

// Deutsche Beschriftungen für Payment-Status
export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  pending: 'Offen',
  paused:  'Pausiert',
  matched: 'Bezahlt',
  missed:  'Verpasst',
}

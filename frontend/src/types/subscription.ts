// Spiegelt die Backend-Schemas (schemas/subscription.py) als TypeScript-Typen.

// Die vier möglichen Abrechnungsintervalle — exakt wie im Backend-Enum
export type BillingInterval = 'monthly' | 'quarterly' | 'yearly' | 'biennial'

// Deutsche Beschriftungen für die Anzeige im UI
export const INTERVAL_LABELS: Record<BillingInterval, string> = {
  monthly:   'Monatlich',
  quarterly: 'Vierteljährlich',
  yearly:    'Jährlich',
  biennial:  'Alle 2 Jahre',
}

export interface SubscriptionRead {
  id: string
  name: string
  amount: string          // Decimal kommt vom Backend als String (z.B. "9.99")
  next_due_date: string   // ISO-Datum "YYYY-MM-DD"
  interval: BillingInterval
}

export interface SubscriptionCreate {
  name: string
  amount: number
  next_due_date: string
  interval: BillingInterval
}

export interface SubscriptionUpdate {
  name?: string
  amount?: number
  next_due_date?: string
  interval?: BillingInterval
}

export interface OverviewRead {
  monthly_total: string   // auf Monatsbasis normiert
  upcoming: SubscriptionRead[]
}

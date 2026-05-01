// MODULE_REGISTRY — alle bekannten Module der App.
// Neues Modul hinzufügen: einfach ein neues Objekt anhängen.
// Die DB braucht dafür keine Änderung — nur der Key muss in MODULE_KEYS (services/profile.py) ergänzt werden.
import type { ModuleDefinition } from '../types/module'

export const MODULE_REGISTRY: ModuleDefinition[] = [
  {
    key: 'subscriptions',
    label: 'Abo-Manager',
    description: 'Verwalte deine wiederkehrenden Ausgaben wie Streaming, Versicherungen und mehr.',
    route: '/subscriptions',
    navLabel: 'Abos',
  },
  {
    key: 'savings_box',
    label: 'Sparfach',
    description: 'Lege Geld für bestimmte Ziele zurück — Urlaub, Anschaffungen, Notgroschen.',
    route: '/savings-box',
    navLabel: 'Sparfach',
  },
  {
    key: 'vacation_fund',
    label: 'Urlaubskasse',
    description: 'Plane und verwalte dein Budget für Reisen und Urlaube.',
    route: '/vacation-fund',
    navLabel: 'Urlaubskasse',
  },
  {
    key: 'household_budget',
    label: 'Haushaltsbuch',
    description: 'Behalte deine Einnahmen und Ausgaben im Blick.',
    route: '/household-budget',
    navLabel: 'Haushaltsbuch',
  },
  {
    key: 'fund_savings',
    label: 'Fondsparen',
    description: 'Plane regelmäßige Investitionen in Fonds und ETFs.',
    route: '/fund-savings',
    navLabel: 'Fondsparen',
  },
  {
    key: 'stock_portfolio',
    label: 'Aktiendepot',
    description: 'Verwalte und analysiere dein Aktienportfolio.',
    route: '/stock-portfolio',
    navLabel: 'Depot',
  },
]

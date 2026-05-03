// DashboardPage.tsx — Übersicht nach dem Login.
// Die App-Shell (Header, Sidebar, Footer, Logout) wird von AppLayout übernommen.
// Diese Seite zeigt nur den Inhalt: Onboarding-Hinweis + finanzielle Übersicht.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { getOverview } from '../api/subscriptions'
import { useAuth } from '../context/useAuth'
import { useModules } from '../context/useModules'
import type { OverviewRead } from '../types/subscription'
import { INTERVAL_LABELS } from '../types/subscription'

export default function DashboardPage() {
  const { user } = useAuth()
  const { hasChosenModules, displayName } = useModules()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<OverviewRead | null>(null)

  // Anzeigename: display_name aus Profil, Fallback: Teil der E-Mail vor dem @
  const greeting = displayName ?? user!.email.split('@')[0]

  // Übersichtsdaten beim Laden der Seite abrufen
  useEffect(() => {
    getOverview()
      .then(setOverview)
      // Kein Fehler anzeigen wenn noch keine Abos vorhanden sind
      .catch(() => {})
  }, [])

  // Warteansicht für Nutzer mit der Rolle "default" (noch kein Zugriff auf Daten).
  // Der Admin muss erst eine Rolle zuweisen — vorher gibt das Backend 403 zurück.
  if (user!.role === 'default') {
    return (
      <div className="pending-view">
        <h1>Willkommen!</h1>
        <p>
          Dein Account ist angelegt. Sobald ein Admin dir eine Rolle zugewiesen hat,
          hast du vollen Zugriff auf die App.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="page-title">Dashboard</h1>

      {/* Onboarding-Card — wird nur angezeigt wenn noch keine Module gewählt wurden */}
      {!hasChosenModules && (
        <div className="onboarding-card">
          <h2>Hallo {greeting}!</h2>
          <p>
            Dein Dashboard ist noch leer. Wähle deine Module und richte dein
            Dashboard ein.
          </p>
          <button
            className="btn-primary"
            onClick={() => navigate('/profile/settings')}
          >
            Jetzt loslegen
          </button>
        </div>
      )}

      {/* Finanzielle Übersicht — wird angezeigt sobald Daten vorhanden sind */}
      {overview && (
        <>
          {/* Monatliche Gesamtkosten */}
          <div className="card">
            <h2>Monatliche Gesamtkosten</h2>
            <p className="amount-large">
              {parseFloat(overview.monthly_total).toFixed(2)} €
            </p>
          </div>

          {/* Nächste Fälligkeiten in den kommenden 30 Tagen */}
          {overview.upcoming.length > 0 && (
            <div className="card">
              <h2>Nächste Fälligkeiten (30 Tage)</h2>
              <ul className="upcoming-list">
                {overview.upcoming.map(sub => (
                  <li key={sub.id}>
                    <span>
                      {sub.name}&nbsp;
                      <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>
                        ({INTERVAL_LABELS[sub.interval]})
                      </span>
                    </span>
                    <span className="upcoming-date">
                      {sub.next_due_date} · {parseFloat(sub.amount).toFixed(2)} €
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Hinweis "keine Fälligkeiten" nur wenn Module bereits gewählt wurden */}
          {overview.upcoming.length === 0 && hasChosenModules && (
            <p style={{ color: 'var(--color-text-muted)', fontSize: 14 }}>
              Keine Abos in den nächsten 30 Tagen fällig.
            </p>
          )}
        </>
      )}
    </div>
  )
}

// DashboardPage.tsx — Übersicht nach dem Login.
// Zeigt monatliche Gesamtkosten + demnächst fällige Abos.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { logoutUser } from '../api/auth'
import { getOverview } from '../api/subscriptions'
import { useAuth } from '../context/useAuth'
import type { OverviewRead } from '../types/subscription'
import { INTERVAL_LABELS } from '../types/subscription'

export default function DashboardPage() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<OverviewRead | null>(null)

  // Übersicht beim Laden der Seite abrufen
  useEffect(() => {
    getOverview()
      .then(setOverview)
      .catch(() => {/* kein Fehler anzeigen wenn noch keine Abos vorhanden */})
  }, [])

  async function handleLogout() {
    await logoutUser()
    setUser(null)
    navigate('/login')
  }

  // Wartebildschirm für default-Rolle: User ist eingeloggt, hat aber noch keine
  // Rolle zugewiesen bekommen — Datenzugriff ist nicht erlaubt (Backend gibt 403).
  if (user!.role === 'default') {
    return (
      <div style={{ maxWidth: 600, margin: '80px auto', padding: '0 16px', textAlign: 'center' }}>
        <h1>Willkommen!</h1>
        <p style={{ fontSize: 18, marginTop: 16, color: '#444' }}>
          Dein Account wurde freigeschaltet.
        </p>
        <p style={{ color: '#666', marginTop: 8 }}>
          Warte auf die Rollenzuweisung durch einen Admin. Sobald du eine Rolle
          erhalten hast, hast du Zugriff auf die App.
        </p>
        <button
          onClick={handleLogout}
          style={{ marginTop: 32, padding: '10px 24px' }}
        >
          Abmelden
        </button>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: '0 16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Dashboard</h1>
        <button onClick={handleLogout} style={{ padding: '8px 16px' }}>
          Abmelden
        </button>
      </div>
      <p style={{ color: '#666', marginTop: 4 }}>Eingeloggt als: {user!.email} ({user!.role})</p>

      <hr style={{ margin: '24px 0' }} />

      {/* Übersicht */}
      {overview && (
        <>
          <div style={{ marginBottom: 24 }}>
            <h2>Monatliche Gesamtkosten</h2>
            <p style={{ fontSize: 32, fontWeight: 'bold', marginTop: 8 }}>
              {parseFloat(overview.monthly_total).toFixed(2)} €
            </p>
          </div>

          {overview.upcoming.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h2>Nächste Fälligkeiten (30 Tage)</h2>
              <ul style={{ marginTop: 8, paddingLeft: 16 }}>
                {overview.upcoming.map(sub => (
                  <li key={sub.id} style={{ marginBottom: 4 }}>
                    {sub.next_due_date} — {sub.name} ({parseFloat(sub.amount).toFixed(2)} €, {INTERVAL_LABELS[sub.interval]})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {overview.upcoming.length === 0 && (
            <p style={{ color: '#666' }}>Keine Abos in den nächsten 30 Tagen fällig.</p>
          )}
        </>
      )}

      {/* Navigation */}
      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        <button
          onClick={() => navigate('/subscriptions')}
          style={{ padding: '10px 20px' }}
        >
          Alle Abos verwalten →
        </button>

        {/* Admin-Link — nur für User mit Rolle "admin" sichtbar */}
        {user!.role === 'admin' && (
          <button
            onClick={() => navigate('/admin')}
            style={{ padding: '10px 20px' }}
          >
            User verwalten (Admin) →
          </button>
        )}
      </div>
    </div>
  )
}

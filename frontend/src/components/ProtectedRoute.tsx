// ProtectedRoute.tsx — Schutzschicht für Seiten die nur eingeloggte User sehen dürfen.
//
// Verwendung in App.tsx:
//   <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
//
// Was passiert:
//   1. App startet, getMe() läuft noch  → "Laden..." anzeigen (kein Flackern zur Login-Seite)
//   2. Nicht eingeloggt                 → Weiterleitung zu /login
//   3. Eingeloggt                       → Inhalt (children) anzeigen
import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  // Noch am Prüfen ob Session-Cookie gültig ist — kurz warten
  if (loading) return <p style={{ padding: 32 }}>Laden...</p>

  // Kein eingeloggter User → zur Login-Seite (replace verhindert "Zurück"-Button-Loop)
  if (!user) return <Navigate to="/login" replace />

  // Eingeloggt → gewünschte Seite anzeigen
  return <>{children}</>
}

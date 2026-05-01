// AdminRoute.tsx — Schutzschicht für Seiten die nur Admins sehen dürfen.
//
// Wie ProtectedRoute, aber mit einer zweiten Prüfung:
//   1. App startet, getMe() läuft noch  → "Laden..." anzeigen
//   2. Nicht eingeloggt                 → Weiterleitung zu /login
//   3. Eingeloggt aber kein Admin       → Weiterleitung zu /dashboard
//   4. Admin                            → Inhalt (children) anzeigen
import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export default function AdminRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  // Noch am Prüfen ob Session-Cookie gültig ist
  if (loading) return <p style={{ padding: 32 }}>Laden...</p>

  // Nicht eingeloggt → Login-Seite
  if (!user) return <Navigate to="/login" replace />

  // Eingeloggt aber keine Admin-Rolle → Dashboard (keine Fehlermeldung nötig)
  if (user.role !== 'admin') return <Navigate to="/dashboard" replace />

  // Admin → gewünschte Seite anzeigen
  return <>{children}</>
}

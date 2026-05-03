// App.tsx — Routing der gesamten App.
// Statische Routen: /login, /register, /dashboard, /admin
// Dynamische Modul-Routen: werden aus activeModules (ModulesContext) generiert.
// Nur aktive Module (Admin freigegeben + User aktiviert) sind als Route erreichbar.
import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import AdminRoute from './components/AdminRoute'
import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import { useModules } from './context/useModules'
import AdminPage from './pages/AdminPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import PlaceholderPage from './pages/PlaceholderPage'
import ProfileSettingsPage from './pages/ProfileSettingsPage'
import RegisterPage from './pages/RegisterPage'
import SettingsPage from './pages/SettingsPage'
import SubscriptionsPage from './pages/SubscriptionsPage'

// Hilfsfunktion: kombiniert Zugriffsschutz + App-Shell für normale User-Seiten.
// Alle geschützten Seiten werden damit in Header/Sidebar/Footer eingebettet.
function Layout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <AppLayout>{children}</AppLayout>
    </ProtectedRoute>
  )
}

// Wie Layout, aber mit zusätzlicher Admin-Rollenprüfung
function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminRoute>
      <AppLayout>{children}</AppLayout>
    </AdminRoute>
  )
}

function App() {
  const { activeModules } = useModules()

  return (
    <Routes>
      {/* Root → Dashboard (ProtectedRoute leitet bei Bedarf auf /login weiter) */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Öffentlich — keine App-Shell */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Geschützt — immer erreichbar für eingeloggte User */}
      <Route path="/dashboard" element={<Layout><DashboardPage /></Layout>} />

      {/* Nur für Admins — AdminLayout prüft zusätzlich die Rolle */}
      <Route path="/admin" element={<AdminLayout><AdminPage /></AdminLayout>} />
      <Route path="/settings" element={<AdminLayout><SettingsPage /></AdminLayout>} />

      {/* Profil-Einstellungen — für jeden eingeloggten User */}
      <Route path="/profile/settings" element={<Layout><ProfileSettingsPage /></Layout>} />

      {/* Dynamische Modul-Routen — nur aktive Module sind erreichbar (ADR 0008).
          Inaktive Module haben keine Route → URL-Aufruf landet beim Fallback (Login). */}
      {activeModules.map(module => (
        <Route
          key={module.key}
          path={module.route}
          element={
            <Layout>
              {/* Abo-Manager hat eine echte Seite — alle anderen sind Platzhalter (v0.2.0) */}
              {module.key === 'subscriptions'
                ? <SubscriptionsPage />
                : <PlaceholderPage moduleName={module.label} />
              }
            </Layout>
          }
        />
      ))}

      {/* Alles andere → 404-Seite (kein blindes Redirect zum Login) */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App

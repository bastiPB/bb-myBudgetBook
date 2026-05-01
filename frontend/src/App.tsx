// App.tsx — Routing der gesamten App.
// Statische Routen: /login, /register, /dashboard, /admin
// Dynamische Modul-Routen: werden aus activeModules (ModulesContext) generiert.
// Nur aktive Module (Admin freigegeben + User aktiviert) sind als Route erreichbar.
import { Navigate, Route, Routes } from 'react-router-dom'

import AdminRoute from './components/AdminRoute'
import ProtectedRoute from './components/ProtectedRoute'
import { useModules } from './context/useModules'
import AdminPage from './pages/AdminPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import PlaceholderPage from './pages/PlaceholderPage'
import NotFoundPage from './pages/NotFoundPage'
import ProfileSettingsPage from './pages/ProfileSettingsPage'
import RegisterPage from './pages/RegisterPage'
import SettingsPage from './pages/SettingsPage'
import SubscriptionsPage from './pages/SubscriptionsPage'

function App() {
  const { activeModules } = useModules()

  return (
    <Routes>
      {/* Root → Dashboard (ProtectedRoute leitet bei Bedarf auf /login weiter) */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Öffentlich */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Geschützt — immer erreichbar für eingeloggte User */}
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />

      {/* Nur für Admins — AdminRoute prüft zusätzlich die Rolle */}
      <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
      <Route path="/settings" element={<AdminRoute><SettingsPage /></AdminRoute>} />

      {/* Profil-Einstellungen — für jeden eingeloggten User */}
      <Route path="/profile/settings" element={<ProtectedRoute><ProfileSettingsPage /></ProtectedRoute>} />

      {/* Dynamische Modul-Routen — nur aktive Module sind erreichbar (ADR 0008).
          Inaktive Module haben keine Route → URL-Aufruf landet beim Fallback (Login). */}
      {activeModules.map(module => (
        <Route
          key={module.key}
          path={module.route}
          element={
            <ProtectedRoute>
              {/* Abo-Manager hat eine echte Seite — alle anderen sind Platzhalter (v0.2.0) */}
              {module.key === 'subscriptions'
                ? <SubscriptionsPage />
                : <PlaceholderPage moduleName={module.label} />
              }
            </ProtectedRoute>
          }
        />
      ))}

      {/* Alles andere → 404-Seite (kein blindes Redirect zum Login) */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App

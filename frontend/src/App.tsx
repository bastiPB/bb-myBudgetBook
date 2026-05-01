// App.tsx — Routing der gesamten App.
// ProtectedRoute schützt alle Seiten die nur für eingeloggte User gedacht sind.
import { Navigate, Route, Routes } from 'react-router-dom'
import AdminRoute from './components/AdminRoute'
import ProtectedRoute from './components/ProtectedRoute'
import AdminPage from './pages/AdminPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import SubscriptionsPage from './pages/SubscriptionsPage'

function App() {
  return (
    <Routes>
      {/* Öffentlich */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Geschützt — nur für eingeloggte User */}
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/subscriptions" element={<ProtectedRoute><SubscriptionsPage /></ProtectedRoute>} />

      {/* Nur für Admins — AdminRoute prüft zusätzlich die Rolle */}
      <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />

      {/* Alles andere → Login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

export default App

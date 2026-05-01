// NotFoundPage.tsx — wird angezeigt wenn eine URL nicht existiert.
// Zeigt eingeloggten Usern einen "Zum Dashboard"-Button,
// nicht eingeloggten Usern einen "Zum Login"-Button.
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export default function NotFoundPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  return (
    <div style={{ maxWidth: 500, margin: '120px auto', padding: '0 16px', textAlign: 'center' }}>
      <h1 style={{ fontSize: 64, margin: 0, color: '#ccc' }}>404</h1>
      <h2 style={{ marginTop: 8 }}>Seite nicht gefunden</h2>
      <p style={{ color: '#666', marginTop: 8 }}>
        Diese Seite existiert nicht oder du hast keine Berechtigung sie aufzurufen.
      </p>
      <button
        onClick={() => navigate(user ? '/dashboard' : '/login')}
        style={{ marginTop: 24, padding: '10px 24px' }}
      >
        {user ? 'Zum Dashboard' : 'Zum Login'}
      </button>
    </div>
  )
}

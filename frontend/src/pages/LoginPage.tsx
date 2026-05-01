// LoginPage.tsx — Login-Formular.
// Konzepte die hier vorkommen:
//   useState  = Wert speichern, der sich ändern kann (React aktualisiert die Seite automatisch)
//   useNavigate = nach dem Login programmatisch zu einer anderen URL wechseln
//   async/await = auf das Backend warten ohne die Seite einzufrieren
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { loginUser } from '../api/auth'
import { useAuth } from '../context/useAuth'

export default function LoginPage() {
  // Formular-Felder: jedes Feld hat seinen eigenen State
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // Fehlermeldung (null = kein Fehler)
  const [error, setError] = useState<string | null>(null)

  // Verhindert Doppelklick: true während der Request läuft
  const [loading, setLoading] = useState(false)

  // navigate('/dashboard') wechselt die URL ohne Seitenreload
  const navigate = useNavigate()

  // setUser schreibt den eingeloggten User in den globalen Context
  const { setUser } = useAuth()

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    // Standard-Browser-Verhalten verhindern (Seite neu laden beim Formular-Submit)
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const user = await loginUser(email, password)
      // User im globalen Context speichern — alle anderen Komponenten kennen ihn jetzt
      setUser(user)
      navigate('/dashboard')
    } catch (err) {
      // Fehlermeldung aus dem Backend anzeigen (z.B. "E-Mail oder Passwort ist falsch.")
      setError(err instanceof Error ? err.message : 'Login fehlgeschlagen.')
    } finally {
      // Egal ob Erfolg oder Fehler — Loading beenden
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: '80px auto', padding: '0 16px' }}>
      <h1 style={{ marginBottom: 8 }}>Anmelden</h1>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="email">E-Mail</label>
          <input
            id="email"
            type="email"
            value={email}
            // onChange feuert bei jedem Tastendruck — aktualisiert den State
            onChange={e => setEmail(e.target.value)}
            required
            autoFocus
            style={{ padding: '8px', fontSize: 16 }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="password">Passwort</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{ padding: '8px', fontSize: 16 }}
          />
        </div>

        {/* Fehlermeldung — wird nur angezeigt wenn error nicht null ist */}
        {error && (
          <p style={{ color: 'red', margin: 0 }}>{error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{ padding: '10px', fontSize: 16, cursor: loading ? 'not-allowed' : 'pointer' }}
        >
          {loading ? 'Anmelden...' : 'Anmelden'}
        </button>
      </form>

      {/* Link zur Registrierung */}
      <p style={{ marginTop: 24, textAlign: 'center', color: '#666', fontSize: 14 }}>
        Noch kein Konto?{' '}
        <button
          onClick={() => navigate('/register')}
          style={{ background: 'none', border: 'none', color: '#0070f3', cursor: 'pointer', fontSize: 14, padding: 0 }}
        >
          Jetzt registrieren
        </button>
      </p>
    </div>
  )
}

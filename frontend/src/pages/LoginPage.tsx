// LoginPage.tsx — Login-Formular.
// Konzepte die hier vorkommen:
//   useState  = Wert speichern, der sich ändern kann (React aktualisiert die Seite automatisch)
//   useNavigate = nach dem Login programmatisch zu einer anderen URL wechseln
//   async/await = auf das Backend warten ohne die Seite einzufrieren
import { useEffect, useState } from 'react'
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
  const { user, setUser } = useAuth()

  // Countdown für den Redirect wenn der User bereits eingeloggt ist
  const [loginCountdown, setLoginCountdown] = useState(3)

  // Abmelde-Bestätigung: true wenn der User gerade über Logout hierher kam.
  // sessionStorage statt location.state — überlebt den Navigation-Dance zuverlässig
  // (location.state kann durch ProtectedRoute's <Navigate replace> überschrieben werden).
  // Flag sofort löschen damit ein manuelles Reload die Meldung nicht erneut zeigt.
  const [showGoodbye] = useState(() => {
    const flag = sessionStorage.getItem('justLoggedOut') === 'true'
    if (flag) sessionStorage.removeItem('justLoggedOut')
    return flag
  })
  const [goodbyeCountdown, setGoodbyeCountdown] = useState(3)

  // Wenn der User bereits eingeloggt ist: Countdown starten, dann zum Dashboard
  useEffect(() => {
    if (!user) return
    if (loginCountdown === 0) {
      navigate('/dashboard')
      return
    }
    const timer = setTimeout(() => setLoginCountdown(prev => prev - 1), 1000)
    return () => clearTimeout(timer)
  }, [user, loginCountdown, navigate])

  // Abmelde-Bestätigung: Countdown läuft bis 0, dann zeigt die Bedingung im JSX das Formular
  // Kein setState im Effect-Body — nur setTimeout (asynchron, Lint-konform)
  useEffect(() => {
    if (!showGoodbye || goodbyeCountdown === 0) return
    const timer = setTimeout(() => setGoodbyeCountdown(prev => prev - 1), 1000)
    return () => clearTimeout(timer)
  }, [showGoodbye, goodbyeCountdown])

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

  // Bereits eingeloggt → Hinweisscreen mit Countdown anzeigen
  if (user) {
    return (
      <div style={{ maxWidth: 400, margin: '80px auto', padding: '0 16px', textAlign: 'center' }}>
        <h2>Du bist bereits eingeloggt.</h2>
        <p style={{ color: '#666', marginTop: 8 }}>
          Du wirst in {loginCountdown} Sekunde{loginCountdown !== 1 ? 'n' : ''} zum Dashboard weitergeleitet…
        </p>
        <button
          onClick={() => navigate('/dashboard')}
          style={{ marginTop: 24, padding: '10px 24px' }}
        >
          Jetzt zum Dashboard
        </button>
      </div>
    )
  }

  // Gerade abgemeldet → kurze Bestätigung solange Countdown > 0, dann das Formular
  if (showGoodbye && goodbyeCountdown > 0) {
    return (
      <div style={{ maxWidth: 400, margin: '80px auto', padding: '0 16px', textAlign: 'center' }}>
        <h2>Du hast dich erfolgreich abgemeldet.</h2>
        <p style={{ color: '#666', marginTop: 8 }}>
          Das Anmeldeformular erscheint in {goodbyeCountdown} Sekunde{goodbyeCountdown !== 1 ? 'n' : ''}…
        </p>
        <button
          onClick={() => setGoodbyeCountdown(0)}
          style={{ marginTop: 24, padding: '10px 24px' }}
        >
          Jetzt anmelden
        </button>
      </div>
    )
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

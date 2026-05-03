// LoginPage.tsx — Login-Formular.
// Konzepte die hier vorkommen:
//   useState  = Wert speichern, der sich ändern kann (React aktualisiert die Seite automatisch)
//   useNavigate = nach dem Login programmatisch zu einer anderen URL wechseln
//   async/await = auf das Backend warten ohne die Seite einzufrieren
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { loginUser } from '../api/auth'
import { useAuth } from '../context/useAuth'
import './LoginPage.css'

// SVG-Logo — identisch zu AppLayout, damit der Wiedererkennungswert stimmt
function LogoIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <rect width="26" height="26" rx="6" fill="var(--color-accent)" />
      <text
        x="3"
        y="19"
        fontFamily="system-ui, sans-serif"
        fontWeight="800"
        fontSize="14"
        fill="white"
      >
        BB
      </text>
    </svg>
  )
}

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

  // Theme aus localStorage anwenden — damit die Login-Seite das gespeicherte Theme zeigt,
  // auch wenn AppLayout (das sonst data-theme setzt) hier nicht gerendert wird.
  useEffect(() => {
    const savedTheme = localStorage.getItem('bb-theme') ?? 'light'
    document.documentElement.setAttribute('data-theme', savedTheme)
  }, [])

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
      const loggedInUser = await loginUser(email, password)
      // User im globalen Context speichern — alle anderen Komponenten kennen ihn jetzt
      setUser(loggedInUser)
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
      <div className="login-page">
        <div className="login-info-card">
          <h2>Du bist bereits eingeloggt.</h2>
          <p>
            Du wirst in {loginCountdown} Sekunde{loginCountdown !== 1 ? 'n' : ''} zum
            Dashboard weitergeleitet…
          </p>
          <button
            className="login-btn-secondary"
            onClick={() => navigate('/dashboard')}
          >
            Jetzt zum Dashboard
          </button>
        </div>
      </div>
    )
  }

  // Gerade abgemeldet → kurze Bestätigung solange Countdown > 0, dann das Formular
  if (showGoodbye && goodbyeCountdown > 0) {
    return (
      <div className="login-page">
        <div className="login-info-card">
          <h2>Du hast dich erfolgreich abgemeldet.</h2>
          <p>
            Das Anmeldeformular erscheint in {goodbyeCountdown}{' '}
            Sekunde{goodbyeCountdown !== 1 ? 'n' : ''}…
          </p>
          <button
            className="login-btn-secondary"
            onClick={() => setGoodbyeCountdown(0)}
          >
            Jetzt anmelden
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-card">

        {/* Logo — gleiche Optik wie im App-Header */}
        <div className="login-logo">
          <LogoIcon />
          <span className="login-logo-text">my-BB</span>
        </div>

        <h1>Anmelden</h1>

        <form className="login-form" onSubmit={handleSubmit}>

          <div className="form-field">
            <label htmlFor="email">E-Mail</label>
            <input
              id="email"
              type="email"
              value={email}
              // onChange feuert bei jedem Tastendruck — aktualisiert den State
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus
              autoComplete="email"
              placeholder="deine@email.de"
            />
          </div>

          <div className="form-field">
            <label htmlFor="password">Passwort</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              placeholder="••••••••"
            />
          </div>

          {/* Fehlermeldung — wird nur angezeigt wenn error nicht null ist */}
          {error && <p className="login-error">{error}</p>}

          <button
            type="submit"
            className="login-submit"
            disabled={loading}
          >
            {loading ? 'Anmelden…' : 'Anmelden'}
          </button>

        </form>

        {/* Link zur Registrierungsseite */}
        <p className="login-footer-text">
          Noch kein Konto?{' '}
          <button
            className="login-link"
            onClick={() => navigate('/register')}
          >
            Jetzt registrieren
          </button>
        </p>

      </div>
    </div>
  )
}

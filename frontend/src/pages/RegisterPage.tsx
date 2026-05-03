// RegisterPage.tsx — Selbst-Registrierung für neue User.
// Nach erfolgreicher Registrierung wartet der Account auf Admin-Freigabe.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { registerUser } from '../api/auth'
import { useAuth } from '../context/useAuth'
import './RegisterPage.css'

// SVG-Logo — identisch zu LoginPage und AppLayout
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

export default function RegisterPage() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  // Zweites Passwortfeld — nur zur Bestätigung, wird nicht ans Backend geschickt
  const [passwordConfirm, setPasswordConfirm] = useState('')

  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Nach erfolgreicher Registrierung: Erfolgsscreen anzeigen statt weiterleiten
  const [success, setSuccess] = useState(false)

  // Countdown für den Redirect wenn der User bereits eingeloggt ist
  const [countdown, setCountdown] = useState(3)

  // Theme aus localStorage anwenden — damit die Register-Seite das gespeicherte Theme zeigt
  useEffect(() => {
    const savedTheme = localStorage.getItem('bb-theme') ?? 'light'
    document.documentElement.setAttribute('data-theme', savedTheme)
  }, [])

  // Wenn der User bereits eingeloggt ist: Countdown starten, dann zum Dashboard
  useEffect(() => {
    if (!user) return
    if (countdown === 0) {
      navigate('/dashboard')
      return
    }
    const timer = setTimeout(() => setCountdown(prev => prev - 1), 1000)
    return () => clearTimeout(timer)
  }, [user, countdown, navigate])

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)

    // Passwörter müssen übereinstimmen — das prüfen wir im Frontend, kein Backend-Call nötig
    if (password !== passwordConfirm) {
      setError('Die Passwörter stimmen nicht überein.')
      return
    }

    setLoading(true)
    try {
      await registerUser(email, password)
      // Erfolgreich registriert — Erfolgsscreen anzeigen
      setSuccess(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registrierung fehlgeschlagen.')
    } finally {
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
            Du wirst in {countdown} Sekunde{countdown !== 1 ? 'n' : ''} zum
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

  // Erfolgsscreen: Account ist pending, wartet auf Admin-Freigabe
  if (success) {
    return (
      <div className="login-page">
        <div className="login-info-card">
          <h2>Registrierung erfolgreich!</h2>
          <p>
            Dein Account wurde angelegt und wartet auf Freigabe durch einen
            Admin. Sobald das passiert ist, kannst du dich einloggen.
          </p>
          <button
            className="login-btn-secondary"
            onClick={() => navigate('/login')}
          >
            Zum Login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-card">

        {/* Logo — gleiche Optik wie Login und App-Header */}
        <div className="login-logo">
          <LogoIcon />
          <span className="login-logo-text">my-BB</span>
        </div>

        <h1>Registrieren</h1>

        <form className="login-form" onSubmit={handleSubmit}>

          <div className="form-field">
            <label htmlFor="email">E-Mail</label>
            <input
              id="email"
              type="email"
              value={email}
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
              // minLength prüft der Browser selbst — kein extra JS nötig
              minLength={8}
              autoComplete="new-password"
              placeholder="Mindestens 8 Zeichen"
            />
          </div>

          <div className="form-field">
            <label htmlFor="passwordConfirm">Passwort bestätigen</label>
            <input
              id="passwordConfirm"
              type="password"
              value={passwordConfirm}
              onChange={e => setPasswordConfirm(e.target.value)}
              required
              autoComplete="new-password"
              placeholder="••••••••"
            />
          </div>

          {error && <p className="login-error">{error}</p>}

          <button
            type="submit"
            className="login-submit"
            disabled={loading}
          >
            {loading ? 'Registrieren…' : 'Registrieren'}
          </button>

        </form>

        {/* Hinweis unter dem Formular: Account braucht Admin-Freigabe */}
        <p className="login-footer-text">
          Nach der Registrierung muss dein Account von einem Admin freigegeben werden.
        </p>

        <p className="login-footer-text" style={{ marginTop: 8 }}>
          Bereits registriert?{' '}
          <button
            className="login-link"
            onClick={() => navigate('/login')}
          >
            Anmelden
          </button>
        </p>

      </div>
    </div>
  )
}

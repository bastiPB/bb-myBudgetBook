// RegisterPage.tsx — Selbst-Registrierung für neue User.
// Nach erfolgreicher Registrierung wartet der Account auf Admin-Freigabe.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { registerUser } from '../api/auth'
import { useAuth } from '../context/useAuth'

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
      <div style={{ maxWidth: 400, margin: '80px auto', padding: '0 16px', textAlign: 'center' }}>
        <h2>Du bist bereits registriert und eingeloggt.</h2>
        <p style={{ color: '#666', marginTop: 8 }}>
          Du wirst in {countdown} Sekunde{countdown !== 1 ? 'n' : ''} zum Dashboard weitergeleitet…
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

  // Erfolgsscreen: Account ist pending, warte auf Admin-Freigabe
  if (success) {
    return (
      <div style={{ maxWidth: 400, margin: '80px auto', padding: '0 16px', textAlign: 'center' }}>
        <h1 style={{ marginBottom: 16 }}>Registrierung erfolgreich!</h1>
        <p style={{ color: '#444', marginBottom: 8 }}>
          Dein Account wurde angelegt und wartet auf Freigabe durch einen Admin.
        </p>
        <p style={{ color: '#666', fontSize: 14, marginBottom: 32 }}>
          Sobald dein Account freigegeben wurde, kannst du dich einloggen.
        </p>
        <button onClick={() => navigate('/login')} style={{ padding: '10px 24px', fontSize: 16 }}>
          Zum Login
        </button>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 400, margin: '80px auto', padding: '0 16px' }}>
      <h1 style={{ marginBottom: 8 }}>Registrieren</h1>
      <p style={{ color: '#666', marginBottom: 24, fontSize: 14 }}>
        Nach der Registrierung muss dein Account von einem Admin freigegeben werden.
      </p>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="email">E-Mail</label>
          <input
            id="email"
            type="email"
            value={email}
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
            // minLength prüft der Browser selbst — kein extra JS nötig
            minLength={8}
            style={{ padding: '8px', fontSize: 16 }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="passwordConfirm">Passwort bestätigen</label>
          <input
            id="passwordConfirm"
            type="password"
            value={passwordConfirm}
            onChange={e => setPasswordConfirm(e.target.value)}
            required
            style={{ padding: '8px', fontSize: 16 }}
          />
        </div>

        {error && <p style={{ color: 'red', margin: 0 }}>{error}</p>}

        <button
          type="submit"
          disabled={loading}
          style={{ padding: '10px', fontSize: 16, cursor: loading ? 'not-allowed' : 'pointer' }}
        >
          {loading ? 'Registrieren...' : 'Registrieren'}
        </button>
      </form>

      {/* Link zurück zum Login */}
      <p style={{ marginTop: 24, textAlign: 'center', color: '#666', fontSize: 14 }}>
        Bereits registriert?{' '}
        <button
          onClick={() => navigate('/login')}
          style={{ background: 'none', border: 'none', color: '#0070f3', cursor: 'pointer', fontSize: 14, padding: 0 }}
        >
          Anmelden
        </button>
      </p>
    </div>
  )
}
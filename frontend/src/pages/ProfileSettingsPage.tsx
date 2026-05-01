// ProfileSettingsPage.tsx — Persönliche Einstellungen für jeden eingeloggten User.
// Abschnitt 1: Anzeigename (+ Avatar-Platzhalter für v0.2.x)
// Abschnitt 2: Module — nur Admin-freigegebene erscheinen zur Auswahl
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchProfileSettings, patchProfileSettings } from '../api/profile'
import type { ProfileSettings } from '../api/profile'
import { useModules } from '../context/useModules'

export default function ProfileSettingsPage() {
  const navigate = useNavigate()
  const { availableModules, reload } = useModules()
  const [profile, setProfile] = useState<ProfileSettings | null>(null)
  // Lokaler State für das Textfeld — wird beim Laden mit dem gespeicherten Wert befüllt
  const [displayNameInput, setDisplayNameInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [nameSaved, setNameSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchProfileSettings()
      .then(p => {
        setProfile(p)
        setDisplayNameInput(p.display_name ?? '')
      })
      .catch(() => setError('Profil konnte nicht geladen werden.'))
  }, [])

  async function saveDisplayName() {
    setSaving(true)
    setError(null)
    setNameSaved(false)
    try {
      // Leeres Textfeld → "" speichern (löscht den Namen in der DB)
      // null würde PATCH-Semantik auslösen ("kein Change") — "" ist das Lösch-Signal
      const updated = await patchProfileSettings({
        display_name: displayNameInput.trim(),
      })
      setProfile(updated)
      setNameSaved(true)
      // ModulesContext aktualisieren — displayName in der Onboarding-Card neu laden
      reload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function toggleModule(key: string, enabled: boolean) {
    if (!profile) return
    setSaving(true)
    setError(null)
    // Neues modules-Objekt: nur den einen Key ändern, alle anderen behalten
    const newModules = { ...profile.modules, [key]: enabled }
    try {
      const updated = await patchProfileSettings({ modules: newModules })
      setProfile(updated)
      // ModulesContext aktualisieren — activeModules und hasChosenModules neu berechnen
      reload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (!profile) {
    return <div style={{ padding: '2rem' }}>Lade Profil...</div>
  }

  return (
    <div style={{ maxWidth: 700, margin: '40px auto', padding: '0 16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Mein Profil</h1>
        <button onClick={() => navigate('/dashboard')} style={{ padding: '8px 16px' }}>
          Dashboard
        </button>
      </div>

      {error && <p style={{ color: 'red', marginTop: 8 }}>{error}</p>}

      <hr style={{ margin: '24px 0' }} />

      {/* Abschnitt 1: Profildaten */}
      <section>
        <h2>Profildaten</h2>

        <div style={{ marginBottom: 20 }}>
          <label style={{ display: 'block', marginBottom: 6, fontWeight: 500 }}>
            Anzeigename
          </label>
          <p style={{ color: '#666', fontSize: 14, margin: '0 0 8px' }}>
            Wird auf dem Dashboard zur Begrüßung angezeigt. Leer lassen = E-Mail-Adresse als Fallback.
          </p>
          <div style={{ display: 'flex', gap: 12 }}>
            <input
              type="text"
              value={displayNameInput}
              onChange={e => { setDisplayNameInput(e.target.value); setNameSaved(false) }}
              placeholder="z.B. Sparfuchs"
              maxLength={100}
              style={{ padding: '8px 12px', fontSize: 15, flex: 1 }}
            />
            <button
              onClick={saveDisplayName}
              disabled={saving}
              style={{ padding: '8px 16px' }}
            >
              {saving ? 'Speichert...' : 'Speichern'}
            </button>
          </div>
          {nameSaved && (
            <p style={{ color: 'green', marginTop: 6, fontSize: 14 }}>Gespeichert!</p>
          )}
        </div>

        {/* Avatar — Platzhalter, Upload folgt in v0.2.x */}
        <div style={{
          color: '#999',
          fontSize: 14,
          borderTop: '1px solid #f0f0f0',
          paddingTop: 12,
          fontStyle: 'italic',
        }}>
          Profilbild — Upload wird in einer zukünftigen Version verfügbar sein.
        </div>
      </section>

      <hr style={{ margin: '32px 0' }} />

      {/* Abschnitt 2: Module */}
      <section>
        <h2>Meine Module</h2>

        {availableModules.length === 0 ? (
          <p style={{ color: '#666' }}>
            Noch keine Module vom Admin freigegeben. Bitte wende dich an deinen Administrator.
          </p>
        ) : (
          <>
            <p style={{ color: '#666', marginBottom: 16 }}>
              Wähle welche Module du in deinem Dashboard sehen möchtest.
              Nur vom Admin freigegebene Module stehen zur Auswahl.
            </p>

            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #ddd' }}>
                  <th style={{ textAlign: 'left', padding: '8px 0', width: '25%' }}>Modul</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px' }}>Beschreibung</th>
                  <th style={{ textAlign: 'center', padding: '8px 0', width: '80px' }}>Aktiv</th>
                </tr>
              </thead>
              <tbody>
                {availableModules.map(module => (
                  <tr key={module.key} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '12px 0', fontWeight: 500 }}>{module.label}</td>
                    <td style={{ padding: '12px 12px', color: '#666' }}>{module.description}</td>
                    <td style={{ padding: '12px 0', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={profile.modules[module.key] === true}
                        onChange={e => toggleModule(module.key, e.target.checked)}
                        disabled={saving}
                        style={{ width: 18, height: 18, cursor: saving ? 'wait' : 'pointer' }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>

    </div>
  )
}

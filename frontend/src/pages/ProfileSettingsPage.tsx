// ProfileSettingsPage.tsx — Persönliche Einstellungen für jeden eingeloggten User.
// Abschnitt 1: Anzeigename (+ Avatar-Platzhalter für v0.2.x)
// Abschnitt 2: Module — nur Admin-freigegebene erscheinen zur Auswahl
import { useEffect, useState } from 'react'

import { fetchProfileSettings, patchProfileSettings } from '../api/profile'
import type { ProfileSettings } from '../api/profile'
import { useModules } from '../context/useModules'
import './ProfileSettingsPage.css'

export default function ProfileSettingsPage() {
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
    return <p className="settings-loading">Lade Profil…</p>
  }

  return (
    <div>

      <h1 className="page-title">Mein Profil</h1>

      {error && <p className="settings-error">{error}</p>}

      {/* ── Abschnitt 1: Profildaten ── */}
      <div className="settings-card">
        <h2>Profildaten</h2>

        <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--color-text-muted)', marginBottom: 4 }}>
          Anzeigename
        </label>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: '0 0 4px' }}>
          Wird auf dem Dashboard zur Begrüßung angezeigt. Leer lassen = E-Mail-Adresse als Fallback.
        </p>

        <div className="profile-name-row">
          <input
            className="profile-name-input"
            type="text"
            value={displayNameInput}
            onChange={e => { setDisplayNameInput(e.target.value); setNameSaved(false) }}
            placeholder="z. B. Sparfuchs"
            maxLength={100}
          />
          <button
            className="btn-primary"
            onClick={saveDisplayName}
            disabled={saving}
          >
            {saving ? 'Speichert…' : 'Speichern'}
          </button>
        </div>

        {nameSaved && <p className="profile-success">Gespeichert!</p>}

        {/* Avatar — Platzhalter, Upload folgt in v0.2.x */}
        <p className="profile-avatar-placeholder">
          Profilbild — Upload wird in einer zukünftigen Version verfügbar sein.
        </p>
      </div>

      {/* ── Abschnitt 2: Module ── */}
      <div className="settings-card">
        <h2>Meine Module</h2>

        {availableModules.length === 0 ? (
          <p className="profile-no-modules">
            Noch keine Module vom Admin freigegeben. Bitte wende dich an deinen Administrator.
          </p>
        ) : (
          <>
            <p>
              Wähle welche Module du in deinem Dashboard sehen möchtest.
              Nur vom Admin freigegebene Module stehen zur Auswahl.
            </p>

            <table className="settings-table">
              <thead>
                <tr>
                  <th>Modul</th>
                  <th>Beschreibung</th>
                  <th className="col-toggle">Aktiv</th>
                </tr>
              </thead>
              <tbody>
                {availableModules.map(module => (
                  <tr key={module.key}>
                    <td><span className="module-name">{module.label}</span></td>
                    <td><span className="module-desc">{module.description}</span></td>
                    <td className="col-toggle">
                      <input
                        className="settings-checkbox"
                        type="checkbox"
                        checked={profile.modules[module.key] === true}
                        onChange={e => toggleModule(module.key, e.target.checked)}
                        disabled={saving}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

    </div>
  )
}

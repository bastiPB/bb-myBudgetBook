// SettingsPage.tsx — Systemweite Einstellungen (nur Admin).
// Abschnitt 1: Module freischalten (alle aus MODULE_REGISTRY mit Checkbox)
// Abschnitt 2: Selbst-Registrierung ein/aus
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchSystemSettings, patchSystemSettings } from '../api/settings'
import type { SystemSettings } from '../api/settings'
import { useModules } from '../context/useModules'
import { MODULE_REGISTRY } from '../modules/registry'

export default function SettingsPage() {
  const navigate = useNavigate()
  const { reload } = useModules()
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchSystemSettings()
      .then(setSettings)
      .catch(() => setError('Einstellungen konnten nicht geladen werden.'))
  }, [])

  async function toggleModule(key: string, enabled: boolean) {
    if (!settings) return
    setSaving(true)
    setError(null)
    // Neues modules-Objekt: nur den einen Key ändern, alle anderen behalten
    const newModules = { ...settings.modules, [key]: enabled }
    try {
      const updated = await patchSystemSettings({ modules: newModules })
      setSettings(updated)
      // ModulesContext aktualisieren — availableModules und activeModules neu berechnen
      reload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function toggleSignup(enabled: boolean) {
    if (!settings) return
    setSaving(true)
    setError(null)
    try {
      const updated = await patchSystemSettings({ email_signup_enabled: enabled })
      setSettings(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (!settings) {
    return <div style={{ padding: '2rem' }}>Lade Einstellungen...</div>
  }

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: '0 16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>System-Einstellungen</h1>
        <button onClick={() => navigate('/dashboard')} style={{ padding: '8px 16px' }}>
          Dashboard
        </button>
      </div>
      <p style={{ color: '#666', marginTop: 4 }}>
        Änderungen gelten sofort für alle User.
      </p>

      {error && <p style={{ color: 'red', marginTop: 8 }}>{error}</p>}

      <hr style={{ margin: '24px 0' }} />

      {/* Abschnitt 1: Module */}
      <section>
        <h2>Module</h2>
        <p style={{ color: '#666', marginBottom: 16 }}>
          Lege fest, welche Module systemweit verfügbar sind.
          User können nur aus freigegebenen Modulen für ihr Dashboard wählen.
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
            {MODULE_REGISTRY.map(module => (
              <tr key={module.key} style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '12px 0', fontWeight: 500 }}>{module.label}</td>
                <td style={{ padding: '12px 12px', color: '#666' }}>{module.description}</td>
                <td style={{ padding: '12px 0', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={settings.modules[module.key] === true}
                    onChange={e => toggleModule(module.key, e.target.checked)}
                    disabled={saving}
                    style={{ width: 18, height: 18, cursor: saving ? 'wait' : 'pointer' }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <hr style={{ margin: '32px 0' }} />

      {/* Abschnitt 2: Selbst-Registrierung */}
      <section>
        <h2>Selbst-Registrierung</h2>
        <p style={{ color: '#666', marginBottom: 16 }}>
          Wenn aktiv, können neue User sich unter /register selbst einen Account anlegen
          (wartet dann auf Admin-Freigabe). Wenn deaktiviert, kann nur der Admin neue
          Accounts erstellen.
        </p>
        <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={settings.email_signup_enabled}
            onChange={e => toggleSignup(e.target.checked)}
            disabled={saving}
            style={{ width: 18, height: 18 }}
          />
          <span>Selbst-Registrierung über /register erlauben</span>
        </label>
      </section>

    </div>
  )
}

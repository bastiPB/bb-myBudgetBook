// SettingsPage.tsx — Systemweite Einstellungen (nur Admin).
// Abschnitt 1: Module freischalten (alle aus MODULE_REGISTRY mit Checkbox)
// Abschnitt 2: Selbst-Registrierung ein/aus
import { useEffect, useState } from 'react'

import { triggerScheduledPayments } from '../api/admin'
import {
  fetchSystemSettings,
  patchSystemSettings,
  SCHEDULER_CATCH_UP_DAYS_MAX,
} from '../api/settings'
import type { SystemSettings } from '../api/settings'
import { useModules } from '../context/useModules'
import { MODULE_REGISTRY } from '../modules/registry'
import './SettingsPage.css'

export default function SettingsPage() {
  const { reload } = useModules()
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // State für Scheduler-Trigger (Abschnitt 3)
  const [triggerResult, setTriggerResult] = useState<string | null>(null)
  const [triggering, setTriggering] = useState(false)
  // Lokaler Entwurf für Scheduler-Felder (Speichern erst auf Klick)
  const [schedulerTime, setSchedulerTime] = useState('03:00')
  const [catchUpDays, setCatchUpDays] = useState(60)

  useEffect(() => {
    fetchSystemSettings()
      .then(s => {
        setSettings(s)
        // Entwurf initial aus Serverwerten setzen (ohne extra useEffect → ESLint-konform)
        setSchedulerTime(s.scheduler_time)
        setCatchUpDays(s.scheduler_catch_up_days)
      })
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

  async function saveSchedulerSettings() {
    if (!settings) return
    if (catchUpDays > SCHEDULER_CATCH_UP_DAYS_MAX || catchUpDays < 0) {
      setError(`Maximal ${SCHEDULER_CATCH_UP_DAYS_MAX} Tage rückwirkend erlaubt.`)
      return
    }
    setSaving(true)
    setError(null)
    try {
      const updated = await patchSystemSettings({
        scheduler_time: schedulerTime,
        scheduler_catch_up_days: catchUpDays,
      })
      setSettings(updated)
      // Nach erfolgreichem Speichern Entwurf mit Serverzustand synchronisieren
      setSchedulerTime(updated.scheduler_time)
      setCatchUpDays(updated.scheduler_catch_up_days)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function runScheduler() {
    setTriggering(true)
    setTriggerResult(null)
    setError(null)
    try {
      const result = await triggerScheduledPayments()
      setTriggerResult(`${result.created} neue Buchung(en) erzeugt.`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setTriggering(false)
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
    return <p className="settings-loading">Lade Einstellungen…</p>
  }

  return (
    <div>

      <h1 className="page-title">Systemeinstellungen</h1>
      <p className="settings-subtitle">Änderungen gelten sofort für alle User.</p>

      {error && <p className="settings-error">{error}</p>}

      {/* ── Abschnitt 1: Module ── */}
      <div className="settings-card">
        <h2>Module</h2>
        <p>
          Lege fest, welche Module systemweit verfügbar sind.
          User können nur aus freigegebenen Modulen für ihr Dashboard wählen.
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
            {MODULE_REGISTRY.map(module => (
              <tr key={module.key}>
                <td><span className="module-name">{module.label}</span></td>
                <td><span className="module-desc">{module.description}</span></td>
                <td className="col-toggle">
                  <input
                    className="settings-checkbox"
                    type="checkbox"
                    checked={settings.modules[module.key] === true}
                    onChange={e => toggleModule(module.key, e.target.checked)}
                    disabled={saving}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Abschnitt 2: Selbst-Registrierung ── */}
      <div className="settings-card">
        <h2>Selbst-Registrierung</h2>
        <p>
          Wenn aktiv, können neue User sich unter /register selbst einen Account anlegen
          (wartet dann auf Admin-Freigabe). Wenn deaktiviert, kann nur der Admin neue
          Accounts erstellen.
        </p>
        <label className="settings-toggle-row">
          <input
            type="checkbox"
            checked={settings.email_signup_enabled}
            onChange={e => toggleSignup(e.target.checked)}
            disabled={saving}
          />
          <span className="settings-toggle-label">
            Selbst-Registrierung über /register erlauben
          </span>
        </label>
      </div>

      {/* ── Abschnitt 3: Scheduler ── */}
      <div className="settings-card">
        <h2>Buchungs-Scheduler</h2>
        <p>
          Der Scheduler läuft täglich automatisch und erzeugt Soll-Buchungen für alle Abos,
          bei denen der User die Buchungshistorie aktiviert hat.
          Uhrzeit und Catch-up-Fenster gelten nach Speichern ohne App-Neustart (täglicher Lauf).
        </p>
        <div className="settings-scheduler-form">
          <label className="settings-field-label">
            Tägliche Laufzeit (Server-Uhrzeit)
            <input
              type="time"
              value={schedulerTime}
              onChange={e => setSchedulerTime(e.target.value)}
              disabled={saving}
              className="settings-input-time"
            />
          </label>
          <label className="settings-field-label">
            Catch-up (max. {SCHEDULER_CATCH_UP_DAYS_MAX} Tage)
            <input
              type="number"
              min={0}
              max={SCHEDULER_CATCH_UP_DAYS_MAX}
              value={catchUpDays}
              onChange={e => setCatchUpDays(Number(e.target.value))}
              disabled={saving}
              className="settings-input-number"
            />
          </label>
          <p className="settings-hint">
            Verpasste Fälligkeiten werden höchstens so viele Tage in die Vergangenheit nachgetragen
            (z.&nbsp;B. nach längerem Ausfall). Maximal {SCHEDULER_CATCH_UP_DAYS_MAX} Tage.
          </p>
          <button type="button" className="btn-primary" onClick={saveSchedulerSettings} disabled={saving}>
            {saving ? 'Speichern…' : 'Scheduler-Einstellungen speichern'}
          </button>
        </div>
        <p style={{ marginTop: '1rem' }}>
          Manuell auslösen — z.&nbsp;B. nach einem Neustart oder zum Testen.
          Der Vorgang ist idempotent: bereits vorhandene Einträge werden nicht doppelt erzeugt.
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <button className="btn-primary" onClick={runScheduler} disabled={triggering}>
            {triggering ? 'Läuft…' : 'Jetzt ausführen'}
          </button>
          {triggerResult && (
            <span style={{ fontSize: 13, color: 'var(--color-success, green)' }}>
              {triggerResult}
            </span>
          )}
        </div>
      </div>

    </div>
  )
}

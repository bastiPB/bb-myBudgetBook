// SubscriptionDetailPage.tsx — Detailansicht eines einzelnen Abos (Slice C).
//
// Zeigt:
//   - Kostenkarten (monatlich / jährlich / kumuliert)
//   - Alle Stammdaten (Abschlussdatum, Fälligkeit, Intervall, Status)
//   - Notizen mit Inline-Bearbeitung
//   - Pausieren / Fortsetzen Aktionen
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { getLogoUrl, getPriceHistory, getSubscription, resumeSubscription, suspendSubscription, updateSubscription, uploadSubscriptionLogo } from '../api/subscriptions'
import type { PriceHistoryEntry, SubscriptionDetail, SubscriptionStatus } from '../types/subscription'
import { formatAmount, formatDate, INTERVAL_LABELS, STATUS_LABELS } from '../types/subscription'
// SubscriptionsPage.css enthält die gemeinsamen Button-Klassen (btn-primary-sm, btn-outline-sm etc.)
import './SubscriptionsPage.css'
import './SubscriptionDetailPage.css'

// Kleines Status-Badge — gleiche Logik wie in SubscriptionsPage
function StatusBadge({ status }: { status: SubscriptionStatus }) {
  return (
    <span className={`detail-status-badge detail-status-${status}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

// Eine Kostenkarte mit Bezeichnung, formatiertem Betrag und optionalem Hinweis
function CostCard({ label, amount, hint }: { label: string; amount: string; hint?: string }) {
  return (
    <div className="detail-cost-card">
      <span className="detail-cost-label">{label}</span>
      <span className="detail-cost-value">{formatAmount(amount)} €</span>
      {hint && <span className="detail-cost-hint">{hint}</span>}
    </div>
  )
}

export default function SubscriptionDetailPage() {
  // :id aus der URL lesen — z. B. /subscriptions/abc-123 → id = "abc-123"
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [sub, setSub] = useState<SubscriptionDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Preishistorie (Slice E)
  const [priceHistory, setPriceHistory] = useState<PriceHistoryEntry[]>([])

  // Logo-Upload
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [logoLoading, setLogoLoading] = useState(false)
  const [logoError, setLogoError] = useState<string | null>(null)

  // Notizen-Inline-Bearbeitung
  const [notesEditing, setNotesEditing] = useState(false)
  const [notesValue, setNotesValue] = useState('')
  const [notesLoading, setNotesLoading] = useState(false)
  const [notesError, setNotesError] = useState<string | null>(null)

  // Abo und Preishistorie beim ersten Rendern parallel laden.
  // Promise.all: beide Requests laufen gleichzeitig — kürzer als nacheinander.
  useEffect(() => {
    if (!id) return
    Promise.all([getSubscription(id), getPriceHistory(id)])
      .then(([data, history]) => {
        setSub(data)
        setNotesValue(data.notes ?? '')
        setPriceHistory(history)
      })
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Ladefehler'))
  }, [id])

  // Abo pausieren — navigiert nicht weg, aktualisiert nur den State
  async function handleSuspend() {
    if (!sub) return
    if (!window.confirm(`"${sub.name}" pausieren?`)) return
    try {
      await suspendSubscription(sub.id, {})
      // getSubscription erneut aufrufen damit computed fields aktuell bleiben
      const detail = await getSubscription(sub.id)
      setSub(detail)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Fehler beim Pausieren.')
    }
  }

  // Pausiertes Abo wieder fortsetzen
  async function handleResume() {
    if (!sub) return
    if (!window.confirm(`"${sub.name}" wieder fortsetzen?`)) return
    try {
      await resumeSubscription(sub.id)
      const detail = await getSubscription(sub.id)
      setSub(detail)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Fehler beim Fortsetzen.')
    }
  }

  // Logo hochladen — Datei-Input löst diesen Handler aus
  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !sub) return
    setLogoError(null)
    setLogoLoading(true)
    try {
      const updated = await uploadSubscriptionLogo(sub.id, file)
      // Nur logo_url aktualisieren — computed fields bleiben wie sie sind
      setSub(prev => prev ? { ...prev, logo_url: updated.logo_url } : prev)
    } catch (err) {
      setLogoError(err instanceof Error ? err.message : 'Fehler beim Hochladen.')
    } finally {
      setLogoLoading(false)
      // Input zurücksetzen damit dieselbe Datei erneut gewählt werden kann
      e.target.value = ''
    }
  }

  // Notizen speichern — sendet nur das notes-Feld per PATCH
  async function handleSaveNotes(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!sub) return
    setNotesError(null)
    setNotesLoading(true)
    try {
      // model_fields_set im Backend: notes wird explizit gesetzt (auch wenn null)
      await updateSubscription(sub.id, { notes: notesValue || null })
      setSub(prev => prev ? { ...prev, notes: notesValue || null } : prev)
      setNotesEditing(false)
    } catch (err) {
      setNotesError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setNotesLoading(false)
    }
  }

  if (loadError) return <p className="detail-load-error">Fehler: {loadError}</p>
  if (!sub) return <p className="detail-loading">Wird geladen…</p>

  return (
    <div className="detail-page">

      {/* Zurück-Navigation */}
      <button className="detail-back-btn" onClick={() => navigate('/subscriptions')}>
        ← Zurück zur Liste
      </button>

      {/* Kopfbereich: Logo + Name + Status */}
      <div className="detail-header">

        {/* Logo-Bereich: zeigt Bild oder Fallback-Buchstaben, Upload-Button unten-rechts */}
        <div className="detail-logo-wrap">
          {sub.logo_url ? (
            <img
              src={getLogoUrl(sub.logo_url)!}
              alt={`${sub.name} Logo`}
              className="detail-logo-img"
            />
          ) : (
            <div className="detail-logo-fallback">
              {sub.name.charAt(0).toUpperCase()}
            </div>
          )}
          {/* Versteckter File-Input — wird per Button-Klick ausgelöst */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            style={{ display: 'none' }}
            onChange={handleLogoUpload}
          />
          <button
            className="detail-logo-upload-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Logo hochladen (JPEG, PNG, WebP, max. 2 MB)"
            disabled={logoLoading}
          >
            {logoLoading ? '…' : '↑'}
          </button>
        </div>

        <div className="detail-header-info">
          <h1 className="detail-name">{sub.name}</h1>
          <StatusBadge status={sub.status} />
          {logoError && <p className="detail-logo-error">{logoError}</p>}
        </div>

      </div>

      {/* Kostenkarten — drei Kennzahlen nebeneinander */}
      <div className="detail-cost-cards">
        <CostCard label="Monatlich" amount={sub.monthly_cost_normalized} />
        <CostCard label="Jährlich" amount={sub.yearly_cost_normalized} />
        <CostCard
          label="Bisher gezahlt"
          amount={sub.total_paid_estimate}
          hint="Schätzung auf Basis des aktuellen Preises"
        />
      </div>

      {/* Stammdaten */}
      <div className="detail-card">
        <h2 className="detail-section-title">Details</h2>
        <dl className="detail-dl">
          <dt>Intervall</dt>
          <dd>{INTERVAL_LABELS[sub.interval]}</dd>

          <dt>Aktueller Betrag</dt>
          <dd>{formatAmount(sub.amount)} €</dd>

          <dt>Abgeschlossen am</dt>
          <dd>{formatDate(sub.started_on)}</dd>

          <dt>Nächste Fälligkeit</dt>
          <dd>{formatDate(sub.next_due_date)}</dd>

          {sub.suspended_at && (
            <>
              <dt>Pausiert seit</dt>
              <dd>{formatDate(sub.suspended_at)}</dd>
            </>
          )}
          {sub.access_until && (
            <>
              <dt>Zugang bis</dt>
              <dd>{formatDate(sub.access_until)}</dd>
            </>
          )}
        </dl>
      </div>

      {/* Notizen */}
      <div className="detail-card">
        <h2 className="detail-section-title">Notizen</h2>
        {notesEditing ? (
          <form onSubmit={handleSaveNotes}>
            <textarea
              className="detail-notes-textarea"
              value={notesValue}
              onChange={e => setNotesValue(e.target.value)}
              placeholder="Notizen zum Abo…"
              rows={4}
              autoFocus
            />
            {notesError && <p className="detail-notes-error">{notesError}</p>}
            <div className="detail-notes-actions">
              <button type="submit" className="btn-primary-sm" disabled={notesLoading}>
                {notesLoading ? '…' : 'Speichern'}
              </button>
              <button
                type="button"
                className="btn-outline-sm"
                onClick={() => { setNotesEditing(false); setNotesValue(sub.notes ?? '') }}
              >
                Abbrechen
              </button>
            </div>
          </form>
        ) : (
          <div className="detail-notes-view">
            <p className="detail-notes-text">
              {sub.notes || <span className="detail-notes-empty">Keine Notizen</span>}
            </p>
            <button className="btn-outline-sm" onClick={() => setNotesEditing(true)}>
              Bearbeiten
            </button>
          </div>
        )}
      </div>

      {/* Preishistorie (Slice E) */}
      <div className="detail-card">
        <h2 className="detail-section-title">Preishistorie</h2>
        {priceHistory.length === 0 ? (
          <p className="detail-ph-empty">Keine Preisänderungen erfasst.</p>
        ) : (
          <table className="detail-ph-table">
            <thead>
              <tr>
                <th>Gültig ab</th>
                <th>Betrag</th>
              </tr>
            </thead>
            <tbody>
              {priceHistory.map((entry, i) => (
                <tr key={entry.id} className={i === 0 ? 'detail-ph-current' : ''}>
                  <td>{formatDate(entry.valid_from)}</td>
                  <td>{formatAmount(entry.amount)} €</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Aktionen */}
      <div className="detail-actions">
        {sub.status === 'active' && (
          <button className="btn-outline-sm detail-btn-suspend" onClick={handleSuspend}>
            Pausieren
          </button>
        )}
        {sub.status === 'suspended' && (
          <button className="btn-outline-sm detail-btn-resume" onClick={handleResume}>
            Fortsetzen
          </button>
        )}
      </div>

    </div>
  )
}

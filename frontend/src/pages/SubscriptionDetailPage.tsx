// SubscriptionDetailPage.tsx — Detailansicht eines einzelnen Abos (v0.2.3).
//
// Zeigt:
//   - Vier Kostenkennzahlen (Monatlich / Dieses Jahr / Intervalle / Tatsächlich)
//   - Alle Stammdaten (Abschlussdatum, Fälligkeit, Intervall, Status)
//   - Preisänderungs-Formular mit Wirkungsdatum
//   - Notizen mit Inline-Bearbeitung
//   - Pausieren / Fortsetzen / Kündigen (mit Modal)
//   - Preishistorie + Buchungshistorie
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import ConfirmModal from '../components/ConfirmModal'
import {
  cancelSubscription,
  getLogoUrl,
  getPriceHistory,
  getScheduledPayments,
  getSubscription,
  priceChange,
  resumeSubscription,
  suspendSubscription,
  updateSubscription,
  uploadSubscriptionLogo,
} from '../api/subscriptions'
import type { PriceHistoryEntry, ScheduledPaymentEntry, SubscriptionDetail, SubscriptionStatus } from '../types/subscription'
import { formatAmount, formatDate, INTERVAL_LABELS, parseAmount, PAYMENT_STATUS_LABELS, STATUS_LABELS } from '../types/subscription'
// SubscriptionsPage.css enthält die gemeinsamen Button-Klassen
import './SubscriptionsPage.css'
import './SubscriptionDetailPage.css'

// Typ für den Modal-State
type ModalState = {
  title: string
  body?: string
  dangerous?: boolean
  confirmText?: string
  onConfirm: () => void
}

function StatusBadge({ status }: { status: SubscriptionStatus }) {
  return (
    <span className={`detail-status-badge detail-status-${status}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

// Eine Kostenkarte mit Bezeichnung, formatiertem Wert und optionalem Hinweis.
// valueStr: bereits formatierter String (z. B. "9,99 €" oder "12")
function CostCard({ label, valueStr, hint }: { label: string; valueStr: string; hint?: string }) {
  return (
    <div className="detail-cost-card">
      <span className="detail-cost-label">{label}</span>
      <span className="detail-cost-value">{valueStr}</span>
      {hint && <span className="detail-cost-hint">{hint}</span>}
    </div>
  )
}

export default function SubscriptionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [sub, setSub] = useState<SubscriptionDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [priceHistory, setPriceHistory] = useState<PriceHistoryEntry[]>([])
  const [scheduledPayments, setScheduledPayments] = useState<ScheduledPaymentEntry[]>([])

  // Logo-Upload
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [logoLoading, setLogoLoading] = useState(false)
  const [logoError, setLogoError] = useState<string | null>(null)

  // Notizen-Inline-Bearbeitung
  const [notesEditing, setNotesEditing] = useState(false)
  const [notesValue, setNotesValue] = useState('')
  const [notesLoading, setNotesLoading] = useState(false)
  const [notesError, setNotesError] = useState<string | null>(null)

  // Preisänderungs-Formular
  const [showPriceForm, setShowPriceForm] = useState(false)
  const [priceForm, setPriceForm] = useState({ amount: '', valid_from: '' })
  const [priceLoading, setPriceLoading] = useState(false)
  const [priceError, setPriceError] = useState<string | null>(null)

  // Bestätigungs-Modal (Pausieren, Fortsetzen, Kündigen)
  const [modal, setModal] = useState<ModalState | null>(null)

  // Abo + Preishistorie + Buchungshistorie beim ersten Rendern parallel laden
  useEffect(() => {
    if (!id) return
    Promise.all([getSubscription(id), getPriceHistory(id), getScheduledPayments(id)])
      .then(([data, history, payments]) => {
        setSub(data)
        setNotesValue(data.notes ?? '')
        setPriceHistory(history)
        setScheduledPayments(payments)
      })
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Ladefehler'))
  }, [id])

  // --- Hilfe: Abo neu laden (nach Preis- oder Status-Änderung) ---
  async function reloadSub() {
    if (!id) return
    const [data, history] = await Promise.all([getSubscription(id), getPriceHistory(id)])
    setSub(data)
    setPriceHistory(history)
  }

  // --- Abo pausieren ---
  function handleSuspend() {
    if (!sub) return
    setModal({
      title: `"${sub.name}" pausieren?`,
      body: 'Das Abo bleibt gespeichert. Du kannst es jederzeit fortsetzen.',
      onConfirm: () => {
        setModal(null)
        suspendSubscription(sub.id, {})
          .then(() => reloadSub())
          .catch(err => alert(err instanceof Error ? err.message : 'Fehler beim Pausieren.'))
      },
    })
  }

  // --- Abo fortsetzen ---
  function handleResume() {
    if (!sub) return
    setModal({
      title: `"${sub.name}" fortsetzen?`,
      onConfirm: () => {
        setModal(null)
        resumeSubscription(sub.id)
          .then(() => reloadSub())
          .catch(err => alert(err instanceof Error ? err.message : 'Fehler beim Fortsetzen.'))
      },
    })
  }

  // --- Abo kündigen — Sicherheits-Modal (User muss Namen eintippen) ---
  function handleCancel() {
    if (!sub) return
    setModal({
      title: `"${sub.name}" kündigen?`,
      body: 'Das Abo wird als "Beendet" markiert. Der Eintrag bleibt als Archiv erhalten.',
      dangerous: true,
      confirmText: sub.name,
      onConfirm: () => {
        setModal(null)
        cancelSubscription(sub.id)
          .then(updated => setSub(updated))
          .catch(err => alert(err instanceof Error ? err.message : 'Fehler beim Kündigen.'))
      },
    })
  }

  // --- Logo hochladen ---
  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !sub) return
    setLogoError(null)
    setLogoLoading(true)
    try {
      const updated = await uploadSubscriptionLogo(sub.id, file)
      setSub(prev => prev ? { ...prev, logo_url: updated.logo_url } : prev)
    } catch (err) {
      setLogoError(err instanceof Error ? err.message : 'Fehler beim Hochladen.')
    } finally {
      setLogoLoading(false)
      e.target.value = ''
    }
  }

  // --- Notizen speichern ---
  async function handleSaveNotes(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!sub) return
    setNotesError(null)
    setNotesLoading(true)
    try {
      await updateSubscription(sub.id, { notes: notesValue || null })
      setSub(prev => prev ? { ...prev, notes: notesValue || null } : prev)
      setNotesEditing(false)
    } catch (err) {
      setNotesError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setNotesLoading(false)
    }
  }

  // --- Preisänderung speichern ---
  async function handlePriceChange(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!sub) return
    setPriceError(null)

    const amountNum = parseAmount(priceForm.amount)
    if (isNaN(amountNum) || amountNum <= 0) {
      setPriceError('Bitte einen gültigen Betrag eingeben (z. B. 9,99).')
      return
    }
    if (!priceForm.valid_from) {
      setPriceError('Bitte ein Wirkungsdatum angeben.')
      return
    }

    setPriceLoading(true)
    try {
      const updated = await priceChange(sub.id, { amount: amountNum, valid_from: priceForm.valid_from })
      setSub(updated)
      // Preishistorie separat neu laden damit die Tabelle aktuell ist
      const history = await getPriceHistory(sub.id)
      setPriceHistory(history)
      setPriceForm({ amount: '', valid_from: '' })
      setShowPriceForm(false)
    } catch (err) {
      setPriceError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setPriceLoading(false)
    }
  }

  if (loadError) return <p className="detail-load-error">Fehler: {loadError}</p>
  if (!sub) return <p className="detail-loading">Wird geladen…</p>

  // Prüfen ob eine Preisankündigung in der Zukunft liegt
  const today = new Date().toISOString().slice(0, 10)
  const futurePrice = priceHistory.find(p => p.valid_from > today)

  return (
    <div className="detail-page">

      {/* Bestätigungs-Modal */}
      {modal && (
        <ConfirmModal
          title={modal.title}
          body={modal.body}
          dangerous={modal.dangerous}
          confirmText={modal.confirmText}
          onConfirm={modal.onConfirm}
          onCancel={() => setModal(null)}
        />
      )}

      {/* Zurück-Navigation */}
      <button className="detail-back-btn" onClick={() => navigate('/subscriptions')}>
        ← Zurück zur Liste
      </button>

      {/* Kopfbereich: Logo + Name + Status */}
      <div className="detail-header">
        <div className="detail-logo-wrap">
          {sub.logo_url ? (
            <img src={getLogoUrl(sub.logo_url)!} alt={`${sub.name} Logo`} className="detail-logo-img" />
          ) : (
            <div className="detail-logo-fallback">{sub.name.charAt(0).toUpperCase()}</div>
          )}
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
          {/* Badge für angekündigte Preisänderung */}
          {futurePrice && (
            <span className="detail-price-announcement">
              Preisänderung ab {formatDate(futurePrice.valid_from)}: {formatAmount(futurePrice.amount)} €
            </span>
          )}
          {logoError && <p className="detail-logo-error">{logoError}</p>}
        </div>
      </div>

      {/* Kostenkennzahlen — vier Karten (v0.2.3) */}
      <div className="detail-cost-cards">
        <CostCard
          label="Monatlich"
          valueStr={`${formatAmount(sub.monatlich)} €`}
        />
        <CostCard
          label="Dieses Jahr"
          valueStr={`${formatAmount(sub.dieses_kalenderjahr)} €`}
          hint="inkl. Preisankündigungen"
        />
        <CostCard
          label="Intervalle"
          valueStr={String(sub.intervalle)}
          hint="Zahlungsperioden seit Beginn"
        />
        <CostCard
          label="Tatsächlich ~"
          valueStr={`${formatAmount(sub.tatsaechlich)} €`}
          hint="Summe bezahlter Perioden"
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
          {/* next_due_date kann null sein wenn started_on in der Zukunft liegt */}
          <dd>{sub.next_due_date ? formatDate(sub.next_due_date) : '—'}</dd>
        </dl>
      </div>

      {/* Preisänderung */}
      <div className="detail-card">
        <div className="detail-section-header">
          <h2 className="detail-section-title">Preisänderung</h2>
          {!showPriceForm && (
            <button className="btn-outline-sm" onClick={() => setShowPriceForm(true)}>
              Preis ändern
            </button>
          )}
        </div>

        {showPriceForm && (
          <form className="detail-price-form" onSubmit={handlePriceChange}>
            <div className="detail-price-form-row">
              {/* type="text" damit Komma als Dezimaltrennzeichen akzeptiert wird */}
              <input
                className="subs-input subs-input-sm"
                placeholder="Neuer Betrag (z. B. 12,99)"
                value={priceForm.amount}
                onChange={e => setPriceForm(f => ({ ...f, amount: e.target.value }))}
                required
                autoFocus
              />
              <input
                className="subs-input subs-input-sm"
                type="date"
                title="Wirkungsdatum (Vergangenheit, heute oder Zukunft)"
                value={priceForm.valid_from}
                onChange={e => setPriceForm(f => ({ ...f, valid_from: e.target.value }))}
                required
              />
            </div>
            {priceError && <p className="detail-notes-error">{priceError}</p>}
            <div className="detail-notes-actions">
              <button type="submit" className="btn-primary-sm" disabled={priceLoading}>
                {priceLoading ? '…' : 'Speichern'}
              </button>
              <button
                type="button"
                className="btn-outline-sm"
                onClick={() => { setShowPriceForm(false); setPriceForm({ amount: '', valid_from: '' }); setPriceError(null) }}
              >
                Abbrechen
              </button>
            </div>
          </form>
        )}
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

      {/* Preishistorie */}
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

      {/* Buchungshistorie — nur anzeigen wenn Einträge vorhanden */}
      {scheduledPayments.length > 0 && (
        <div className="detail-card">
          <h2 className="detail-section-title">Buchungshistorie</h2>
          <table className="detail-ph-table">
            <thead>
              <tr>
                <th>Fälligkeit</th>
                <th>Betrag</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {scheduledPayments.map(entry => (
                <tr key={entry.id} className={`detail-payment-${entry.status}`}>
                  <td>{formatDate(entry.due_date)}</td>
                  {/* amount ist null bei pausierten Perioden */}
                  <td>{entry.amount ? `${formatAmount(entry.amount)} €` : '—'}</td>
                  <td>
                    <span className={`detail-payment-badge detail-payment-badge--${entry.status}`}>
                      {PAYMENT_STATUS_LABELS[entry.status]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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
        {sub.status !== 'canceled' && (
          <button className="btn-danger" onClick={handleCancel}>
            Abo kündigen
          </button>
        )}
      </div>

    </div>
  )
}

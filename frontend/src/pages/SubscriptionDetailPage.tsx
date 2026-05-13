// SubscriptionDetailPage.tsx — Detailansicht eines einzelnen Abos (v0.2.4).
//
// Zeigt:
//   - Vier Kostenkennzahlen (Monatlich / Dieses Jahr / Intervalle / Tatsächlich)
//   - Alle Stammdaten (Abschlussdatum, Fälligkeit, Intervall, Status)
//   - Preisänderungs-Formular mit Wirkungsdatum
//   - Intervallwechsel-Formular (v0.2.4): Betrag + Intervall + Datum gemeinsam ändern
//   - Notizen mit Inline-Bearbeitung
//   - Pausieren / Fortsetzen / Kündigen (mit Modal)
//   - Preishistorie + Abrechnungshistorie (v0.2.4) + Buchungshistorie
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import ConfirmModal from '../components/ConfirmModal'
import InfoModal from '../components/InfoModal'
import TagBadge from '../components/TagBadge'
import TagManagementModal from '../components/TagManagementModal'
import { getTags, setSubscriptionTags } from '../api/tags'
import type { TagRead } from '../types/tag'
import {
  cancelSubscription,
  deleteBillingHistoryEntry,
  deletePriceHistoryEntry,
  getBillingHistory,
  getLogoUrl,
  getPriceHistory,
  getScheduledPayments,
  getSubscription,
  intervalChange,
  priceChange,
  resumeSubscription,
  suspendSubscription,
  updateSubscription,
  uploadSubscriptionLogo,
} from '../api/subscriptions'
import type {
  BillingHistoryEntry,
  BillingInterval,
  PriceHistoryEntry,
  ScheduledPaymentEntry,
  SubscriptionDetail,
  SubscriptionStatus,
} from '../types/subscription'
import {
  formatAmount,
  formatDate,
  INTERVAL_LABELS,
  parseAmount,
  PAYMENT_STATUS_LABELS,
  STATUS_LABELS,
} from '../types/subscription'
// SubscriptionsPage.css enthält die gemeinsamen Button-Klassen
import './SubscriptionsPage.css'
import './SubscriptionDetailPage.css'

// Alle Intervalle in der gewünschten Reihenfolge für das Intervallwechsel-Dropdown
const INTERVALS: BillingInterval[] = ['monthly', 'quarterly', 'semiannual', 'yearly', 'biennial']

const MONTHS_PER_PERIOD: Record<BillingInterval, number> = {
  monthly: 1,
  quarterly: 3,
  semiannual: 6,
  yearly: 12,
  biennial: 24,
}

function parseAmountInput(input: string): number | null {
  // UI-Helfer: "12,99" oder "12.99" erlauben. Keine Validierung von Währung/Locale hier.
  const normalized = input.trim().replace(',', '.')
  const n = Number(normalized)
  return Number.isFinite(n) ? n : null
}

// Typ für den Bestätigungs-Modal-State
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
  const [billingHistory, setBillingHistory] = useState<BillingHistoryEntry[]>([])
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

  // Preisänderungs-Formular — ändert nur den Betrag, Intervall bleibt gleich
  const [showPriceForm, setShowPriceForm] = useState(false)
  const [priceForm, setPriceForm] = useState({ amount: '', valid_from: '' })
  const [priceLoading, setPriceLoading] = useState(false)
  const [priceError, setPriceError] = useState<string | null>(null)

  // Intervallwechsel-Formular (v0.2.4) — ändert Betrag + Intervall gemeinsam
  const [showIntervalForm, setShowIntervalForm] = useState(false)
  const [intervalForm, setIntervalForm] = useState({
    amount: '',
    interval: 'monthly' as BillingInterval,
    valid_from: '',
  })
  const [intervalLoading, setIntervalLoading] = useState(false)
  const [intervalError, setIntervalError] = useState<string | null>(null)
  // Zwei-Phasen-Flow: User bestätigt bewusst dass vorhandene Buchungen betroffen sind (409-Flow)
  const [intervalAcknowledge, setIntervalAcknowledge] = useState(false)
  // Kurze Abrechnungsphase (z.B. jährlich nur 2 Monate bis zum nächsten Historien-Eintrag)
  const [intervalAcknowledgeShortSegment, setIntervalAcknowledgeShortSegment] = useState(false)

  // Bestätigungs-Modal (Pausieren, Fortsetzen, Kündigen, Einträge löschen)
  const [modal, setModal] = useState<ModalState | null>(null)

  // Info/Fehler-Modal — zeigt Fehlermeldungen der API als Overlay an
  const [infoModal, setInfoModal] = useState<{ title: string; body: string } | null>(null)

  // Tags (v0.2.7)
  const [allTags, setAllTags] = useState<TagRead[]>([])
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([])
  const [showTagModal, setShowTagModal] = useState(false)
  const [tagPickerOpen, setTagPickerOpen] = useState(false)
  const [tagError, setTagError] = useState<string | null>(null)
  const tagPickerRef = useRef<HTMLDivElement>(null)

  // Abo + Preishistorie + Abrechnungshistorie + Buchungshistorie beim ersten Rendern parallel laden
  useEffect(() => {
    if (!id) return
    Promise.all([
      getSubscription(id),
      getPriceHistory(id),
      getScheduledPayments(id),
      getBillingHistory(id),
      getTags(),
    ])
      .then(([data, history, payments, billing, tags]) => {
        setSub(data)
        setNotesValue(data.notes ?? '')
        setPriceHistory(history)
        setScheduledPayments(payments)
        setBillingHistory(billing)
        setAllTags(tags)
        // Aktuelle Tag-Auswahl aus den geladenen Abo-Daten initialisieren
        setSelectedTagIds(data.tags.map(t => t.id))
      })
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Ladefehler'))
  }, [id])

  // --- Hilfe: Abo neu laden (nach Preis-, Intervall- oder Status-Änderung) ---
  async function reloadSub() {
    if (!id) return
    const [data, history, billing] = await Promise.all([
      getSubscription(id),
      getPriceHistory(id),
      getBillingHistory(id),
    ])
    setSub(data)
    setPriceHistory(history)
    setBillingHistory(billing)
  }

  // --- Tag an-/abwählen und sofort speichern ---
  async function handleToggleTag(tagId: string) {
    if (!sub) return
    const newIds = selectedTagIds.includes(tagId)
      ? selectedTagIds.filter(id => id !== tagId)
      : [...selectedTagIds, tagId]
    setSelectedTagIds(newIds)
    setTagError(null)
    try {
      await setSubscriptionTags(sub.id, { tag_ids: newIds })
      setSub(prev => prev ? { ...prev, tags: allTags.filter(t => newIds.includes(t.id)) } : prev)
    } catch (err) {
      setSelectedTagIds(selectedTagIds) // Auswahl bei Fehler zurücksetzen
      setTagError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    }
  }

  // Klick außerhalb des Tag-Pickers schließt das Dropdown
  useEffect(() => {
    if (!tagPickerOpen) return
    function handleOutside(e: MouseEvent) {
      if (tagPickerRef.current && !tagPickerRef.current.contains(e.target as Node)) {
        setTagPickerOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [tagPickerOpen])

  // --- Tag-Liste nach Änderungen im TagManagementModal neu laden ---
  async function handleTagsChanged() {
    try {
      const tags = await getTags()
      setAllTags(tags)
      // Ungültige IDs entfernen (z. B. wenn ein Tag gelöscht wurde)
      const validIds = new Set(tags.map(t => t.id))
      setSelectedTagIds(prev => prev.filter(id => validIds.has(id)))
    } catch {
      // Tag-Liste konnte nicht neu geladen werden — kein kritischer Fehler
    }
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

  // --- Preishistorie-Eintrag löschen ---
  function handleDeletePriceEntry(entry: PriceHistoryEntry) {
    if (!sub) return
    setModal({
      title: `Preiseintrag vom ${formatDate(entry.valid_from)} löschen?`,
      body: `Betrag: ${formatAmount(entry.amount)} €. Diese Aktion kann nicht rückgängig gemacht werden.`,
      onConfirm: async () => {
        setModal(null)
        try {
          await deletePriceHistoryEntry(sub.id, entry.id)
          // Preishistorie und Kennzahlen neu laden — sub.amount könnte sich geändert haben
          const [updated, history] = await Promise.all([getSubscription(sub.id), getPriceHistory(sub.id)])
          setSub(updated)
          setPriceHistory(history)
        } catch (err) {
          setInfoModal({
            title: 'Löschen nicht möglich',
            body: err instanceof Error ? err.message : 'Unbekannter Fehler.',
          })
        }
      },
    })
  }

  // --- Abrechnungshistorie-Eintrag löschen (v0.2.4) ---
  function handleDeleteBillingEntry(entry: BillingHistoryEntry) {
    if (!sub) return
    setModal({
      title: `Abrechnungseintrag vom ${formatDate(entry.valid_from)} löschen?`,
      body: `${formatAmount(entry.amount)} € ${INTERVAL_LABELS[entry.interval]}. Diese Aktion kann nicht rückgängig gemacht werden.`,
      onConfirm: async () => {
        setModal(null)
        try {
          await deleteBillingHistoryEntry(sub.id, entry.id)
          // Abo neu laden — sub.amount oder sub.interval könnte sich geändert haben
          const [updated, billing] = await Promise.all([
            getSubscription(sub.id),
            getBillingHistory(sub.id),
          ])
          setSub(updated)
          setBillingHistory(billing)
        } catch (err) {
          setInfoModal({
            title: 'Löschen nicht möglich',
            body: err instanceof Error ? err.message : 'Unbekannter Fehler.',
          })
        }
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

  // --- Preisänderung speichern (nur Betrag, Intervall bleibt gleich) ---
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
      // Preishistorie + Abrechnungshistorie separat neu laden damit die Tabellen aktuell sind
      const [history, billing] = await Promise.all([getPriceHistory(sub.id), getBillingHistory(sub.id)])
      setPriceHistory(history)
      setBillingHistory(billing)
      setPriceForm({ amount: '', valid_from: '' })
      setShowPriceForm(false)
    } catch (err) {
      setPriceError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setPriceLoading(false)
    }
  }

  // --- Intervallwechsel speichern (v0.2.4) ---
  // valid_from = erste Fälligkeit im neuen Intervall — dient auch als neuer Anker.
  // Zwei-Phasen-Flow: bei vorhandenen Buchungen kommt zunächst ein 409-Fehler.
  // Mit angehakter Checkbox wird acknowledge_existing_payments=true mitgeschickt.
  async function handleIntervalChange(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!sub) return
    setIntervalError(null)

    const amountNum = parseAmount(intervalForm.amount)
    if (isNaN(amountNum) || amountNum <= 0) {
      setIntervalError('Bitte einen gültigen Betrag eingeben (z. B. 9,99).')
      return
    }
    if (!intervalForm.valid_from) {
      setIntervalError('Bitte ein Datum angeben.')
      return
    }

    setIntervalLoading(true)
    try {
      const updated = await intervalChange(sub.id, {
        amount: amountNum,
        interval: intervalForm.interval,
        valid_from: intervalForm.valid_from,
        // Nur mitsenden wenn User explizit bestätigt hat — sonst weglassen
        ...(intervalAcknowledge ? { acknowledge_existing_payments: true } : {}),
        ...(intervalAcknowledgeShortSegment ? { acknowledge_short_segment: true } : {}),
      })
      setSub(updated)
      const [history, billing] = await Promise.all([getPriceHistory(sub.id), getBillingHistory(sub.id)])
      setPriceHistory(history)
      setBillingHistory(billing)
      setIntervalForm({ amount: '', interval: 'monthly', valid_from: '' })
      setIntervalAcknowledge(false)
      setIntervalAcknowledgeShortSegment(false)
      setShowIntervalForm(false)
    } catch (err) {
      setIntervalError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setIntervalLoading(false)
    }
  }

  if (loadError) return <p className="detail-load-error">Fehler: {loadError}</p>
  if (!sub) return <p className="detail-loading">Wird geladen…</p>

  // Prüfen ob eine Preisankündigung in der Zukunft liegt
  const today = new Date().toISOString().slice(0, 10)
  const futureBilling = billingHistory
    .filter(entry => entry.valid_from > today)
    .sort((a, b) => a.valid_from.localeCompare(b.valid_from))[0]

  // Aktuell ausgewählte Tag-Objekte (für die Anzeige als Chips)
  const selectedTags = allTags.filter(t => selectedTagIds.includes(t.id))

  // Acknowledge-Checkbox nur anzeigen wenn der Fehler auf vorhandene Buchungen hinweist
  const showAcknowledgeCheckbox = intervalError !== null && intervalError.includes('Buchung')
  const showShortSegmentCheckbox =
    intervalError !== null && intervalError.includes('Kurze Abrechnungsphase')

  return (
    <div className="detail-page">

      {/* Bestätigungs-Modal (Pausieren, Fortsetzen, Kündigen, Einträge löschen) */}
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

      {/* TagManagementModal — CRUD für Tags */}
      {showTagModal && (
        <TagManagementModal
          onClose={() => setShowTagModal(false)}
          onTagsChanged={handleTagsChanged}
        />
      )}

      {/* Preisänderungs-Modal — öffnet sich über Stift-Icon in der Details-Box */}
      {showPriceForm && (
        <div className="confirm-backdrop" onClick={() => {
          setShowPriceForm(false)
          setPriceForm({ amount: '', valid_from: '' })
          setPriceError(null)
        }}>
          <div className="detail-interval-modal" onClick={e => e.stopPropagation()}>
            <h3 className="detail-interval-modal-title">Preis ändern</h3>
            <form onSubmit={handlePriceChange}>
              <div className="detail-interval-modal-fields">
                {/* type="text" damit Komma als Dezimaltrennzeichen akzeptiert wird */}
                <input
                  className="subs-input"
                  placeholder="Neuer Betrag (z. B. 12,99)"
                  value={priceForm.amount}
                  onChange={e => setPriceForm(f => ({ ...f, amount: e.target.value }))}
                  required
                  autoFocus
                />
                <input
                  className="subs-input"
                  type="date"
                  title="Wirkungsdatum (Vergangenheit, heute oder Zukunft)"
                  value={priceForm.valid_from}
                  onChange={e => setPriceForm(f => ({ ...f, valid_from: e.target.value }))}
                  required
                />
              </div>
              {priceError && <p className="detail-notes-error" style={{ marginTop: '8px' }}>{priceError}</p>}
              <div className="detail-notes-actions" style={{ marginTop: '16px' }}>
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
          </div>
        </div>
      )}

      {/* Intervallwechsel-Modal — öffnet sich über Stift-Icon in der Details-Box */}
      {showIntervalForm && (
        <div className="confirm-backdrop" onClick={() => {
          setShowIntervalForm(false)
          setIntervalForm({ amount: '', interval: 'monthly', valid_from: '' })
          setIntervalError(null)
          setIntervalAcknowledge(false)
          setIntervalAcknowledgeShortSegment(false)
        }}>
          <div className="detail-interval-modal" onClick={e => e.stopPropagation()}>
            <h3 className="detail-interval-modal-title">Intervall ändern</h3>
            <form onSubmit={handleIntervalChange}>
              <div className="detail-interval-modal-fields">
                <input
                  className="subs-input"
                  placeholder="Neuer Betrag pro Intervall (z. B. 79,99)"
                  value={intervalForm.amount}
                  onChange={e => setIntervalForm(f => ({ ...f, amount: e.target.value }))}
                  required
                  autoFocus
                />
                <select
                  className="subs-select"
                  value={intervalForm.interval}
                  onChange={e => setIntervalForm(f => ({ ...f, interval: e.target.value as BillingInterval }))}
                >
                  {INTERVALS.map(iv => (
                    <option key={iv} value={iv}>{INTERVAL_LABELS[iv]}</option>
                  ))}
                </select>
                <input
                  className="subs-input"
                  type="date"
                  title="Erste Fälligkeit im neuen Intervall (wird auch neuer Anker)"
                  value={intervalForm.valid_from}
                  onChange={e => setIntervalForm(f => ({ ...f, valid_from: e.target.value }))}
                  required
                />
              </div>
              <p className="detail-notes-muted" style={{ marginTop: '8px' }}>
                {(() => {
                  const amount = parseAmountInput(intervalForm.amount)
                  if (amount === null) return 'Hinweis: Der Betrag gilt immer pro gewähltem Intervall (z. B. bei „Vierteljährlich" pro Quartal).'
                  const months = MONTHS_PER_PERIOD[intervalForm.interval]
                  const yearly = (amount * 12) / months
                  const label = INTERVAL_LABELS[intervalForm.interval]
                  return `Hinweis: Der Betrag ist pro „${label}". Das entspricht ca. ${yearly.toFixed(2).replace('.', ',')} € pro Jahr.`
                })()}
              </p>
              {intervalError && (
                <>
                  <p className="detail-notes-error">{intervalError}</p>
                  {/* Acknowledge-Checkbox erscheint wenn der Server meldet dass Buchungen betroffen sind */}
                  {showAcknowledgeCheckbox && (
                    <label style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', margin: '8px 0', fontSize: '0.875rem' }}>
                      <input
                        type="checkbox"
                        checked={intervalAcknowledge}
                        onChange={e => setIntervalAcknowledge(e.target.checked)}
                      />
                      Ich bestätige, dass die vorhandenen Buchungen angepasst werden sollen.
                    </label>
                  )}
                  {showShortSegmentCheckbox && (
                    <label style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', margin: '8px 0', fontSize: '0.875rem' }}>
                      <input
                        type="checkbox"
                        checked={intervalAcknowledgeShortSegment}
                        onChange={e => setIntervalAcknowledgeShortSegment(e.target.checked)}
                      />
                      Ich bestätige trotzdem: Die Abrechnungsphase ist kürzer als eine volle Periode (Absicht oder Korrektur später).
                    </label>
                  )}
                </>
              )}
              <div className="detail-notes-actions" style={{ marginTop: '16px' }}>
                <button type="submit" className="btn-primary-sm" disabled={intervalLoading}>
                  {intervalLoading ? '…' : 'Speichern'}
                </button>
                <button
                  type="button"
                  className="btn-outline-sm"
                  onClick={() => {
                    setShowIntervalForm(false)
                    setIntervalForm({ amount: '', interval: 'monthly', valid_from: '' })
                    setIntervalError(null)
                    setIntervalAcknowledge(false)
                    setIntervalAcknowledgeShortSegment(false)
                  }}
                >
                  Abbrechen
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Info/Fehler-Modal — API-Fehlermeldungen als Overlay */}
      {infoModal && (
        <InfoModal
          title={infoModal.title}
          body={infoModal.body}
          onClose={() => setInfoModal(null)}
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
          <dd>
            {INTERVAL_LABELS[sub.interval]}
            <button
              className="detail-inline-edit-btn"
              onClick={() => {
                setIntervalForm(f => ({ ...f, interval: sub.interval }))
                setShowIntervalForm(true)
              }}
              title="Intervall ändern"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="m18.5 2.5 2 2L11 14l-4 1 1-4z"/>
              </svg>
            </button>
          </dd>

          <dt>Aktueller Betrag</dt>
          <dd>
            {formatAmount(sub.amount)} €
            <button
              className="detail-inline-edit-btn"
              onClick={() => setShowPriceForm(true)}
              title="Preis ändern"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="m18.5 2.5 2 2L11 14l-4 1 1-4z"/>
              </svg>
            </button>
          </dd>

          {futureBilling && (
            <>
              <dt>Geplante Änderung</dt>
              <dd>
                <span className="detail-price-announcement">
                  Ab {formatDate(futureBilling.valid_from)}: {formatAmount(futureBilling.amount)} €, {INTERVAL_LABELS[futureBilling.interval]}
                </span>
              </dd>
            </>
          )}

          <dt>Abgeschlossen am</dt>
          <dd>{formatDate(sub.started_on)}</dd>

          <dt>Nächste Fälligkeit</dt>
          {/* next_due_date kann null sein wenn started_on in der Zukunft liegt */}
          <dd>{sub.next_due_date ? formatDate(sub.next_due_date) : '—'}</dd>

          <dt>Tags</dt>
          <dd>
            <div className="detail-tags-inline" ref={tagPickerRef}>
              {selectedTags.map(tag => (
                <TagBadge
                  key={tag.id}
                  tag={tag}
                  onRemove={() => handleToggleTag(tag.id)}
                />
              ))}
              <button
                type="button"
                className="detail-tags-add-btn"
                onClick={() => setTagPickerOpen(v => !v)}
              >
                + Hinzufügen
              </button>
              {tagPickerOpen && (
                <div className="detail-tags-picker">
                  {allTags.filter(t => !selectedTagIds.includes(t.id)).length === 0 ? (
                    <p className="detail-tags-picker-empty">Alle Tags bereits zugewiesen.</p>
                  ) : (
                    allTags
                      .filter(t => !selectedTagIds.includes(t.id))
                      .map(tag => (
                        <button
                          key={tag.id}
                          type="button"
                          className="detail-tags-picker-option"
                          onClick={() => { handleToggleTag(tag.id); setTagPickerOpen(false) }}
                        >
                          <span className="detail-tags-picker-dot" style={{ background: tag.color }} />
                          {tag.name}
                        </button>
                      ))
                  )}
                  <button
                    type="button"
                    className="detail-tags-picker-manage"
                    onClick={() => { setTagPickerOpen(false); setShowTagModal(true) }}
                  >
                    Tags verwalten...
                  </button>
                </div>
              )}
            </div>
            {tagError && <p className="detail-notes-error" style={{ marginTop: '6px' }}>{tagError}</p>}
          </dd>
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
                <th></th>
              </tr>
            </thead>
            <tbody>
              {priceHistory.map((entry, i) => (
                <tr key={entry.id} className={i === 0 ? 'detail-ph-current' : ''}>
                  <td>{formatDate(entry.valid_from)}</td>
                  <td>{formatAmount(entry.amount)} €</td>
                  <td className="detail-ph-actions">
                    <button
                      className="ph-delete-btn"
                      title={
                        priceHistory.length <= 1
                          ? 'Letzter Eintrag — kann nicht gelöscht werden'
                          : 'Eintrag löschen'
                      }
                      disabled={priceHistory.length <= 1}
                      onClick={() => handleDeletePriceEntry(entry)}
                    >
                      {/* Papierkorb-Icon (Feather-Style) */}
                      <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14H6L5 6" />
                        <path d="M10 11v6" />
                        <path d="M14 11v6" />
                        <path d="M9 6V4h6v2" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Abrechnungshistorie — Betrag + Intervall + Anker pro Zeitraum (v0.2.4).
          Wird nur angezeigt wenn mindestens ein Eintrag vorhanden ist. */}
      {billingHistory.length > 0 && (
        <div className="detail-card">
          <h2 className="detail-section-title">Abrechnungshistorie</h2>
          <table className="detail-ph-table">
            <thead>
              <tr>
                <th>Gültig ab</th>
                <th>Betrag</th>
                <th>Intervall</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {billingHistory.map((entry, i) => (
                <tr key={entry.id} className={i === 0 ? 'detail-ph-current' : ''}>
                  <td>{formatDate(entry.valid_from)}</td>
                  <td>{formatAmount(entry.amount)} €</td>
                  <td>{INTERVAL_LABELS[entry.interval]}</td>
                  <td className="detail-ph-actions">
                    <button
                      className="ph-delete-btn"
                      title={
                        billingHistory.length <= 1
                          ? 'Letzter Eintrag — kann nicht gelöscht werden'
                          : 'Eintrag löschen'
                      }
                      disabled={billingHistory.length <= 1}
                      onClick={() => handleDeleteBillingEntry(entry)}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14H6L5 6" />
                        <path d="M10 11v6" />
                        <path d="M14 11v6" />
                        <path d="M9 6V4h6v2" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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

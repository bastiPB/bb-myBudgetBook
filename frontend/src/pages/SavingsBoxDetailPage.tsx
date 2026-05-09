// SavingsBoxDetailPage.tsx — Detailansicht eines Sparfachs (v0.2.6).
//
// Tabs:
//  - Übersicht: Progress + Termine (offen/verpasst/erledigt) + Einzahlung-Modal
//  - Buchungen: Tabelle + Bearbeiten/Löschen
//  - Einstellungen: Stammdaten bearbeiten + Close/Reopen Flow
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import ConfirmModal from '../components/ConfirmModal'
import InfoModal from '../components/InfoModal'
import {
  closeBox,
  createBooking,
  deleteBooking,
  getBoxDetail,
  reopenBox,
  updateBooking,
  updateBox,
} from '../api/savingsBox'
import type {
  SavingsBookingRead,
  SavingsBookingType,
  SavingsBoxDetail,
  SavingsBoxUpdate,
  SavingsTermRead,
} from '../types/savingsBox'
import {
  SAVINGS_BOOKING_TYPE_LABELS,
  SAVINGS_BOX_STATUS_LABELS,
  SAVINGS_TERM_STATUS_LABELS,
} from '../types/savingsBox'
import { formatAmount, formatDate, parseAmount } from '../types/subscription'
// Button-Klassen (btn-outline-sm, btn-primary-sm, btn-danger) kommen aus SubscriptionsPage.css
import './SubscriptionsPage.css'
import './SavingsBoxDetailPage.css'

type TabKey = 'overview' | 'bookings' | 'settings'

type ConfirmState = {
  title: string
  body?: string
  dangerous?: boolean
  confirmText?: string
  onConfirm: () => void
}

function todayISO(): string {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

function bookingTypeOrder(t: SavingsBookingType): number {
  if (t === 'deposit') return 1
  if (t === 'penalty') return 2
  return 3
}

function moneyLabel(amount: string): string {
  return `€${formatAmount(amount)}`
}

function ProgressCard({ detail }: { detail: SavingsBoxDetail }) {
  const s = detail.summary
  const hasTarget = s.target_amount != null && parseFloat(s.target_amount) > 0
  const pct = s.progress_pct ? Math.max(0, Math.min(100, parseFloat(s.progress_pct))) : 0

  return (
    <div className="sb-detail-card">
      <h2 className="sb-detail-section-title">Übersicht</h2>

      {!hasTarget ? (
        <p className="sb-detail-summary-line">
          {moneyLabel(s.total_deposited)} eingezahlt, {moneyLabel(s.total_penalties)} Strafen,{' '}
          <strong>{moneyLabel(s.net_amount)} netto</strong>
        </p>
      ) : (
        <div className="sb-detail-progress">
          <div className="sb-detail-progress-track" aria-hidden>
            <div className="sb-detail-progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="sb-detail-progress-meta">
            <span>
              <strong>{moneyLabel(s.net_amount)}</strong> / {moneyLabel(s.target_amount!)}
            </span>
            <span className="sb-detail-progress-pct">{Number.isFinite(pct) ? pct.toFixed(0) : '0'}%</span>
          </div>
        </div>
      )}

      {s.personal_amount_per_term != null && (
        <p className="sb-detail-hint">
          Persönliches Termziel: <strong>{moneyLabel(s.personal_amount_per_term)}</strong>
        </p>
      )}
    </div>
  )
}

function TermRow({
  term,
  isClosed,
  depositSum,
  penaltyAmountForTerm,
  onDeposit,
}: {
  term: SavingsTermRead
  isClosed: boolean
  depositSum: string
  penaltyAmountForTerm: string | null
  onDeposit: () => void
}) {
  return (
    <div className="sb-term-row">
      <div className="sb-term-left">
        <div className="sb-term-date">{formatDate(term.due_date)}</div>
        <div className="sb-term-sub">
          <span className={`sb-term-pill sb-term-${term.status}`}>
            {SAVINGS_TERM_STATUS_LABELS[term.status]}
          </span>
          <span className="sb-term-muted">Mindestbetrag {moneyLabel(term.expected_amount)}</span>
          {term.status === 'fulfilled' && depositSum !== '0' && (
            <span className="sb-term-muted">gezahlt {moneyLabel(depositSum)}</span>
          )}
          {term.status === 'missed' && penaltyAmountForTerm && (
            <span className="sb-term-muted">Strafe {moneyLabel(penaltyAmountForTerm)}</span>
          )}
        </div>
      </div>

      <div className="sb-term-actions">
        <button className="btn-primary-sm" onClick={onDeposit} disabled={isClosed}>
          Einzahlen
        </button>
      </div>
    </div>
  )
}

function SavingsBoxDetailInner({ id }: { id: string }) {
  const [tab, setTab] = useState<TabKey>('overview')
  const [detail, setDetail] = useState<SavingsBoxDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  /** „Erledigt“-Accordion: beim Wechsel des Sparfachs durch neuen Mount zurückgesetzt (siehe key am Wrapper). */
  const [showFulfilled, setShowFulfilled] = useState(false)

  // Allgemeine „Toast“-Ersatzmeldung pro Seite
  const [actionError, setActionError] = useState<string | null>(null)

  // Confirm / Info Modals
  const [confirm, setConfirm] = useState<ConfirmState | null>(null)
  const [info, setInfo] = useState<{ title: string; body: string } | null>(null)

  // Einzahlung-Modal
  const [depositTerm, setDepositTerm] = useState<SavingsTermRead | null>(null)
  const [depositForm, setDepositForm] = useState({ amount: '', booking_date: todayISO(), note: '' })
  const [depositError, setDepositError] = useState<string | null>(null)
  const [depositLoading, setDepositLoading] = useState(false)

  // Buchung bearbeiten
  const [editBooking, setEditBooking] = useState<SavingsBookingRead | null>(null)
  const [editForm, setEditForm] = useState({ amount: '', booking_date: todayISO(), note: '' })
  const [editError, setEditError] = useState<string | null>(null)
  const [editLoading, setEditLoading] = useState(false)

  // Close Flow
  const [closeOpen, setCloseOpen] = useState(false)
  const [closeForm, setCloseForm] = useState({ actual_amount: '', note: '' })
  const [closeError, setCloseError] = useState<string | null>(null)
  const [closeLoading, setCloseLoading] = useState(false)

  // Settings Form
  const [settingsForm, setSettingsForm] = useState({
    name: '',
    location: '',
    target_amount: '',
    personal_amount_per_term: '',
  })
  const [settingsDirty, setSettingsDirty] = useState(false)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [settingsLoading, setSettingsLoading] = useState(false)

  const reload = useCallback(async () => {
    setLoadError(null)
    try {
      const d = await getBoxDetail(id)
      setDetail(d)
      setSettingsForm({
        name: d.name ?? '',
        location: d.location ?? '',
        target_amount: d.summary.target_amount ?? '',
        personal_amount_per_term: d.summary.personal_amount_per_term ?? '',
      })
      setSettingsDirty(false)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Laden fehlgeschlagen.')
    }
  }, [id])

  useEffect(() => {
    let cancelled = false
    const timerId = window.setTimeout(() => {
      if (!cancelled) void reload()
    }, 0)
    return () => {
      cancelled = true
      window.clearTimeout(timerId)
    }
  }, [reload])

  const isClosed = detail?.status === 'closed'

  const depositsByTerm = useMemo(() => {
    const map = new Map<string, number>()
    if (!detail) return map
    for (const b of detail.bookings) {
      if (b.booking_type !== 'deposit') continue
      if (!b.savings_term_id) continue
      const prev = map.get(b.savings_term_id) ?? 0
      map.set(b.savings_term_id, prev + (parseFloat(b.amount) || 0))
    }
    return map
  }, [detail])

  const penaltiesByTerm = useMemo(() => {
    const map = new Map<string, number>()
    if (!detail) return map
    for (const b of detail.bookings) {
      if (b.booking_type !== 'penalty') continue
      if (!b.savings_term_id) continue
      const prev = map.get(b.savings_term_id) ?? 0
      map.set(b.savings_term_id, prev + (parseFloat(b.amount) || 0))
    }
    return map
  }, [detail])

  const groupedTerms = useMemo(() => {
    const open: SavingsTermRead[] = []
    const missed: SavingsTermRead[] = []
    const fulfilled: SavingsTermRead[] = []
    if (!detail) return { open, missed, fulfilled }
    for (const t of detail.terms) {
      if (t.status === 'open') open.push(t)
      else if (t.status === 'missed') missed.push(t)
      else fulfilled.push(t)
    }
    return { open, missed, fulfilled }
  }, [detail])

  function openDepositModal(term: SavingsTermRead) {
    setDepositTerm(term)
    setDepositForm({ amount: '', booking_date: todayISO(), note: '' })
    setDepositError(null)
  }

  async function submitDeposit() {
    if (!detail || !id || !depositTerm) return
    setDepositError(null)
    setActionError(null)

    const n = parseAmount(depositForm.amount.trim())
    if (!Number.isFinite(n) || n <= 0) {
      setDepositError('Bitte einen gültigen Betrag größer 0 eingeben (z. B. 25,00).')
      return
    }
    const minExpected = parseFloat(depositTerm.expected_amount) || 0
    if (n < minExpected) {
      setDepositError(`Betrag muss mindestens ${moneyLabel(depositTerm.expected_amount)} betragen.`)
      return
    }

    setDepositLoading(true)
    try {
      await createBooking(id, {
        booking_type: 'deposit',
        savings_term_id: depositTerm.id,
        amount: n,
        booking_date: depositForm.booking_date || todayISO(),
        note: depositForm.note.trim() || null,
      })
      setDepositTerm(null)
      await reload()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Fehler beim Speichern.'
      setDepositError(msg)
    } finally {
      setDepositLoading(false)
    }
  }

  function startEditBooking(b: SavingsBookingRead) {
    setEditBooking(b)
    setEditForm({
      amount: formatAmount(b.amount), // in deutsches Format (als UI-Startwert)
      booking_date: b.booking_date,
      note: b.note ?? '',
    })
    setEditError(null)
  }

  async function submitEditBooking() {
    if (!detail || !id || !editBooking) return
    setEditError(null)
    setActionError(null)

    const n = parseAmount(editForm.amount.trim())
    if (!Number.isFinite(n) || n <= 0) {
      setEditError('Bitte einen gültigen Betrag größer 0 eingeben.')
      return
    }

    setEditLoading(true)
    try {
      await updateBooking(id, editBooking.id, {
        amount: n,
        booking_date: editForm.booking_date || editBooking.booking_date,
        note: editForm.note.trim() || null,
      })
      setEditBooking(null)
      await reload()
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setEditLoading(false)
    }
  }

  function askDeleteBooking(b: SavingsBookingRead) {
    if (!id) return
    setConfirm({
      title: 'Buchung löschen?',
      body: 'Diese Aktion kann nicht rückgängig gemacht werden.',
      dangerous: true,
      onConfirm: () => {
        setConfirm(null)
        deleteBooking(id, b.id)
          .then(() => reload())
          .catch(err => {
            const msg = err instanceof Error ? err.message : 'Fehler beim Löschen.'
            // „Toast“: einfache Banner-Meldung
            setActionError(msg)
          })
      },
    })
  }

  async function saveSettings() {
    if (!detail || !id) return
    setSettingsError(null)
    setActionError(null)

    const payload: SavingsBoxUpdate = {}
    if (settingsForm.name.trim() !== detail.name) payload.name = settingsForm.name.trim()
    if ((settingsForm.location.trim() || null) !== (detail.location ?? null)) {
      payload.location = settingsForm.location.trim() || null
    }

    // target / personal sind in der Summary, aber editierbar laut Plan
    const targetRaw = settingsForm.target_amount.trim()
    const personalRaw = settingsForm.personal_amount_per_term.trim()

    if ((targetRaw || null) !== (detail.summary.target_amount ?? null)) {
      if (!targetRaw) payload.target_amount = null
      else {
        const n = parseAmount(targetRaw)
        if (!Number.isFinite(n) || n < 0) {
          setSettingsError('Gesamtziel: ungültiger Betrag.')
          return
        }
        payload.target_amount = n
      }
    }

    if ((personalRaw || null) !== (detail.summary.personal_amount_per_term ?? null)) {
      if (!personalRaw) payload.personal_amount_per_term = null
      else {
        const n = parseAmount(personalRaw)
        if (!Number.isFinite(n) || n < 0) {
          setSettingsError('Persönliches Termziel: ungültiger Betrag.')
          return
        }
        payload.personal_amount_per_term = n
      }
    }

    if (Object.keys(payload).length === 0) {
      setSettingsDirty(false)
      return
    }

    setSettingsLoading(true)
    try {
      await updateBox(id, payload)
      await reload()
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setSettingsLoading(false)
    }
  }

  function askClose() {
    if (!detail) return
    setConfirm({
      title: 'Sparfach abschließen?',
      body: 'Nach dem Abschluss sind keine Änderungen an Terminen und Buchungen mehr möglich.',
      dangerous: true,
      onConfirm: () => {
        setConfirm(null)
        setCloseOpen(true)
        setCloseForm({ actual_amount: '', note: '' })
        setCloseError(null)
      },
    })
  }

  async function submitClose() {
    if (!detail || !id) return
    setCloseError(null)
    setActionError(null)

    const n = parseAmount(closeForm.actual_amount.trim())
    if (!Number.isFinite(n) || n < 0) {
      setCloseError('Bitte einen gültigen Auszahlungsbetrag eingeben.')
      return
    }

    setCloseLoading(true)
    try {
      await closeBox(id, { actual_amount: n, note: closeForm.note.trim() || null })
      setCloseOpen(false)
      await reload()
      setTab('overview')
    } catch (err) {
      setCloseError(err instanceof Error ? err.message : 'Fehler beim Abschließen.')
    } finally {
      setCloseLoading(false)
    }
  }

  function askReopen() {
    if (!detail || !id) return
    setConfirm({
      title: 'Sparfach wieder öffnen?',
      body: 'Dein Abschlussbericht wird gelöscht.',
      dangerous: true,
      onConfirm: () => {
        setConfirm(null)
        reopenBox(id)
          .then(() => reload())
          .catch(err => {
            const msg = err instanceof Error ? err.message : 'Fehler beim Öffnen.'
            setInfo({ title: 'Fehler', body: msg })
          })
      },
    })
  }

  if (loadError) {
    return (
      <div className="sb-detail-page">
        <p style={{ marginBottom: 16 }}>
          <Link to="/savings-box" style={{ color: 'var(--color-accent)' }}>
            ← Zurück zur Übersicht
          </Link>
        </p>
        <p>Fehler: {loadError}</p>
      </div>
    )
  }

  if (!detail) {
    return <p>Laden…</p>
  }

  return (
    <div className="sb-detail-page">
      {confirm && (
        <ConfirmModal
          title={confirm.title}
          body={confirm.body}
          dangerous={confirm.dangerous}
          confirmText={confirm.confirmText}
          onConfirm={confirm.onConfirm}
          onCancel={() => setConfirm(null)}
        />
      )}
      {info && <InfoModal title={info.title} body={info.body} onClose={() => setInfo(null)} />}

      {/* Einzahlung Modal */}
      {depositTerm && (
        <div className="sb-modal-backdrop" onClick={() => setDepositTerm(null)}>
          <div className="sb-modal" role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}>
            <h2 className="sb-modal-title">Einzahlen</h2>
            <p className="sb-modal-body">
              Termin: <strong>{formatDate(depositTerm.due_date)}</strong> · Mindestbetrag{' '}
              <strong>{moneyLabel(depositTerm.expected_amount)}</strong>
            </p>
            {depositTerm.status === 'missed' && penaltiesByTerm.get(depositTerm.id) && (
              <p className="sb-modal-body sb-modal-warn">
                Für diesen Termin wurde eine Strafgebühr erfasst.
              </p>
            )}
            {depositError && <p className="subs-form-error">{depositError}</p>}
            <div className="sb-modal-grid">
              <label className="sb-modal-label">
                Betrag (€)
                <input
                  className="sb-modal-input"
                  placeholder="z. B. 25,00"
                  value={depositForm.amount}
                  onChange={e => setDepositForm(f => ({ ...f, amount: e.target.value }))}
                  autoFocus
                />
              </label>
              <label className="sb-modal-label">
                Datum
                <input
                  className="sb-modal-input"
                  type="date"
                  value={depositForm.booking_date}
                  onChange={e => setDepositForm(f => ({ ...f, booking_date: e.target.value }))}
                />
              </label>
              <label className="sb-modal-label sb-modal-span">
                Notiz (optional)
                <input
                  className="sb-modal-input"
                  value={depositForm.note}
                  onChange={e => setDepositForm(f => ({ ...f, note: e.target.value }))}
                />
              </label>
            </div>
            <div className="sb-modal-actions">
              <button className="btn-primary-sm" onClick={submitDeposit} disabled={depositLoading || isClosed}>
                {depositLoading ? '…' : 'Speichern'}
              </button>
              <button className="btn-outline-sm" onClick={() => setDepositTerm(null)}>
                Abbrechen
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Buchung bearbeiten Modal */}
      {editBooking && (
        <div className="sb-modal-backdrop" onClick={() => setEditBooking(null)}>
          <div className="sb-modal" role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}>
            <h2 className="sb-modal-title">Buchung bearbeiten</h2>
            <p className="sb-modal-body">
              Typ: <strong>{SAVINGS_BOOKING_TYPE_LABELS[editBooking.booking_type]}</strong>
            </p>
            {editError && <p className="subs-form-error">{editError}</p>}
            <div className="sb-modal-grid">
              <label className="sb-modal-label">
                Betrag (€)
                <input
                  className="sb-modal-input"
                  value={editForm.amount}
                  onChange={e => setEditForm(f => ({ ...f, amount: e.target.value }))}
                  autoFocus
                />
              </label>
              <label className="sb-modal-label">
                Datum
                <input
                  className="sb-modal-input"
                  type="date"
                  value={editForm.booking_date}
                  onChange={e => setEditForm(f => ({ ...f, booking_date: e.target.value }))}
                />
              </label>
              <label className="sb-modal-label sb-modal-span">
                Notiz (optional)
                <input
                  className="sb-modal-input"
                  value={editForm.note}
                  onChange={e => setEditForm(f => ({ ...f, note: e.target.value }))}
                />
              </label>
            </div>
            <div className="sb-modal-actions">
              <button className="btn-primary-sm" onClick={submitEditBooking} disabled={editLoading || isClosed}>
                {editLoading ? '…' : 'Speichern'}
              </button>
              <button className="btn-outline-sm" onClick={() => setEditBooking(null)}>
                Abbrechen
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Close Modal (Schritt 2) */}
      {closeOpen && (
        <div className="sb-modal-backdrop" onClick={() => setCloseOpen(false)}>
          <div className="sb-modal" role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}>
            <h2 className="sb-modal-title">Sparfach abschließen</h2>
            <p className="sb-modal-body">
              Bitte den tatsächlichen Auszahlungsbetrag eintragen (Ist) und optional eine Notiz.
            </p>
            {closeError && <p className="subs-form-error">{closeError}</p>}
            <div className="sb-modal-grid">
              <label className="sb-modal-label">
                Auszahlungsbetrag (€)
                <input
                  className="sb-modal-input"
                  placeholder="z. B. 375,00"
                  value={closeForm.actual_amount}
                  onChange={e => setCloseForm(f => ({ ...f, actual_amount: e.target.value }))}
                  autoFocus
                />
              </label>
              <label className="sb-modal-label sb-modal-span">
                Notiz (optional)
                <input
                  className="sb-modal-input"
                  value={closeForm.note}
                  onChange={e => setCloseForm(f => ({ ...f, note: e.target.value }))}
                />
              </label>
            </div>
            <div className="sb-modal-actions">
              <button className="btn-primary-sm" onClick={submitClose} disabled={closeLoading || isClosed}>
                {closeLoading ? '…' : 'Abschließen'}
              </button>
              <button className="btn-outline-sm" onClick={() => setCloseOpen(false)}>
                Abbrechen
              </button>
            </div>
          </div>
        </div>
      )}

      <p className="sb-detail-back">
        <Link to="/savings-box">← Zurück zur Übersicht</Link>
      </p>

      <div className="sb-detail-header">
        <h1 className="page-title sb-detail-title">{detail.name}</h1>
        <span className={`sb-detail-status sb-detail-status-${detail.status}`}>
          {SAVINGS_BOX_STATUS_LABELS[detail.status]}
        </span>
      </div>

      {actionError && <p className="subs-form-error">{actionError}</p>}

      <div className="sb-tabs">
        <button
          type="button"
          className={`sb-tab${tab === 'overview' ? ' is-active' : ''}`}
          onClick={() => setTab('overview')}
        >
          Übersicht
        </button>
        <button
          type="button"
          className={`sb-tab${tab === 'bookings' ? ' is-active' : ''}`}
          onClick={() => setTab('bookings')}
        >
          Buchungen
        </button>
        <button
          type="button"
          className={`sb-tab${tab === 'settings' ? ' is-active' : ''}`}
          onClick={() => setTab('settings')}
        >
          Einstellungen
        </button>
      </div>

      {tab === 'overview' && (
        <>
          <ProgressCard detail={detail} />

          <div className="sb-detail-card">
            <h2 className="sb-detail-section-title">Termine</h2>

            <button
              type="button"
              className="sb-accordion-head"
              aria-disabled
            >
              Offen ({groupedTerms.open.length})
            </button>
            <div className="sb-accordion-body">
              {groupedTerms.open.length === 0 ? (
                <p className="sb-detail-empty">Keine offenen Termine.</p>
              ) : (
                groupedTerms.open.map(t => (
                  <TermRow
                    key={t.id}
                    term={t}
                    isClosed={!!isClosed}
                    depositSum={String(depositsByTerm.get(t.id) ?? 0)}
                    penaltyAmountForTerm={penaltiesByTerm.get(t.id) ? String(penaltiesByTerm.get(t.id)) : null}
                    onDeposit={() => openDepositModal(t)}
                  />
                ))
              )}
            </div>

            <button type="button" className="sb-accordion-head" aria-disabled>
              Verpasst ({groupedTerms.missed.length})
            </button>
            <div className="sb-accordion-body">
              {groupedTerms.missed.length === 0 ? (
                <p className="sb-detail-empty">Keine verpassten Termine.</p>
              ) : (
                groupedTerms.missed.map(t => (
                  <TermRow
                    key={t.id}
                    term={t}
                    isClosed={!!isClosed}
                    depositSum={String(depositsByTerm.get(t.id) ?? 0)}
                    penaltyAmountForTerm={penaltiesByTerm.get(t.id) ? String(penaltiesByTerm.get(t.id)) : null}
                    onDeposit={() => openDepositModal(t)}
                  />
                ))
              )}
            </div>

            <button
              type="button"
              className={`sb-accordion-head${showFulfilled ? ' is-open' : ''}`}
              onClick={() => setShowFulfilled(v => !v)}
            >
              Erledigt ({groupedTerms.fulfilled.length}) <span className="sb-accordion-caret">▾</span>
            </button>
            {showFulfilled && (
              <div className="sb-accordion-body">
                {groupedTerms.fulfilled.length === 0 ? (
                  <p className="sb-detail-empty">Keine erledigten Termine.</p>
                ) : (
                  groupedTerms.fulfilled.map(t => (
                    <TermRow
                      key={t.id}
                      term={t}
                      isClosed={!!isClosed}
                      depositSum={String(depositsByTerm.get(t.id) ?? 0)}
                      penaltyAmountForTerm={penaltiesByTerm.get(t.id) ? String(penaltiesByTerm.get(t.id)) : null}
                      onDeposit={() => openDepositModal(t)}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        </>
      )}

      {tab === 'bookings' && (
        <div className="sb-detail-card">
          <h2 className="sb-detail-section-title">Buchungen</h2>

          <div className="sb-bookings-table-card">
            <table className="sb-bookings-table">
              <thead>
                <tr>
                  <th>Datum</th>
                  <th>Typ</th>
                  <th>Betrag</th>
                  <th>Termin</th>
                  <th>Notiz</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {detail.bookings.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="sb-bookings-empty">
                      Noch keine Buchungen.
                    </td>
                  </tr>
                ) : (
                  [...detail.bookings]
                    .sort((a, b) => {
                      if (a.booking_date !== b.booking_date) return a.booking_date < b.booking_date ? 1 : -1
                      const typeCmp = bookingTypeOrder(a.booking_type) - bookingTypeOrder(b.booking_type)
                      if (typeCmp !== 0) return typeCmp
                      return a.id < b.id ? 1 : -1
                    })
                    .map(b => (
                      <tr key={b.id}>
                        <td>{formatDate(b.booking_date)}</td>
                        <td>{SAVINGS_BOOKING_TYPE_LABELS[b.booking_type]}</td>
                        <td>{moneyLabel(b.amount)}</td>
                        <td className="sb-bookings-term">
                          {b.savings_term_id
                            ? formatDate(detail.terms.find(t => t.id === b.savings_term_id)?.due_date ?? '—')
                            : '—'}
                        </td>
                        <td className="sb-bookings-note">{b.note ?? ''}</td>
                        <td>
                          <div className="subs-action-cell">
                            <button
                              className="btn-outline-sm"
                              onClick={() => startEditBooking(b)}
                              disabled={!!isClosed}
                            >
                              Bearbeiten
                            </button>
                            <button className="btn-danger" onClick={() => askDeleteBooking(b)} disabled={!!isClosed}>
                              Löschen
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'settings' && (
        <>
          <div className="sb-detail-card">
            <h2 className="sb-detail-section-title">Stammdaten</h2>

            {settingsError && <p className="subs-form-error">{settingsError}</p>}

            <div className="sb-settings-grid">
              <label className="sb-settings-label">
                Name
                <input
                  className="sb-settings-input"
                  value={settingsForm.name}
                  onChange={e => {
                    setSettingsForm(f => ({ ...f, name: e.target.value }))
                    setSettingsDirty(true)
                  }}
                  disabled={!!isClosed}
                />
              </label>
              <label className="sb-settings-label">
                Ort
                <input
                  className="sb-settings-input"
                  value={settingsForm.location}
                  onChange={e => {
                    setSettingsForm(f => ({ ...f, location: e.target.value }))
                    setSettingsDirty(true)
                  }}
                  disabled={!!isClosed}
                />
              </label>
              <label className="sb-settings-label">
                Gesamtziel (€)
                <input
                  className="sb-settings-input"
                  placeholder="leer = kein Ziel"
                  value={settingsForm.target_amount}
                  onChange={e => {
                    setSettingsForm(f => ({ ...f, target_amount: e.target.value }))
                    setSettingsDirty(true)
                  }}
                  disabled={!!isClosed}
                />
              </label>
              <label className="sb-settings-label">
                Persönliches Termziel (€)
                <input
                  className="sb-settings-input"
                  placeholder="leer = kein Termziel"
                  value={settingsForm.personal_amount_per_term}
                  onChange={e => {
                    setSettingsForm(f => ({ ...f, personal_amount_per_term: e.target.value }))
                    setSettingsDirty(true)
                  }}
                  disabled={!!isClosed}
                />
              </label>
            </div>

            <div className="sb-settings-actions">
              <button className="btn-primary-sm" onClick={saveSettings} disabled={!settingsDirty || settingsLoading || !!isClosed}>
                {settingsLoading ? '…' : 'Speichern'}
              </button>
              <button className="btn-outline-sm" onClick={() => reload()} disabled={settingsLoading}>
                Zurücksetzen
              </button>
            </div>
          </div>

          <div className="sb-detail-card">
            <h2 className="sb-detail-section-title">Abschluss</h2>

            {detail.status !== 'closed' ? (
              <button className="btn-danger" onClick={askClose} disabled={!!isClosed}>
                Sparfach abschließen
              </button>
            ) : (
              <>
                <p className="sb-detail-hint">
                  Abgeschlossen am{' '}
                  <strong>{detail.closed_at ? new Date(detail.closed_at).toLocaleString('de-DE') : '—'}</strong>
                </p>
                <button className="btn-outline-sm" onClick={askReopen}>
                  Sparfach wieder öffnen
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default function SavingsBoxDetailPage() {
  const { id } = useParams<{ id: string }>()
  if (!id) {
    return (
      <div className="sb-detail-page">
        <p style={{ marginBottom: 16 }}>
          <Link to="/savings-box" style={{ color: 'var(--color-accent)' }}>
            ← Zurück zur Übersicht
          </Link>
        </p>
        <p>Keine Sparfach-ID in der Adresse.</p>
      </div>
    )
  }
  return <SavingsBoxDetailInner key={id} id={id} />
}

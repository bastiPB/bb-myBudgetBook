// Sparfach-Dashboard: Kacheln + Formular zum Anlegen.
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { createBox, listBoxes } from '../api/savingsBox'
import type {
  SavingsBoxCreate,
  SavingsBoxRead,
  SavingsBoxStatus,
  SavingsInterval,
} from '../types/savingsBox'
import {
  SAVINGS_BOX_STATUS_LABELS,
  SAVINGS_INTERVAL_LABELS,
} from '../types/savingsBox'
import { formatAmount, formatDate, parseAmount } from '../types/subscription'
import './SavingsBoxPage.css'

const INTERVALS: SavingsInterval[] = ['weekly', 'biweekly', 'monthly']

const EMPTY_CREATE = {
  name: '',
  location: '',
  box_number: '',
  start_date: '',
  end_date: '',
  interval: 'monthly' as SavingsInterval,
  min_amount: '',
  penalty_amount: '',
  target_amount: '',
  personal_amount: '',
}

function StatusBadge({ status }: { status: SavingsBoxStatus }) {
  return (
    <span className={`sb-status-badge sb-status-${status}`}>
      {SAVINGS_BOX_STATUS_LABELS[status]}
    </span>
  )
}

function progressBarWidthPct(summary: SavingsBoxRead['summary']): number {
  const p = summary.progress_pct
  if (p == null) return 0
  const n = parseFloat(p)
  if (Number.isNaN(n)) return 0
  return Math.min(100, Math.max(0, n))
}

export default function SavingsBoxPage() {
  const navigate = useNavigate()
  const [boxes, setBoxes] = useState<SavingsBoxRead[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_CREATE)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  useEffect(() => {
    listBoxes()
      .then(setBoxes)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Laden fehlgeschlagen.'))
  }, [])

  function optionalMoney(raw: string): number | null | undefined {
    const t = raw.trim()
    if (!t) return undefined
    const n = parseAmount(t)
    if (Number.isNaN(n) || n < 0) return null
    return n
  }

  async function handleCreate(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    setCreateError(null)

    if (!createForm.start_date || !createForm.end_date) {
      setCreateError('Start- und Enddatum sind Pflichtfelder.')
      return
    }
    if (createForm.end_date < createForm.start_date) {
      setCreateError('Das Enddatum muss am oder nach dem Startdatum liegen.')
      return
    }

    const minNum = parseAmount(createForm.min_amount)
    if (Number.isNaN(minNum) || minNum <= 0) {
      setCreateError('Bitte einen Mindestbetrag pro Termin größer 0 eingeben.')
      return
    }

    const penalty = optionalMoney(createForm.penalty_amount)
    if (penalty === null) {
      setCreateError('Strafgebühr: ungültiger Betrag.')
      return
    }
    const target = optionalMoney(createForm.target_amount)
    if (target === null) {
      setCreateError('Gesamtziel: ungültiger Betrag.')
      return
    }
    const personal = optionalMoney(createForm.personal_amount)
    if (personal === null) {
      setCreateError('Persönliches Termziel: ungültiger Betrag.')
      return
    }

    const payload: SavingsBoxCreate = {
      name: createForm.name.trim(),
      start_date: createForm.start_date,
      end_date: createForm.end_date,
      interval: createForm.interval,
      min_amount_per_term: minNum,
      location: createForm.location.trim() || null,
      box_number: createForm.box_number.trim() || null,
      penalty_amount: penalty,
      target_amount: target,
      personal_amount_per_term: personal,
    }

    setCreateLoading(true)
    try {
      const detail = await createBox(payload)
      setBoxes(prev => {
        const row: SavingsBoxRead = {
          id: detail.id,
          name: detail.name,
          location: detail.location,
          box_number: detail.box_number,
          start_date: detail.start_date,
          end_date: detail.end_date,
          interval: detail.interval,
          min_amount_per_term: detail.min_amount_per_term,
          penalty_amount: detail.penalty_amount,
          status: detail.status,
          next_open_due_date: detail.next_open_due_date,
          summary: detail.summary,
        }
        const rest = prev.filter(b => b.id !== row.id)
        return [row, ...rest]
      })
      setCreateForm(EMPTY_CREATE)
      setShowCreate(false)
      navigate(`/savings-box/${detail.id}`)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Fehler beim Anlegen.')
    } finally {
      setCreateLoading(false)
    }
  }

  if (loadError) {
    return <p className="sb-load-error">Fehler: {loadError}</p>
  }

  return (
    <div className="sb-page">
      <div className="sb-page-header">
        <h1 className="page-title sb-title">Sparfächer</h1>
        <button
          type="button"
          className={showCreate ? 'btn-outline' : 'btn-primary'}
          onClick={() => {
            setShowCreate(v => !v)
            setCreateForm(EMPTY_CREATE)
            setCreateError(null)
          }}
        >
          {showCreate ? 'Abbrechen' : '+ Neues Sparfach'}
        </button>
      </div>

      <p className="sb-count">
        {boxes.length === 0
          ? 'Noch kein Sparfach angelegt'
          : `${boxes.length} Sparfach${boxes.length !== 1 ? 'er' : ''}`}
      </p>

      {showCreate && (
        <div className="sb-create-card">
          <h2 className="sb-create-title">Neues Sparfach</h2>
          <form className="sb-create-form" onSubmit={handleCreate}>
            <div className="sb-form-grid">
              <label className="sb-label">
                Name *
                <input
                  className="sb-input"
                  value={createForm.name}
                  onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                  required
                  autoFocus
                />
              </label>
              <label className="sb-label">
                Ort (optional)
                <input
                  className="sb-input"
                  value={createForm.location}
                  onChange={e => setCreateForm(f => ({ ...f, location: e.target.value }))}
                />
              </label>
              <label className="sb-label">
                Fach-Nummer (optional)
                <input
                  className="sb-input"
                  value={createForm.box_number}
                  onChange={e => setCreateForm(f => ({ ...f, box_number: e.target.value }))}
                />
              </label>
              <label className="sb-label">
                Startdatum *
                <input
                  className="sb-input"
                  type="date"
                  value={createForm.start_date}
                  onChange={e => setCreateForm(f => ({ ...f, start_date: e.target.value }))}
                  required
                />
              </label>
              <label className="sb-label">
                Enddatum *
                <input
                  className="sb-input"
                  type="date"
                  value={createForm.end_date}
                  onChange={e => setCreateForm(f => ({ ...f, end_date: e.target.value }))}
                  required
                />
              </label>
              <label className="sb-label">
                Intervall *
                <select
                  className="sb-select"
                  value={createForm.interval}
                  onChange={e =>
                    setCreateForm(f => ({ ...f, interval: e.target.value as SavingsInterval }))
                  }
                >
                  {INTERVALS.map(iv => (
                    <option key={iv} value={iv}>
                      {SAVINGS_INTERVAL_LABELS[iv]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="sb-label">
                Mindestbetrag pro Termin (€) *
                <input
                  className="sb-input"
                  placeholder="z. B. 25"
                  value={createForm.min_amount}
                  onChange={e => setCreateForm(f => ({ ...f, min_amount: e.target.value }))}
                  required
                />
              </label>
              <label className="sb-label">
                Strafgebühr pro verpasstem Termin (optional)
                <input
                  className="sb-input"
                  placeholder="leer = keine automatische Strafe"
                  value={createForm.penalty_amount}
                  onChange={e => setCreateForm(f => ({ ...f, penalty_amount: e.target.value }))}
                />
              </label>
              <label className="sb-label">
                Gesamtziel (optional)
                <input
                  className="sb-input"
                  placeholder="z. B. 400"
                  value={createForm.target_amount}
                  onChange={e => setCreateForm(f => ({ ...f, target_amount: e.target.value }))}
                />
              </label>
              <label className="sb-label">
                Persönliches Termziel (optional)
                <input
                  className="sb-input"
                  placeholder="z. B. 20"
                  value={createForm.personal_amount}
                  onChange={e => setCreateForm(f => ({ ...f, personal_amount: e.target.value }))}
                />
              </label>
            </div>
            {createError && <p className="sb-form-error">{createError}</p>}
            <button type="submit" className="btn-primary" disabled={createLoading}>
              {createLoading ? 'Speichern…' : 'Sparfach anlegen'}
            </button>
          </form>
        </div>
      )}

      {boxes.length === 0 && !showCreate ? (
        <p className="sb-empty">Noch kein Sparfach angelegt.</p>
      ) : (
        <div className="sb-grid">
          {boxes.map(box => {
            const hasTarget = box.summary.target_amount != null
            const pct = progressBarWidthPct(box.summary)
            return (
              <Link key={box.id} className="sb-card" to={`/savings-box/${box.id}`}>
                <div className="sb-card-head">
                  <span className="sb-card-name">{box.name}</span>
                  {box.location ? (
                    <span className="sb-card-location"> · {box.location}</span>
                  ) : null}
                </div>
                <div className="sb-card-row">
                  Nächster Termin:{' '}
                  {box.next_open_due_date ? formatDate(box.next_open_due_date) : '—'}
                </div>
                {hasTarget ? (
                  <div className="sb-progress-wrap">
                    <div className="sb-progress-track" aria-hidden>
                      <div className="sb-progress-fill" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="sb-progress-label">
                      €{formatAmount(box.summary.net_amount)} / €
                      {formatAmount(box.summary.target_amount!)}
                    </div>
                  </div>
                ) : null}
                <div className="sb-card-meta">
                  {box.summary.terms_open} offen · {box.summary.terms_missed} verpasst
                </div>
                <div className="sb-card-footer">
                  <StatusBadge status={box.status} />
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

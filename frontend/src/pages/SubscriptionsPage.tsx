// SubscriptionsPage.tsx — Abo-Verwaltung: Liste, anlegen, bearbeiten, löschen.
//
// Neue Konzepte hier:
//   useEffect  = Code der einmalig beim Laden der Seite ausgeführt wird
//   Array-State = Liste von Abos im State halten und aktualisieren
import { useEffect, useState } from 'react'

import {
  createSubscription,
  deleteSubscription,
  getSubscriptions,
  updateSubscription,
} from '../api/subscriptions'
import type { BillingInterval, SubscriptionRead } from '../types/subscription'
import { INTERVAL_LABELS } from '../types/subscription'
import './SubscriptionsPage.css'

// Alle Intervalle in der gewünschten Reihenfolge für das Dropdown
const INTERVALS: BillingInterval[] = ['monthly', 'quarterly', 'yearly', 'biennial']

// Leeres Formular als Startwert — damit wir es nach dem Speichern einfach zurücksetzen können
const EMPTY_FORM = { name: '', amount: '', next_due_date: '', interval: 'monthly' as BillingInterval }

export default function SubscriptionsPage() {
  // Liste aller Abos
  const [subscriptions, setSubscriptions] = useState<SubscriptionRead[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  // Formular "Neues Abo": showCreate steuert ob es sichtbar ist
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_FORM)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  // Inline-Bearbeitung: editingId ist die ID des Abos das gerade bearbeitet wird (null = keines)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState(EMPTY_FORM)
  const [editError, setEditError] = useState<string | null>(null)
  const [editLoading, setEditLoading] = useState(false)

  // useEffect mit [] = läuft einmal beim ersten Rendern der Seite
  useEffect(() => {
    getSubscriptions()
      .then(setSubscriptions)
      .catch(err => setLoadError(err.message))
  }, [])

  // --- Neues Abo anlegen ---
  async function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setCreateError(null)
    setCreateLoading(true)
    try {
      const neu = await createSubscription({
        name: createForm.name,
        amount: parseFloat(createForm.amount),
        next_due_date: createForm.next_due_date,
        interval: createForm.interval,
      })
      setSubscriptions(prev => [...prev, neu])
      setCreateForm(EMPTY_FORM)
      setShowCreate(false)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Fehler beim Anlegen.')
    } finally {
      setCreateLoading(false)
    }
  }

  // --- Bearbeiten starten: Formular mit aktuellen Werten befüllen ---
  function startEdit(sub: SubscriptionRead) {
    setEditingId(sub.id)
    setEditForm({ name: sub.name, amount: sub.amount, next_due_date: sub.next_due_date, interval: sub.interval })
    setEditError(null)
  }

  // --- Abo speichern ---
  async function handleUpdate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!editingId) return
    setEditError(null)
    setEditLoading(true)
    try {
      const aktualisiert = await updateSubscription(editingId, {
        name: editForm.name,
        amount: parseFloat(editForm.amount),
        next_due_date: editForm.next_due_date,
        interval: editForm.interval,
      })
      // Das bearbeitete Abo in der Liste austauschen
      setSubscriptions(prev => prev.map(s => s.id === editingId ? aktualisiert : s))
      setEditingId(null)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setEditLoading(false)
    }
  }

  // --- Abo löschen ---
  async function handleDelete(id: string, name: string) {
    // window.confirm öffnet einen Browser-Dialog zur Bestätigung
    if (!window.confirm(`"${name}" wirklich löschen?`)) return
    try {
      await deleteSubscription(id)
      // Gelöschtes Abo aus der Liste entfernen
      setSubscriptions(prev => prev.filter(s => s.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Fehler beim Löschen.')
    }
  }

  if (loadError) return <p className="subs-load-error">Fehler: {loadError}</p>

  return (
    <div>

      {/* Seitenheader: Titel + "Neues Abo"-Button */}
      <div className="subs-page-header">
        <h1 className="page-title" style={{ margin: 0 }}>Meine Abos</h1>
        <button
          className={showCreate ? 'btn-outline' : 'btn-primary'}
          onClick={() => { setShowCreate(v => !v); setCreateForm(EMPTY_FORM); setCreateError(null) }}
        >
          {showCreate ? 'Abbrechen' : '+ Neues Abo'}
        </button>
      </div>

      <p className="subs-count">{subscriptions.length} Abo{subscriptions.length !== 1 ? 's' : ''} eingetragen</p>

      {/* Formular: Neues Abo anlegen */}
      {showCreate && (
        <div className="subs-create-card">
          <h2>Neues Abo anlegen</h2>
          <form onSubmit={handleCreate}>
            <div className="subs-input-row">
              <input
                className="subs-input"
                placeholder="Name (z. B. Netflix)"
                value={createForm.name}
                onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                required
                autoFocus
              />
              <input
                className="subs-input subs-input-sm"
                placeholder="Betrag (z. B. 9.99)"
                type="number"
                step="0.01"
                min="0"
                value={createForm.amount}
                onChange={e => setCreateForm(f => ({ ...f, amount: e.target.value }))}
                required
              />
              <input
                className="subs-input subs-input-sm"
                type="date"
                value={createForm.next_due_date}
                onChange={e => setCreateForm(f => ({ ...f, next_due_date: e.target.value }))}
                required
              />
              {/* Dropdown für das Abrechnungsintervall */}
              <select
                className="subs-select"
                value={createForm.interval}
                onChange={e => setCreateForm(f => ({ ...f, interval: e.target.value as BillingInterval }))}
              >
                {INTERVALS.map(iv => (
                  <option key={iv} value={iv}>{INTERVAL_LABELS[iv]}</option>
                ))}
              </select>
            </div>

            {createError && <p className="subs-form-error">{createError}</p>}

            <button type="submit" className="btn-primary" disabled={createLoading}>
              {createLoading ? 'Speichern…' : 'Speichern'}
            </button>
          </form>
        </div>
      )}

      {/* Abo-Liste */}
      {subscriptions.length === 0 ? (
        <p className="subs-empty">Noch keine Abos eingetragen.</p>
      ) : (
        <div className="subs-table-card">
          <table className="subs-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Betrag (€)</th>
                <th>Intervall</th>
                <th>Nächste Fälligkeit</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {subscriptions.map(sub =>
                // Wenn dieses Abo gerade bearbeitet wird → Edit-Zeile anzeigen
                editingId === sub.id ? (
                  <tr key={sub.id} className="is-editing">
                    <td colSpan={5}>
                      <form className="subs-edit-form" onSubmit={handleUpdate}>
                        <input
                          className="subs-input"
                          value={editForm.name}
                          onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                          required
                          autoFocus
                        />
                        <input
                          className="subs-input subs-input-sm"
                          type="number"
                          step="0.01"
                          min="0"
                          value={editForm.amount}
                          onChange={e => setEditForm(f => ({ ...f, amount: e.target.value }))}
                          required
                        />
                        <input
                          className="subs-input subs-input-sm"
                          type="date"
                          value={editForm.next_due_date}
                          onChange={e => setEditForm(f => ({ ...f, next_due_date: e.target.value }))}
                          required
                        />
                        <select
                          className="subs-select"
                          value={editForm.interval}
                          onChange={e => setEditForm(f => ({ ...f, interval: e.target.value as BillingInterval }))}
                        >
                          {INTERVALS.map(iv => (
                            <option key={iv} value={iv}>{INTERVAL_LABELS[iv]}</option>
                          ))}
                        </select>

                        {editError && <span className="subs-edit-error">{editError}</span>}

                        <button type="submit" className="btn-primary-sm" disabled={editLoading}>
                          {editLoading ? '…' : 'Speichern'}
                        </button>
                        <button
                          type="button"
                          className="btn-outline-sm"
                          onClick={() => setEditingId(null)}
                        >
                          Abbrechen
                        </button>
                      </form>
                    </td>
                  </tr>
                ) : (
                  // Normale Zeile
                  <tr key={sub.id}>
                    <td>{sub.name}</td>
                    <td>{parseFloat(sub.amount).toFixed(2)}</td>
                    <td><span className="subs-interval">{INTERVAL_LABELS[sub.interval]}</span></td>
                    <td>{sub.next_due_date}</td>
                    <td>
                      <div className="subs-action-cell">
                        <button className="btn-outline-sm" onClick={() => startEdit(sub)}>
                          Bearbeiten
                        </button>
                        <button className="btn-danger" onClick={() => handleDelete(sub.id, sub.name)}>
                          Löschen
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      )}

    </div>
  )
}

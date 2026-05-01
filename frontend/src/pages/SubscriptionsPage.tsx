// SubscriptionsPage.tsx — Abo-Verwaltung: Liste, anlegen, bearbeiten, löschen.
//
// Neue Konzepte hier:
//   useEffect  = Code der einmalig beim Laden der Seite ausgeführt wird
//   Array-State = Liste von Abos im State halten und aktualisieren
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  createSubscription,
  deleteSubscription,
  getSubscriptions,
  updateSubscription,
} from '../api/subscriptions'
import type { BillingInterval, SubscriptionRead } from '../types/subscription'
import { INTERVAL_LABELS } from '../types/subscription'

// Alle Intervalle in der gewünschten Reihenfolge für das Dropdown
const INTERVALS: BillingInterval[] = ['monthly', 'quarterly', 'yearly', 'biennial']

// Leeres Formular als Startwert — damit wir es nach dem Speichern einfach zurücksetzen können
const EMPTY_FORM = { name: '', amount: '', next_due_date: '', interval: 'monthly' as BillingInterval }

export default function SubscriptionsPage() {
  const navigate = useNavigate()

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

  // --- Render ---
  if (loadError) return <p style={{ color: 'red', padding: 32 }}>Fehler: {loadError}</p>

  return (
    <div style={{ maxWidth: 900, margin: '40px auto', padding: '0 16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Meine Abos</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => navigate('/dashboard')} style={{ padding: '8px 16px' }}>
            ← Dashboard
          </button>
          <button
            onClick={() => { setShowCreate(v => !v); setCreateForm(EMPTY_FORM) }}
            style={{ padding: '8px 16px' }}
          >
            {showCreate ? 'Abbrechen' : '+ Neues Abo'}
          </button>
        </div>
      </div>

      <hr style={{ margin: '24px 0' }} />

      {/* Formular: Neues Abo */}
      {showCreate && (
        <form onSubmit={handleCreate} style={{ marginBottom: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{ marginBottom: 4 }}>Neues Abo anlegen</h2>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              placeholder="Name (z.B. Netflix)"
              value={createForm.name}
              onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
              required
              style={{ flex: 2, padding: 8 }}
            />
            <input
              placeholder="Betrag (z.B. 9.99)"
              type="number"
              step="0.01"
              min="0"
              value={createForm.amount}
              onChange={e => setCreateForm(f => ({ ...f, amount: e.target.value }))}
              required
              style={{ flex: 1, padding: 8 }}
            />
            <input
              type="date"
              value={createForm.next_due_date}
              onChange={e => setCreateForm(f => ({ ...f, next_due_date: e.target.value }))}
              required
              style={{ flex: 1, padding: 8 }}
            />
            {/* Dropdown für das Abrechnungsintervall */}
            <select
              value={createForm.interval}
              onChange={e => setCreateForm(f => ({ ...f, interval: e.target.value as BillingInterval }))}
              style={{ flex: 1, padding: 8 }}
            >
              {INTERVALS.map(iv => (
                <option key={iv} value={iv}>{INTERVAL_LABELS[iv]}</option>
              ))}
            </select>
          </div>
          {createError && <p style={{ color: 'red', margin: 0 }}>{createError}</p>}
          <button type="submit" disabled={createLoading} style={{ padding: '8px 16px', alignSelf: 'flex-start' }}>
            {createLoading ? 'Speichern...' : 'Speichern'}
          </button>
        </form>
      )}

      {/* Abo-Liste */}
      {subscriptions.length === 0 ? (
        <p style={{ color: '#666' }}>Noch keine Abos eingetragen.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '2px solid #ddd' }}>
              <th style={{ padding: '8px' }}>Name</th>
              <th style={{ padding: '8px' }}>Betrag (€)</th>
              <th style={{ padding: '8px' }}>Intervall</th>
              <th style={{ padding: '8px' }}>Nächste Fälligkeit</th>
              <th style={{ padding: '8px' }}></th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map(sub => (
              // Wenn dieses Abo gerade bearbeitet wird → Edit-Zeile anzeigen
              editingId === sub.id ? (
                <tr key={sub.id} style={{ borderBottom: '1px solid #eee', background: '#fffbe6' }}>
                  <td colSpan={5} style={{ padding: 8 }}>
                    <form onSubmit={handleUpdate} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      <input
                        value={editForm.name}
                        onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                        required
                        style={{ flex: 2, padding: 6 }}
                      />
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={editForm.amount}
                        onChange={e => setEditForm(f => ({ ...f, amount: e.target.value }))}
                        required
                        style={{ flex: 1, padding: 6 }}
                      />
                      <select
                        value={editForm.interval}
                        onChange={e => setEditForm(f => ({ ...f, interval: e.target.value as BillingInterval }))}
                        style={{ flex: 1, padding: 6 }}
                      >
                        {INTERVALS.map(iv => (
                          <option key={iv} value={iv}>{INTERVAL_LABELS[iv]}</option>
                        ))}
                      </select>
                      <input
                        type="date"
                        value={editForm.next_due_date}
                        onChange={e => setEditForm(f => ({ ...f, next_due_date: e.target.value }))}
                        required
                        style={{ flex: 1, padding: 6 }}
                      />
                      {editError && <span style={{ color: 'red' }}>{editError}</span>}
                      <button type="submit" disabled={editLoading} style={{ padding: '6px 12px' }}>
                        {editLoading ? '...' : 'Speichern'}
                      </button>
                      <button type="button" onClick={() => setEditingId(null)} style={{ padding: '6px 12px' }}>
                        Abbrechen
                      </button>
                    </form>
                  </td>
                </tr>
              ) : (
                // Normale Zeile
                <tr key={sub.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: 8 }}>{sub.name}</td>
                  <td style={{ padding: 8 }}>{parseFloat(sub.amount).toFixed(2)}</td>
                  <td style={{ padding: 8, color: '#666', fontSize: 14 }}>{INTERVAL_LABELS[sub.interval]}</td>
                  <td style={{ padding: 8 }}>{sub.next_due_date}</td>
                  <td style={{ padding: 8, display: 'flex', gap: 8 }}>
                    <button onClick={() => startEdit(sub)} style={{ padding: '4px 10px' }}>
                      Bearbeiten
                    </button>
                    <button
                      onClick={() => handleDelete(sub.id, sub.name)}
                      style={{ padding: '4px 10px', color: 'red' }}
                    >
                      Löschen
                    </button>
                  </td>
                </tr>
              )
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

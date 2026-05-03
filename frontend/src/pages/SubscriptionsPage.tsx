// SubscriptionsPage.tsx — Abo-Verwaltung: Liste, anlegen, bearbeiten, pausieren, löschen.
//
// Neue Konzepte in v0.2.2 (Slice B):
//   Suche        = clientseitige Filterung per searchQuery-State
//   Paginierung  = pageSize + currentPage bestimmen welche Zeilen angezeigt werden
//   StatusBadge  = kleiner farbiger Hinweis auf den Abo-Status
//   formatAmount = Betrag immer mit Komma anzeigen (deutsches Format)
//   parseAmount  = Betragseingabe mit Komma oder Punkt akzeptieren
import { useEffect, useState } from 'react'

import {
  createSubscription,
  deleteSubscription,
  getSubscriptions,
  resumeSubscription,
  suspendSubscription,
  updateSubscription,
} from '../api/subscriptions'
import type { BillingInterval, SubscriptionRead, SubscriptionStatus } from '../types/subscription'
import {
  formatAmount,
  INTERVAL_LABELS,
  parseAmount,
  STATUS_LABELS,
} from '../types/subscription'
import './SubscriptionsPage.css'

// Alle Intervalle in der gewünschten Reihenfolge für das Dropdown
const INTERVALS: BillingInterval[] = ['monthly', 'quarterly', 'yearly', 'biennial']

// Mögliche Seitengrößen — as const damit TypeScript die genauen Werte kennt
const PAGE_SIZES = [25, 50, 100] as const

// Leeres Formular als Startwert — damit wir es nach dem Speichern einfach zurücksetzen können
const EMPTY_FORM = { name: '', amount: '', next_due_date: '', interval: 'monthly' as BillingInterval }

// Kleines Badge das den Status eines Abos anzeigt
function StatusBadge({ status }: { status: SubscriptionStatus }) {
  return (
    <span className={`subs-status-badge subs-status-${status}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

export default function SubscriptionsPage() {
  // Liste aller Abos
  const [subscriptions, setSubscriptions] = useState<SubscriptionRead[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  // Formular "Neues Abo": showCreate steuert ob es sichtbar ist
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_FORM)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  // Inline-Bearbeitung: editingId ist die ID des Abos das gerade bearbeitet wird
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState(EMPTY_FORM)
  const [editError, setEditError] = useState<string | null>(null)
  const [editLoading, setEditLoading] = useState(false)

  // Slice B: Suche + Paginierung
  const [searchQuery, setSearchQuery] = useState('')
  const [pageSize, setPageSize] = useState(25)
  const [currentPage, setCurrentPage] = useState(0)

  // useEffect mit [] = läuft einmal beim ersten Rendern der Seite
  useEffect(() => {
    getSubscriptions()
      .then(setSubscriptions)
      .catch(err => setLoadError(err.message))
  }, [])

  // --- Suche + Paginierung berechnen ---
  // Gefilterte Liste: alle Abos die den Suchtext im Namen enthalten
  const filtered = subscriptions.filter(s =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase())
  )
  // Wie viele Seiten gibt es insgesamt?
  const totalPages = Math.ceil(filtered.length / pageSize)
  // safePage: currentPage nach oben begrenzt — verhindert leere Seite wenn Einträge wegfallen.
  // Beispiel: Seite 3 von 3, letzter Eintrag wird gelöscht → totalPages wird 2,
  // safePage wird 1 → paginated zeigt korrekt die letzte Seite.
  // Math.max(..., 0) verhindert -1 wenn filtered komplett leer ist.
  // Kein useEffect nötig: der geclammpte Wert wird direkt beim Rendern berechnet.
  const safePage = Math.min(currentPage, Math.max(totalPages - 1, 0))
  // Welche Abos sollen auf der aktuellen Seite angezeigt werden?
  const paginated = filtered.slice(safePage * pageSize, (safePage + 1) * pageSize)

  // Bei Änderung der Suche: zurück auf Seite 1 damit alte Ergebnisse nicht weiter blättern
  function handleSearchChange(q: string) {
    setSearchQuery(q)
    setCurrentPage(0)
  }

  // Bei Änderung der Seitengröße: ebenfalls zurück auf Seite 1
  function handlePageSizeChange(size: number) {
    setPageSize(size)
    setCurrentPage(0)
  }

  // --- Neues Abo anlegen ---
  async function handleCreate(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    setCreateError(null)

    // Betrag parsen — akzeptiert "9,99" oder "9.99"
    const amountNum = parseAmount(createForm.amount)
    if (isNaN(amountNum) || amountNum < 0) {
      setCreateError('Bitte einen gültigen Betrag eingeben (z. B. 9,99).')
      return
    }

    setCreateLoading(true)
    try {
      const neu = await createSubscription({
        name: createForm.name,
        amount: amountNum,
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
    // formatAmount: "9.99" (API) → "9,99" (deutsches Format) — konsistent mit allen anderen Anzeigen
    setEditForm({ name: sub.name, amount: formatAmount(sub.amount), next_due_date: sub.next_due_date, interval: sub.interval })
    setEditError(null)
  }

  // --- Abo speichern ---
  async function handleUpdate(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!editingId) return
    setEditError(null)

    const amountNum = parseAmount(editForm.amount)
    if (isNaN(amountNum) || amountNum < 0) {
      setEditError('Bitte einen gültigen Betrag eingeben (z. B. 9,99).')
      return
    }

    setEditLoading(true)
    try {
      const aktualisiert = await updateSubscription(editingId, {
        name: editForm.name,
        amount: amountNum,
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

  // --- Abo pausieren (Soft-Lifecycle) ---
  async function handleSuspend(id: string, name: string) {
    if (!window.confirm(`"${name}" pausieren? Das Abo bleibt gespeichert und kann später gelöscht werden.`)) return
    try {
      const updated = await suspendSubscription(id, {})
      // Abo in der Liste mit aktualisierten Daten ersetzen (Status wechselt auf "suspended")
      setSubscriptions(prev => prev.map(s => s.id === id ? updated : s))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Fehler beim Pausieren.')
    }
  }

  // --- Abo fortsetzen (Resume) ---
  async function handleResume(id: string, name: string) {
    if (!window.confirm(`"${name}" wieder fortsetzen?`)) return
    try {
      const updated = await resumeSubscription(id)
      setSubscriptions(prev => prev.map(s => s.id === id ? updated : s))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Fehler beim Fortsetzen.')
    }
  }

  // --- Abo löschen (Hard Delete) ---
  async function handleDelete(id: string, name: string) {
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

      {/* Anzahl-Info — zeigt gefilterte Anzahl wenn Suche aktiv ist */}
      <p className="subs-count">
        {searchQuery
          ? `${filtered.length} von ${subscriptions.length} Abo${subscriptions.length !== 1 ? 's' : ''}`
          : `${subscriptions.length} Abo${subscriptions.length !== 1 ? 's' : ''} eingetragen`
        }
      </p>

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
              {/* type="text" statt "number" damit Komma als Dezimaltrennzeichen funktioniert */}
              <input
                className="subs-input subs-input-sm"
                placeholder="Betrag (z. B. 9,99)"
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

      {/* Toolbar: Suche + Seitengrößen-Auswahl — nur sichtbar wenn Abos vorhanden */}
      {subscriptions.length > 0 && (
        <div className="subs-toolbar">
          <input
            className="subs-search"
            placeholder="Nach Name suchen…"
            value={searchQuery}
            onChange={e => handleSearchChange(e.target.value)}
          />
          <select
            className="subs-page-size-select"
            value={pageSize}
            onChange={e => handlePageSizeChange(Number(e.target.value))}
            aria-label="Einträge pro Seite"
          >
            {PAGE_SIZES.map(n => (
              <option key={n} value={n}>{n} pro Seite</option>
            ))}
          </select>
        </div>
      )}

      {/* Abo-Liste */}
      {subscriptions.length === 0 ? (
        <p className="subs-empty">Noch keine Abos eingetragen.</p>
      ) : filtered.length === 0 ? (
        <p className="subs-empty">Keine Abos gefunden für "{searchQuery}".</p>
      ) : (
        <>
          <div className="subs-table-card">
            <table className="subs-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Betrag (€)</th>
                  <th>Intervall</th>
                  <th>Nächste Fälligkeit</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {paginated.map(sub =>
                  // Wenn dieses Abo gerade bearbeitet wird → Edit-Zeile anzeigen
                  editingId === sub.id ? (
                    <tr key={sub.id} className="is-editing">
                      {/* colSpan=6 weil wir jetzt 6 Spalten haben */}
                      <td colSpan={6}>
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
                            placeholder="Betrag (z. B. 9,99)"
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
                      <td><StatusBadge status={sub.status} /></td>
                      {/* formatAmount wandelt "9.99" → "9,99" um */}
                      <td>{formatAmount(sub.amount)}</td>
                      <td><span className="subs-interval">{INTERVAL_LABELS[sub.interval]}</span></td>
                      <td>{sub.next_due_date}</td>
                      <td>
                        <div className="subs-action-cell">
                          {/* Aktive Abos: Bearbeiten + Pausieren */}
                          {sub.status === 'active' && (
                            <>
                              <button className="btn-outline-sm" onClick={() => startEdit(sub)}>
                                Bearbeiten
                              </button>
                              <button
                                className="btn-outline-sm subs-btn-suspend"
                                onClick={() => handleSuspend(sub.id, sub.name)}
                              >
                                Pausieren
                              </button>
                            </>
                          )}
                          {/* Pausierte Abos: Fortsetzen */}
                          {sub.status === 'suspended' && (
                            <button
                              className="btn-outline-sm subs-btn-resume"
                              onClick={() => handleResume(sub.id, sub.name)}
                            >
                              Fortsetzen
                            </button>
                          )}
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

          {/* Paginierung — nur wenn mehr als eine Seite existiert */}
          {totalPages > 1 && (
            <div className="subs-pagination">
              <button
                className="btn-outline-sm"
                disabled={safePage === 0}
                onClick={() => setCurrentPage(safePage - 1)}
              >
                ← Zurück
              </button>
              <span className="subs-pagination-info">
                Seite {safePage + 1} von {totalPages}
              </span>
              <button
                className="btn-outline-sm"
                disabled={safePage >= totalPages - 1}
                onClick={() => setCurrentPage(safePage + 1)}
              >
                Weiter →
              </button>
            </div>
          )}
        </>
      )}

    </div>
  )
}

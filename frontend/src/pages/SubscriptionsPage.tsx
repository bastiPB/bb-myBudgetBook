// SubscriptionsPage.tsx — Abo-Verwaltung: Liste, anlegen, bearbeiten, pausieren, löschen.
//
// v0.2.3-Änderungen:
//   - next_due_date aus Formular entfernt (wird serverseitig berechnet)
//   - amount aus Edit-Formular entfernt (Preisänderungen via Detailseite)
//   - "Halbjährlich" (semiannual) als Intervall-Option
//   - window.confirm() ersetzt durch ConfirmModal
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import ConfirmModal from '../components/ConfirmModal'
import TagBadge from '../components/TagBadge'
import TagManagementModal from '../components/TagManagementModal'
import TagSelector from '../components/TagSelector'
import {
  createSubscription,
  deleteSubscription,
  getLogoUrl,
  getSubscriptions,
  resumeSubscription,
  suspendSubscription,
  updateSubscription,
} from '../api/subscriptions'
import { getTags, setSubscriptionTags } from '../api/tags'
import type { BillingInterval, SubscriptionRead, SubscriptionStatus } from '../types/subscription'
import type { TagRead } from '../types/tag'
import {
  formatAmount,
  formatDate,
  INTERVAL_LABELS,
  parseAmount,
  STATUS_LABELS,
} from '../types/subscription'
import './SubscriptionsPage.css'

// Alle Intervalle in der gewünschten Reihenfolge für das Dropdown (v0.2.3: semiannual neu)
const INTERVALS: BillingInterval[] = ['monthly', 'quarterly', 'semiannual', 'yearly', 'biennial']

// Mögliche Seitengrößen — as const damit TypeScript die genauen Werte kennt
const PAGE_SIZES = [25, 50, 100] as const

// Startformular für "Neues Abo": started_on optional (Backend setzt default auf heute)
const EMPTY_CREATE = { name: '', amount: '', started_on: '', interval: 'monthly' as BillingInterval }

// Startformular fuer "Bearbeiten": Intervallwechsel laufen ueber die Detailseite.
const EMPTY_EDIT = { name: '' }

// Typ für den Modal-State: null = kein Modal offen
type ModalState = {
  title: string
  body?: string
  dangerous?: boolean
  confirmText?: string
  onConfirm: () => void
}

// Kleines Logo-Thumbnail für die Tabelle (28×28 px).
function LogoThumb({ logoUrl, name }: { logoUrl: string | null; name: string }) {
  if (logoUrl) {
    return <img src={getLogoUrl(logoUrl)!} alt="" className="subs-logo-thumb" />
  }
  return <div className="subs-logo-fallback">{name.charAt(0).toUpperCase()}</div>
}

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
  const [createForm, setCreateForm] = useState(EMPTY_CREATE)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  // Inline-Bearbeitung: editingId ist die ID des Abos das gerade bearbeitet wird
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState(EMPTY_EDIT)
  const [editError, setEditError] = useState<string | null>(null)
  const [editLoading, setEditLoading] = useState(false)

  // Bestätigungs-Modal: null = geschlossen
  const [modal, setModal] = useState<ModalState | null>(null)

  // Alle Tags des Users (für TagSelector im Erstell-Formular)
  const [allTags, setAllTags] = useState<TagRead[]>([])
  // Gewählte Tag-IDs im Erstell-Formular
  const [createTagIds, setCreateTagIds] = useState<string[]>([])
  // Aktive Tag-Filter auf der Übersichtsseite (UND-Verknüpfung)
  const [activeFilterTagIds, setActiveFilterTagIds] = useState<string[]>([])
  // Steuert ob das TagManagementModal offen ist
  const [showTagModal, setShowTagModal] = useState(false)

  // Suche + Paginierung
  const [searchQuery, setSearchQuery] = useState('')
  const [pageSize, setPageSize] = useState(25)
  const [currentPage, setCurrentPage] = useState(0)

  // useEffect mit [] = läuft einmal beim ersten Rendern der Seite
  useEffect(() => {
    getSubscriptions()
      .then(setSubscriptions)
      .catch(err => setLoadError(err.message))
    // Tags parallel laden — kein kritischer Fehler wenn es schiefgeht
    getTags()
      .then(setAllTags)
      .catch(() => {})
  }, [])

  // --- Tags nach Änderungen im TagManagementModal neu laden ---
  async function handleTagsChanged() {
    const tags = await getTags().catch(() => allTags)
    setAllTags(tags)
    // Falls gelöschte Tags in der Auswahl oder im Filter waren: bereinigen
    const validIds = new Set(tags.map(t => t.id))
    setCreateTagIds(prev => prev.filter(id => validIds.has(id)))
    setActiveFilterTagIds(prev => prev.filter(id => validIds.has(id)))
  }

  // --- Tag-Filter umschalten (Klick auf Chip) ---
  function toggleFilterTag(tagId: string) {
    setActiveFilterTagIds(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    )
    // Seitenreset damit man immer auf Seite 1 startet
    setCurrentPage(0)
  }

  // --- Suche + Tag-Filter + Paginierung berechnen ---
  const filtered = subscriptions.filter(s => {
    // Namenssuche (Groß-/Kleinschreibung ignorieren)
    if (!s.name.toLowerCase().includes(searchQuery.toLowerCase())) return false
    // Tag-Filter: Abo muss ALLE aktiven Filter-Tags besitzen (UND-Verknüpfung)
    if (activeFilterTagIds.length > 0) {
      const subTagIds = new Set(s.tags.map(t => t.id))
      if (!activeFilterTagIds.every(id => subTagIds.has(id))) return false
    }
    return true
  })
  const totalPages = Math.ceil(filtered.length / pageSize)
  // safePage: verhindert leere Seite wenn Einträge wegfallen (z. B. nach Suche oder Löschen)
  const safePage = Math.min(currentPage, Math.max(totalPages - 1, 0))
  const paginated = filtered.slice(safePage * pageSize, (safePage + 1) * pageSize)

  function handleSearchChange(q: string) {
    setSearchQuery(q)
    setCurrentPage(0)
  }

  function handlePageSizeChange(size: number) {
    setPageSize(size)
    setCurrentPage(0)
  }

  // --- Neues Abo anlegen ---
  async function handleCreate(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    setCreateError(null)

    const amountNum = parseAmount(createForm.amount)
    if (isNaN(amountNum) || amountNum < 0) {
      setCreateError('Bitte einen gültigen Betrag eingeben (z. B. 9,99).')
      return
    }

    setCreateLoading(true)
    try {
      let neu = await createSubscription({
        name: createForm.name,
        amount: amountNum,
        interval: createForm.interval,
        // started_on nur mitschicken wenn der User ein Datum eingetragen hat
        started_on: createForm.started_on || undefined,
      })
      // Falls Tags ausgewählt wurden: direkt nach dem Anlegen zuweisen
      if (createTagIds.length > 0) {
        const assignedTags = await setSubscriptionTags(neu.id, { tag_ids: createTagIds })
        neu = { ...neu, tags: assignedTags }
      }
      setSubscriptions(prev => [...prev, neu])
      setCreateForm(EMPTY_CREATE)
      setCreateTagIds([])
      setShowCreate(false)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Fehler beim Anlegen.')
    } finally {
      setCreateLoading(false)
    }
  }

  // --- Bearbeiten starten ---
  function startEdit(sub: SubscriptionRead) {
    setEditingId(sub.id)
    // Edit-Formular enthaelt nur Name; Preis/Intervall laufen ueber eigene Detail-Flows.
    setEditForm({ name: sub.name })
    setEditError(null)
  }

  // --- Abo speichern (nur Name) ---
  async function handleUpdate(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!editingId) return
    setEditError(null)
    setEditLoading(true)
    try {
      const aktualisiert = await updateSubscription(editingId, {
        name: editForm.name,
      })
      setSubscriptions(prev => prev.map(s => s.id === editingId ? aktualisiert : s))
      setEditingId(null)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setEditLoading(false)
    }
  }

  // --- Abo pausieren — öffnet Bestätigungs-Modal ---
  function handleSuspend(id: string, name: string) {
    setModal({
      title: `"${name}" pausieren?`,
      body: 'Das Abo bleibt gespeichert und kann jederzeit fortgesetzt werden.',
      onConfirm: () => {
        setModal(null)
        suspendSubscription(id, {})
          .then(updated => setSubscriptions(prev => prev.map(s => s.id === id ? updated : s)))
          .catch(err => alert(err instanceof Error ? err.message : 'Fehler beim Pausieren.'))
      },
    })
  }

  // --- Abo fortsetzen — öffnet Bestätigungs-Modal ---
  function handleResume(id: string, name: string) {
    setModal({
      title: `"${name}" fortsetzen?`,
      onConfirm: () => {
        setModal(null)
        resumeSubscription(id)
          .then(updated => setSubscriptions(prev => prev.map(s => s.id === id ? updated : s)))
          .catch(err => alert(err instanceof Error ? err.message : 'Fehler beim Fortsetzen.'))
      },
    })
  }

  // --- Abo löschen — öffnet Sicherheits-Modal (User muss Namen eintippen) ---
  function handleDelete(id: string, name: string) {
    setModal({
      title: `"${name}" löschen?`,
      body: 'Diese Aktion kann nicht rückgängig gemacht werden. Das Abo und alle zugehörigen Daten werden dauerhaft gelöscht.',
      dangerous: true,
      confirmText: name,
      onConfirm: () => {
        setModal(null)
        deleteSubscription(id)
          .then(() => setSubscriptions(prev => prev.filter(s => s.id !== id)))
          .catch(err => alert(err instanceof Error ? err.message : 'Fehler beim Löschen.'))
      },
    })
  }

  if (loadError) return <p className="subs-load-error">Fehler: {loadError}</p>

  return (
    <div>

      {/* TagManagementModal — CRUD für Tags, aufrufbar aus dem TagSelector heraus */}
      {showTagModal && (
        <TagManagementModal
          onClose={() => setShowTagModal(false)}
          onTagsChanged={handleTagsChanged}
        />
      )}

      {/* Bestätigungs-Modal — nur sichtbar wenn modal-State gesetzt */}
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

      {/* Seitenheader: Titel + "Neues Abo"-Button */}
      <div className="subs-page-header">
        <h1 className="page-title" style={{ margin: 0 }}>Meine Abos</h1>
        <button
          className={showCreate ? 'btn-outline' : 'btn-primary'}
          onClick={() => { setShowCreate(v => !v); setCreateForm(EMPTY_CREATE); setCreateError(null); setCreateTagIds([]) }}
        >
          {showCreate ? 'Abbrechen' : '+ Neues Abo'}
        </button>
      </div>

      {/* Anzahl-Info */}
      <p className="subs-count">
        {(searchQuery || activeFilterTagIds.length > 0)
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
              {/* started_on: optional — Backend setzt default auf heute wenn leer */}
              <input
                className="subs-input subs-input-sm"
                type="date"
                title="Abschlussdatum (optional — leer = heute)"
                value={createForm.started_on}
                onChange={e => setCreateForm(f => ({ ...f, started_on: e.target.value }))}
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

            {/* Tags optional beim Erstellen zuweisen */}
            <TagSelector
              allTags={allTags}
              selectedIds={createTagIds}
              onChange={setCreateTagIds}
              onManageTags={() => setShowTagModal(true)}
            />

            {createError && <p className="subs-form-error">{createError}</p>}

            <button type="submit" className="btn-primary" disabled={createLoading}>
              {createLoading ? 'Speichern…' : 'Speichern'}
            </button>
          </form>
        </div>
      )}

      {/* Toolbar: Suche + Seitengrößen-Auswahl */}
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

      {/* Tag-Filter-Leiste — nur wenn Tags vorhanden */}
      {allTags.length > 0 && (
        <div className="subs-filter-bar">
          {allTags.map(tag => (
            <button
              key={tag.id}
              type="button"
              className={`subs-filter-chip${activeFilterTagIds.includes(tag.id) ? ' active' : ''}`}
              onClick={() => toggleFilterTag(tag.id)}
              style={activeFilterTagIds.includes(tag.id) ? { borderColor: tag.color, color: tag.color, background: `${tag.color}18` } : {}}
            >
              {/* Farbpunkt des Tags */}
              <span className="subs-filter-chip-dot" style={{ background: tag.color }} />
              {tag.name}
            </button>
          ))}
          {/* Zurücksetzen-Button — nur wenn ein Filter aktiv ist */}
          {activeFilterTagIds.length > 0 && (
            <button
              type="button"
              className="subs-filter-reset"
              onClick={() => { setActiveFilterTagIds([]); setCurrentPage(0) }}
            >
              Filter zurücksetzen
            </button>
          )}
        </div>
      )}

      {/* Abo-Liste */}
      {subscriptions.length === 0 ? (
        <p className="subs-empty">Noch keine Abos eingetragen.</p>
      ) : filtered.length === 0 ? (
        <p className="subs-empty">
          {activeFilterTagIds.length > 0
            ? 'Kein Abo hat alle gewählten Tags.'
            : `Keine Abos gefunden für "${searchQuery}".`
          }
        </p>
      ) : (
        <>
          <div className="subs-table-card">
            <table className="subs-table">
              <thead>
                <tr>
                  <th></th>{/* Logo */}
                  <th>Name</th>
                  <th>Status</th>
                  <th>Betrag (€)</th>
                  <th>Intervall</th>
                  <th>Nächste Fälligkeit</th>
                  <th></th>{/* Aktionen */}
                </tr>
              </thead>
              <tbody>
                {paginated.map(sub =>
                  editingId === sub.id ? (
                    // Edit-Zeile: nur Name; Preis und Intervall laufen ueber die Detailseite.
                    <tr key={sub.id} className="is-editing">
                      <td colSpan={7}>
                        <form className="subs-edit-form" onSubmit={handleUpdate}>
                          <input
                            className="subs-input"
                            value={editForm.name}
                            onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                            required
                            autoFocus
                          />
                          <span className="subs-interval">{INTERVAL_LABELS[sub.interval]}</span>

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
                      <td><LogoThumb logoUrl={sub.logo_url} name={sub.name} /></td>
                      <td>
                        <Link className="subs-name-link" to={`/subscriptions/${sub.id}`}>{sub.name}</Link>
                        {sub.tags.length > 0 && (
                          <div className="subs-tags-row">
                            {sub.tags.map(tag => <TagBadge key={tag.id} tag={tag} />)}
                          </div>
                        )}
                      </td>
                      <td><StatusBadge status={sub.status} /></td>
                      <td>{formatAmount(sub.amount)}</td>
                      <td><span className="subs-interval">{INTERVAL_LABELS[sub.interval]}</span></td>
                      {/* next_due_date ist jetzt nullable (Zukunfts-Abos) */}
                      <td>{sub.next_due_date ? formatDate(sub.next_due_date) : '—'}</td>
                      <td>
                        <div className="subs-action-cell">
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

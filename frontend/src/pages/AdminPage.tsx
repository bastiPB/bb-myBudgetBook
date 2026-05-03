// AdminPage.tsx — User-Verwaltung für Admins.
// Zeigt alle User in einer Tabelle: Status, Rolle, Aktionen (freigeben, Rolle ändern, löschen).
// Admins können hier auch direkt neue User anlegen (sofort active, kein pending-Schritt).
import { useEffect, useState } from 'react'

import { approveUser, createUser, deleteUser, getUsers, updateUserRole } from '../api/admin'
import { useAuth } from '../context/useAuth'
import type { UserRead, UserRole } from '../types/user'
import './AdminPage.css'

// Alle gültigen Rollen als Array — wird für Dropdowns gebraucht
const ROLES: UserRole[] = ['admin', 'editor', 'default']

// Leeres Formular-Objekt — zum Zurücksetzen nach dem Anlegen
const EMPTY_CREATE_FORM = { email: '', password: '', role: 'editor' as UserRole }

export default function AdminPage() {
  const { user: currentUser } = useAuth()

  // Liste aller User + möglicher Ladefehler
  const [users, setUsers] = useState<UserRead[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  // Formular "Neuen User anlegen"
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_CREATE_FORM)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  // Welche User-IDs gerade eine laufende Aktion haben (verhindert Doppel-Klicks)
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set())

  // Fehlermeldungen pro User-ID (z.B. "403 Forbidden" wenn Admin sich selbst ändert)
  const [errors, setErrors] = useState<Record<string, string>>({})

  // Beim ersten Rendern alle User laden
  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(err => setLoadError(err.message))
  }, [])

  // --- Neuen User anlegen (Admin-Variante: sofort active) ---
  async function handleCreate(e: React.SyntheticEvent) {
    e.preventDefault()
    setCreateError(null)
    setCreateLoading(true)
    try {
      const newUser = await createUser(createForm.email, createForm.password, createForm.role)
      // Neuen User zur Liste hinzufügen — kein Reload nötig
      setUsers(prev => [...prev, newUser])
      setCreateForm(EMPTY_CREATE_FORM)
      setShowCreate(false)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Fehler beim Anlegen.')
    } finally {
      setCreateLoading(false)
    }
  }

  // Hilfsfunktion: Aktion für einen User starten (Loading-State setzen)
  function startAction(id: string) {
    setPendingIds(prev => new Set(prev).add(id))
    // Bisherige Fehlermeldung für diesen User löschen
    setErrors(prev => { const next = { ...prev }; delete next[id]; return next })
  }

  // Hilfsfunktion: Aktion für einen User beenden
  function endAction(id: string) {
    setPendingIds(prev => { const next = new Set(prev); next.delete(id); return next })
  }

  // User freigeben: status "pending" → "active"
  async function handleApprove(userId: string) {
    startAction(userId)
    try {
      const updated = await approveUser(userId)
      // Den freigegebenen User in der Liste aktualisieren
      setUsers(prev => prev.map(u => u.id === userId ? updated : u))
    } catch (err) {
      setErrors(prev => ({ ...prev, [userId]: err instanceof Error ? err.message : 'Fehler' }))
    } finally {
      endAction(userId)
    }
  }

  // Rolle ändern über das Dropdown-Menü
  async function handleRoleChange(userId: string, newRole: UserRole) {
    startAction(userId)
    try {
      const updated = await updateUserRole(userId, newRole)
      setUsers(prev => prev.map(u => u.id === userId ? updated : u))
    } catch (err) {
      setErrors(prev => ({ ...prev, [userId]: err instanceof Error ? err.message : 'Fehler' }))
    } finally {
      endAction(userId)
    }
  }

  // User löschen (mit Bestätigungsdialog)
  async function handleDelete(userId: string, email: string) {
    if (!window.confirm(`"${email}" wirklich löschen? Alle Abos werden mitgelöscht.`)) return
    startAction(userId)
    try {
      await deleteUser(userId)
      // Gelöschten User aus der Liste entfernen
      setUsers(prev => prev.filter(u => u.id !== userId))
    } catch (err) {
      setErrors(prev => ({ ...prev, [userId]: err instanceof Error ? err.message : 'Fehler' }))
    } finally {
      endAction(userId)
    }
  }

  if (loadError) return <p className="admin-load-error">Fehler: {loadError}</p>

  return (
    <div>

      {/* Seitenheader: Titel + "Neuen User anlegen"-Button */}
      <div className="admin-page-header">
        <h1 className="page-title" style={{ margin: 0 }}>User-Verwaltung</h1>
        <button
          className={showCreate ? 'btn-outline' : 'btn-primary'}
          onClick={() => { setShowCreate(v => !v); setCreateForm(EMPTY_CREATE_FORM); setCreateError(null) }}
        >
          {showCreate ? 'Abbrechen' : '+ Neuen User anlegen'}
        </button>
      </div>

      <p className="admin-count">{users.length} User registriert</p>

      {/* Formular: Neuen User anlegen */}
      {showCreate && (
        <div className="admin-create-card">
          <h2>Neuen User anlegen</h2>
          <p>
            Der User wird sofort freigeschaltet. Teile das Passwort dem User mit — er kann es später ändern.
          </p>
          <form onSubmit={handleCreate}>
            <div className="admin-input-row">
              <input
                className="admin-input"
                type="email"
                placeholder="E-Mail"
                value={createForm.email}
                onChange={e => setCreateForm(f => ({ ...f, email: e.target.value }))}
                required
                autoFocus
              />
              <input
                className="admin-input"
                type="password"
                placeholder="Passwort (min. 8 Zeichen)"
                value={createForm.password}
                onChange={e => setCreateForm(f => ({ ...f, password: e.target.value }))}
                required
                minLength={8}
              />
              {/* Rollen-Dropdown — Standard ist editor (häufigstes Familienmitglied) */}
              <select
                className="admin-select"
                value={createForm.role}
                onChange={e => setCreateForm(f => ({ ...f, role: e.target.value as UserRole }))}
              >
                {ROLES.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>

            {createError && <p className="admin-form-error">{createError}</p>}

            <button type="submit" className="btn-primary" disabled={createLoading}>
              {createLoading ? 'Anlegen…' : 'Anlegen'}
            </button>
          </form>
        </div>
      )}

      {/* User-Tabelle */}
      {users.length === 0 ? (
        <p className="admin-empty">Keine User gefunden.</p>
      ) : (
        <div className="admin-table-card">
          <table className="admin-table">
            <thead>
              <tr>
                <th>E-Mail</th>
                <th>Status</th>
                <th>Rolle</th>
                <th>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const isSelf = u.id === currentUser?.id
                const isPending = pendingIds.has(u.id)
                const rowError = errors[u.id]

                return (
                  <tr key={u.id} className={isSelf ? 'is-self' : undefined}>

                    {/* E-Mail + "(du)"-Markierung */}
                    <td>
                      {u.email}
                      {isSelf && <span className="self-badge">(du)</span>}
                    </td>

                    {/* Status als farbiges Badge */}
                    <td>
                      <span className={`badge ${u.status === 'active' ? 'badge--active' : 'badge--pending'}`}>
                        {u.status === 'active' ? 'Aktiv' : 'Ausstehend'}
                      </span>
                    </td>

                    {/* Rolle als Dropdown — deaktiviert für sich selbst */}
                    <td>
                      <select
                        className="role-select"
                        value={u.role}
                        disabled={isSelf || isPending}
                        onChange={e => handleRoleChange(u.id, e.target.value as UserRole)}
                      >
                        {ROLES.map(r => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </td>

                    {/* Aktions-Buttons */}
                    <td>
                      <div className="action-cell">

                        {/* Freigeben — nur sichtbar wenn Status "pending" */}
                        {u.status === 'pending' && (
                          <button
                            className="btn-approve"
                            onClick={() => handleApprove(u.id)}
                            disabled={isPending}
                          >
                            {isPending ? '…' : 'Freigeben'}
                          </button>
                        )}

                        {/* Löschen — deaktiviert für sich selbst */}
                        <button
                          className="btn-danger"
                          onClick={() => handleDelete(u.id, u.email)}
                          disabled={isSelf || isPending}
                        >
                          Löschen
                        </button>

                        {/* Fehlermeldung für diese Zeile */}
                        {rowError && <span className="row-error">{rowError}</span>}

                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

    </div>
  )
}

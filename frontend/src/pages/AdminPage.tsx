// AdminPage.tsx — User-Verwaltung für Admins.
// Zeigt alle User in einer Tabelle: Status, Rolle, Aktionen (freigeben, Rolle ändern, löschen).
// Admins können hier auch direkt neue User anlegen (sofort active, kein pending-Schritt).
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { approveUser, createUser, deleteUser, getUsers, updateUserRole } from '../api/admin'
import { useAuth } from '../context/useAuth'
import type { UserRead, UserRole } from '../types/user'

// Alle gültigen Rollen als Array — wird für Dropdowns gebraucht
const ROLES: UserRole[] = ['admin', 'editor', 'default']

// Leeres Formular-Objekt — zum Zurücksetzen nach dem Anlegen
const EMPTY_CREATE_FORM = { email: '', password: '', role: 'editor' as UserRole }

export default function AdminPage() {
  const { user: currentUser } = useAuth()
  const navigate = useNavigate()

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

  if (loadError) return <p style={{ color: 'red', padding: 32 }}>Fehler: {loadError}</p>

  return (
    <div style={{ maxWidth: 900, margin: '40px auto', padding: '0 16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Admin — User-Verwaltung</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => navigate('/dashboard')} style={{ padding: '8px 16px' }}>
            ← Dashboard
          </button>
          <button
            onClick={() => { setShowCreate(v => !v); setCreateForm(EMPTY_CREATE_FORM); setCreateError(null) }}
            style={{ padding: '8px 16px' }}
          >
            {showCreate ? 'Abbrechen' : '+ Neuen User anlegen'}
          </button>
        </div>
      </div>
      <p style={{ color: '#666', marginTop: 4 }}>
        {users.length} User registriert
      </p>

      <hr style={{ margin: '24px 0' }} />

      {/* Formular: Neuen User anlegen */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          style={{ marginBottom: 24, display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          <h2 style={{ marginBottom: 4 }}>Neuen User anlegen</h2>
          <p style={{ color: '#666', fontSize: 14, margin: 0 }}>
            Der User wird sofort freigeschaltet. Teile das Passwort dem User mit — er kann es später ändern.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              type="email"
              placeholder="E-Mail"
              value={createForm.email}
              onChange={e => setCreateForm(f => ({ ...f, email: e.target.value }))}
              required
              style={{ flex: 2, padding: 8 }}
            />
            <input
              type="password"
              placeholder="Passwort (min. 8 Zeichen)"
              value={createForm.password}
              onChange={e => setCreateForm(f => ({ ...f, password: e.target.value }))}
              required
              minLength={8}
              style={{ flex: 2, padding: 8 }}
            />
            {/* Rollen-Dropdown — Standard ist editor (häufigstes Familienmitglied) */}
            <select
              value={createForm.role}
              onChange={e => setCreateForm(f => ({ ...f, role: e.target.value as UserRole }))}
              style={{ flex: 1, padding: 8 }}
            >
              {ROLES.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          {createError && <p style={{ color: 'red', margin: 0 }}>{createError}</p>}
          <button
            type="submit"
            disabled={createLoading}
            style={{ padding: '8px 16px', alignSelf: 'flex-start' }}
          >
            {createLoading ? 'Anlegen...' : 'Anlegen'}
          </button>
        </form>
      )}

      {/* User-Tabelle */}
      {users.length === 0 ? (
        <p style={{ color: '#666' }}>Keine User gefunden.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '2px solid #ddd' }}>
              <th style={{ padding: '8px' }}>E-Mail</th>
              <th style={{ padding: '8px' }}>Status</th>
              <th style={{ padding: '8px' }}>Rolle</th>
              <th style={{ padding: '8px' }}>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => {
              const isSelf = u.id === currentUser?.id
              const isPending = pendingIds.has(u.id)
              const rowError = errors[u.id]

              return (
                <tr
                  key={u.id}
                  style={{
                    borderBottom: '1px solid #eee',
                    // Eigene Zeile leicht hervorheben
                    background: isSelf ? '#f0f8ff' : undefined,
                  }}
                >
                  {/* E-Mail + "(du)" Markierung */}
                  <td style={{ padding: 8 }}>
                    {u.email}
                    {isSelf && <span style={{ color: '#888', fontSize: 12, marginLeft: 6 }}>(du)</span>}
                  </td>

                  {/* Status als farbiges Badge */}
                  <td style={{ padding: 8 }}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: 13,
                      background: u.status === 'active' ? '#d4edda' : '#fff3cd',
                      color: u.status === 'active' ? '#155724' : '#856404',
                    }}>
                      {u.status === 'active' ? 'Aktiv' : 'Ausstehend'}
                    </span>
                  </td>

                  {/* Rolle als Dropdown — deaktiviert für sich selbst */}
                  <td style={{ padding: 8 }}>
                    <select
                      value={u.role}
                      disabled={isSelf || isPending}
                      onChange={e => handleRoleChange(u.id, e.target.value as UserRole)}
                      style={{ padding: '4px 8px' }}
                    >
                      {ROLES.map(r => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </td>

                  {/* Aktions-Buttons */}
                  <td style={{ padding: 8 }}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>

                      {/* Freigeben — nur sichtbar wenn Status "pending" */}
                      {u.status === 'pending' && (
                        <button
                          onClick={() => handleApprove(u.id)}
                          disabled={isPending}
                          style={{ padding: '4px 10px', color: 'green' }}
                        >
                          {isPending ? '...' : 'Freigeben'}
                        </button>
                      )}

                      {/* Löschen — deaktiviert für sich selbst */}
                      <button
                        onClick={() => handleDelete(u.id, u.email)}
                        disabled={isSelf || isPending}
                        style={{ padding: '4px 10px', color: 'red' }}
                      >
                        Löschen
                      </button>

                      {/* Fehlermeldung für diese Zeile */}
                      {rowError && (
                        <span style={{ color: 'red', fontSize: 13 }}>{rowError}</span>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

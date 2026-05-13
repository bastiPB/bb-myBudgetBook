// TagManagementModal — CRUD-Modal zum Erstellen, Umbenennen und Löschen von Tags.
// Erreichbar über den "Tags verwalten..."-Link im TagSelector.
//
// Funktionen:
//   - Alle Tags des Users anzeigen
//   - Neuen Tag erstellen (Name + Farbauswahl)
//   - Bestehenden Tag inline bearbeiten
//   - Tag löschen mit Inline-Warnung

import { useEffect, useState } from 'react'
import { createTag, deleteTag, getTags, updateTag } from '../api/tags'
import { TAG_COLORS } from '../types/tag'
import type { TagRead } from '../types/tag'
import './TagManagementModal.css'

interface TagManagementModalProps {
  onClose: () => void
  // Wird aufgerufen sobald sich Tags geändert haben — Parent kann seine Tag-Liste refreshen
  onTagsChanged: () => void
}

export default function TagManagementModal({ onClose, onTagsChanged }: TagManagementModalProps) {
  // Alle Tags des Users
  const [tags, setTags] = useState<TagRead[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  // "Neuer Tag erstellen"-Formular
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(TAG_COLORS[0].hex)
  const [createError, setCreateError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  // Inline-Bearbeitung: welcher Tag wird gerade bearbeitet?
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editColor, setEditColor] = useState('')
  const [editError, setEditError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Lösch-Bestätigung: welcher Tag hat die Inline-Warnung sichtbar?
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // Tags beim Öffnen laden
  useEffect(() => {
    loadTags()
  }, [])

  async function loadTags() {
    try {
      const loaded = await getTags()
      setTags(loaded)
      setLoadError(null)
    } catch {
      setLoadError('Tags konnten nicht geladen werden.')
    }
  }

  // ── Neuen Tag erstellen ──

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    setCreateError(null)
    try {
      await createTag({ name: newName.trim(), color: newColor })
      setNewName('')
      setNewColor(TAG_COLORS[0].hex)
      await loadTags()
      onTagsChanged()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Fehler beim Erstellen.')
    } finally {
      setCreating(false)
    }
  }

  // ── Bearbeitung starten ──

  function startEdit(tag: TagRead) {
    // Falls gerade ein anderer Tag gelöscht werden soll: zurücksetzen
    setDeletingId(null)
    setDeleteError(null)
    setEditingId(tag.id)
    setEditName(tag.name)
    setEditColor(tag.color)
    setEditError(null)
  }

  function cancelEdit() {
    setEditingId(null)
    setEditError(null)
  }

  // ── Bearbeitung speichern ──

  async function handleSaveEdit(tagId: string) {
    setSaving(true)
    setEditError(null)
    try {
      await updateTag(tagId, { name: editName.trim(), color: editColor })
      setEditingId(null)
      await loadTags()
      onTagsChanged()
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Fehler beim Speichern.')
    } finally {
      setSaving(false)
    }
  }

  // ── Löschen ──

  function requestDelete(tagId: string) {
    // Falls gerade ein anderer Tag bearbeitet wird: zurücksetzen
    setEditingId(null)
    setEditError(null)
    setDeletingId(tagId)
    setDeleteError(null)
  }

  function cancelDelete() {
    setDeletingId(null)
    setDeleteError(null)
  }

  async function handleConfirmDelete(tagId: string) {
    setDeleteError(null)
    try {
      await deleteTag(tagId)
      setDeletingId(null)
      await loadTags()
      onTagsChanged()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Fehler beim Löschen.')
    }
  }

  return (
    // Klick auf den Hintergrund schließt das Modal
    <div className="tag-mgmt-backdrop" onClick={onClose}>
      <div
        className="tag-mgmt-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Tags verwalten"
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="tag-mgmt-header">
          <h2 className="tag-mgmt-title">Tags verwalten</h2>
          <button className="tag-mgmt-close" onClick={onClose} aria-label="Schließen" type="button">
            ✕
          </button>
        </div>

        {/* ── Neuen Tag erstellen ── */}
        <form className="tag-mgmt-create-form" onSubmit={handleCreate}>
          <p className="tag-mgmt-section-label">Neuen Tag erstellen</p>

          {/* Farbauswahl */}
          <div className="tag-color-picker">
            {TAG_COLORS.map(c => (
              <button
                key={c.hex}
                type="button"
                className={`tag-color-swatch${newColor === c.hex ? ' selected' : ''}`}
                style={{ background: c.hex }}
                onClick={() => setNewColor(c.hex)}
                aria-label={c.label}
                title={c.label}
              />
            ))}
          </div>

          <div className="tag-mgmt-create-row">
            <input
              className="tag-mgmt-input"
              type="text"
              placeholder="Tag-Name..."
              value={newName}
              maxLength={50}
              onChange={e => setNewName(e.target.value)}
            />
            <button
              className="tag-mgmt-btn-primary"
              type="submit"
              disabled={creating || !newName.trim()}
            >
              {creating ? '...' : 'Erstellen'}
            </button>
          </div>

          {createError && <p className="tag-mgmt-error">{createError}</p>}
        </form>

        {/* ── Bestehende Tags ── */}
        <div className="tag-mgmt-list">
          <p className="tag-mgmt-section-label">Vorhandene Tags</p>

          {loadError && <p className="tag-mgmt-error">{loadError}</p>}

          {tags.length === 0 && !loadError && (
            <p className="tag-mgmt-empty">Noch keine Tags angelegt.</p>
          )}

          {tags.map(tag => (
            <div key={tag.id} className="tag-mgmt-row">

              {editingId === tag.id ? (
                /* ── Inline-Bearbeitung ── */
                <div className="tag-mgmt-edit-form">
                  <div className="tag-color-picker">
                    {TAG_COLORS.map(c => (
                      <button
                        key={c.hex}
                        type="button"
                        className={`tag-color-swatch${editColor === c.hex ? ' selected' : ''}`}
                        style={{ background: c.hex }}
                        onClick={() => setEditColor(c.hex)}
                        aria-label={c.label}
                        title={c.label}
                      />
                    ))}
                  </div>
                  <div className="tag-mgmt-create-row">
                    <input
                      className="tag-mgmt-input"
                      type="text"
                      value={editName}
                      maxLength={50}
                      onChange={e => setEditName(e.target.value)}
                      autoFocus
                    />
                    <button
                      className="tag-mgmt-btn-primary"
                      type="button"
                      onClick={() => handleSaveEdit(tag.id)}
                      disabled={saving || !editName.trim()}
                    >
                      {saving ? '...' : 'Speichern'}
                    </button>
                    <button
                      className="tag-mgmt-btn-ghost"
                      type="button"
                      onClick={cancelEdit}
                    >
                      Abbrechen
                    </button>
                  </div>
                  {editError && <p className="tag-mgmt-error">{editError}</p>}
                </div>
              ) : (
                /* ── Normale Tag-Zeile ── */
                <div className="tag-mgmt-tag-line">
                  {/* Farbpunkt + Name */}
                  <span className="tag-mgmt-dot" style={{ background: tag.color }} />
                  <span className="tag-mgmt-name">{tag.name}</span>

                  {/* Aktions-Buttons */}
                  <button
                    className="tag-mgmt-icon-btn"
                    type="button"
                    onClick={() => startEdit(tag)}
                    aria-label={`"${tag.name}" bearbeiten`}
                    title="Bearbeiten"
                  >
                    ✏️
                  </button>
                  <button
                    className="tag-mgmt-icon-btn tag-mgmt-icon-btn--danger"
                    type="button"
                    onClick={() => requestDelete(tag.id)}
                    aria-label={`"${tag.name}" löschen`}
                    title="Löschen"
                  >
                    🗑️
                  </button>
                </div>
              )}

              {/* ── Inline-Lösch-Warnung ── */}
              {deletingId === tag.id && (
                <div className="tag-mgmt-delete-warning">
                  <span className="tag-mgmt-warning-text">
                    Dieser Tag wird aus allen zugehörigen Abos entfernt.
                  </span>
                  <div className="tag-mgmt-delete-actions">
                    <button
                      className="tag-mgmt-btn-danger"
                      type="button"
                      onClick={() => handleConfirmDelete(tag.id)}
                    >
                      Löschen
                    </button>
                    <button
                      className="tag-mgmt-btn-ghost"
                      type="button"
                      onClick={cancelDelete}
                    >
                      Abbrechen
                    </button>
                  </div>
                  {deleteError && <p className="tag-mgmt-error">{deleteError}</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

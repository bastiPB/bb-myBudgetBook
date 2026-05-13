// TagSelector — Multi-Select-Dropdown zur Tag-Zuweisung bei einem Abo.
// Zeigt ausgewählte Tags als Badges. Öffnet ein Dropdown mit allen verfügbaren Tags.
// "Tags verwalten..." öffnet das TagManagementModal (Callback vom Parent).

import { useEffect, useRef, useState } from 'react'
import type { TagRead } from '../types/tag'
import TagBadge from './TagBadge'
import './TagSelector.css'

interface TagSelectorProps {
  allTags: TagRead[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
  onManageTags: () => void
}

export default function TagSelector({ allTags, selectedIds, onChange, onManageTags }: TagSelectorProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Klick außerhalb schließt das Dropdown
  useEffect(() => {
    if (!open) return
    function handleOutsideClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [open])

  // Nur Tags die wirklich ausgewählt sind (Abgleich mit allTags)
  const selectedTags = allTags.filter(t => selectedIds.includes(t.id))

  function toggle(tagId: string) {
    if (selectedIds.includes(tagId)) {
      // Tag abwählen
      onChange(selectedIds.filter(id => id !== tagId))
    } else {
      // Tag hinzufügen
      onChange([...selectedIds, tagId])
    }
  }

  function handleManageTags(e: React.MouseEvent) {
    e.stopPropagation()
    setOpen(false)
    onManageTags()
  }

  return (
    <div className="tag-selector" ref={containerRef}>
      {/* Klick auf den Kontrollbereich öffnet/schließt das Dropdown */}
      <div
        className={`tag-selector-control${open ? ' open' : ''}`}
        onClick={() => setOpen(v => !v)}
        role="button"
        aria-expanded={open}
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && setOpen(v => !v)}
      >
        <div className="tag-selector-badges">
          {selectedTags.length === 0 ? (
            <span className="tag-selector-placeholder">Tags auswählen...</span>
          ) : (
            selectedTags.map(tag => (
              <TagBadge
                key={tag.id}
                tag={tag}
                onRemove={e => { e.stopPropagation(); toggle(tag.id) }}
              />
            ))
          )}
        </div>
        {/* Pfeil zeigt ob das Dropdown offen ist */}
        <span className="tag-selector-chevron" aria-hidden>{open ? '▲' : '▼'}</span>
      </div>

      {open && (
        <div className="tag-selector-dropdown" role="listbox" aria-multiselectable>
          {allTags.length === 0 ? (
            <p className="tag-selector-empty">Noch keine Tags vorhanden.</p>
          ) : (
            allTags.map(tag => {
              const isSelected = selectedIds.includes(tag.id)
              return (
                <button
                  key={tag.id}
                  className={`tag-selector-option${isSelected ? ' selected' : ''}`}
                  onClick={() => toggle(tag.id)}
                  role="option"
                  aria-selected={isSelected}
                  type="button"
                >
                  {/* Farbpunkt des Tags */}
                  <span className="tag-selector-dot" style={{ background: tag.color }} />
                  <span className="tag-selector-option-name">{tag.name}</span>
                  {/* Häkchen zeigt aktuelle Auswahl */}
                  {isSelected && <span className="tag-selector-check" aria-hidden>✓</span>}
                </button>
              )
            })
          )}

          {/* Link zum TagManagementModal */}
          <button
            className="tag-selector-manage-link"
            onClick={handleManageTags}
            type="button"
          >
            Tags verwalten...
          </button>
        </div>
      )}
    </div>
  )
}

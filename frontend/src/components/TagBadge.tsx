// TagBadge — kleines Farbpill-Element zur Anzeige eines Tags.
// Wird überall verwendet: Abo-Karten, Detailansicht, TagSelector.
// onRemove: wenn gesetzt, erscheint ein × zum Entfernen (nur im TagSelector).

import type { TagRead } from '../types/tag'
import './TagBadge.css'

interface TagBadgeProps {
  tag: TagRead
  onRemove?: (e: React.MouseEvent) => void
}

export default function TagBadge({ tag, onRemove }: TagBadgeProps) {
  return (
    <span className="tag-badge">
      {/* Farbiger Punkt — Farbe kommt direkt aus dem Tag-Objekt */}
      <span className="tag-badge-dot" style={{ background: tag.color }} />
      <span className="tag-badge-name">{tag.name}</span>

      {/* × nur anzeigen wenn onRemove gesetzt (z.B. im TagSelector) */}
      {onRemove && (
        <button
          className="tag-badge-remove"
          onClick={onRemove}
          aria-label={`Tag "${tag.name}" entfernen`}
          type="button"
        >
          ×
        </button>
      )}
    </span>
  )
}

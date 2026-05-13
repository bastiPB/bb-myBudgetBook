// Typen und Konstanten für das Tag-Feature (v0.2.7).
// Spiegelt app/schemas/subscription_tag.py und die Farbpalette exakt wider.

export interface TagRead {
  id: string
  name: string
  color: string  // Hex-Farbe aus der Palette, z.B. "#6366f1"
}

export interface TagCreate {
  name: string
  color: string
}

export interface TagUpdate {
  name?: string
  color?: string
}

export interface TagAssignRequest {
  tag_ids: string[]
}

// Vordefinierte Farbpalette — exakt dieselbe Liste wie ALLOWED_TAG_COLORS im Backend.
// Reihenfolge ist bewusst so gewählt: warme Farben rechts, kühle links.
export const TAG_COLORS: { hex: string; label: string }[] = [
  { hex: '#6366f1', label: 'Indigo' },
  { hex: '#8b5cf6', label: 'Violett' },
  { hex: '#a855f7', label: 'Lila' },
  { hex: '#ec4899', label: 'Pink' },
  { hex: '#ef4444', label: 'Rot' },
  { hex: '#f97316', label: 'Orange' },
  { hex: '#eab308', label: 'Gelb' },
  { hex: '#22c55e', label: 'Grün' },
  { hex: '#14b8a6', label: 'Teal' },
  { hex: '#06b6d4', label: 'Cyan' },
  { hex: '#3b82f6', label: 'Blau' },
  { hex: '#64748b', label: 'Slate' },
]

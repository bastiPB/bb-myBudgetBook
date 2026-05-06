// ConfirmModal.tsx — wiederverwendbares Bestätigungs-Modal.
//
// Typ a: Einfacher Dialog mit Bestätigen/Abbrechen.
//   <ConfirmModal title="Abo pausieren?" onConfirm={...} onCancel={...} />
//
// Typ b: Sicherheits-Modal für destruktive Aktionen (dangerous=true).
//   User muss den Namen des Abos eintippen, erst dann wird Bestätigen aktiv.
//   <ConfirmModal title="Abo kündigen" confirmText={sub.name} dangerous onConfirm={...} onCancel={...} />

import { useState } from 'react'
import './ConfirmModal.css'

interface ConfirmModalProps {
  title: string
  body?: string         // optionaler Erklärungstext unterhalb des Titels
  onConfirm: () => void
  onCancel: () => void
  confirmText?: string  // wenn gesetzt: User muss diesen Text eintippen (Typ b)
  dangerous?: boolean   // wenn true: Bestätigen-Button ist rot
}

export default function ConfirmModal({
  title,
  body,
  onConfirm,
  onCancel,
  confirmText,
  dangerous = false,
}: ConfirmModalProps) {
  // Eingabe-State für den Sicherheitstext (nur bei Typ b genutzt)
  const [inputValue, setInputValue] = useState('')

  // Bestätigen ist nur möglich wenn der Text übereinstimmt (oder kein Text nötig ist)
  const canConfirm = confirmText ? inputValue === confirmText : true

  return (
    // Klick auf den Hintergrund schließt das Modal (= Abbrechen)
    <div className="confirm-backdrop" onClick={onCancel}>
      {/* stopPropagation: Klick innerhalb des Modals schließt es nicht */}
      <div className="confirm-modal" role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}>
        <h2 className="confirm-title">{title}</h2>
        {body && <p className="confirm-body">{body}</p>}

        {/* Typ b: Eingabefeld für Sicherheitsbestätigung */}
        {confirmText && (
          <div className="confirm-input-block">
            <p className="confirm-input-hint">
              Zur Bestätigung bitte <strong>{confirmText}</strong> eintippen:
            </p>
            <input
              className="confirm-input"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              autoFocus
              autoComplete="off"
            />
          </div>
        )}

        <div className="confirm-actions">
          <button
            className={`confirm-btn-ok${dangerous ? ' confirm-btn-danger' : ''}`}
            onClick={onConfirm}
            disabled={!canConfirm}
          >
            Bestätigen
          </button>
          <button className="confirm-btn-cancel" onClick={onCancel}>
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  )
}

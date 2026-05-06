// InfoModal.tsx — Einfaches Info- oder Fehlermeldungs-Modal mit einem OK-Button.
//
// Nutzung: wenn eine Aktion fehlschlägt und der Fehler als Overlay angezeigt werden soll.
// Nutzt dieselben CSS-Klassen wie ConfirmModal — kein eigenes Stylesheet nötig.
import './ConfirmModal.css'

interface InfoModalProps {
  title: string
  body: string
  onClose: () => void
}

export default function InfoModal({ title, body, onClose }: InfoModalProps) {
  return (
    // Klick auf den Hintergrund schließt das Modal
    <div className="confirm-backdrop" onClick={onClose}>
      <div className="confirm-modal" role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}>
        <h2 className="confirm-title">{title}</h2>
        <p className="confirm-body">{body}</p>
        <div className="confirm-actions">
          <button className="confirm-btn-ok" onClick={onClose}>
            OK
          </button>
        </div>
      </div>
    </div>
  )
}

// SubscriptionCreateModal.tsx — Modal zum Anlegen eines neuen Abos.
//
// Enthält den vollständigen Create-Flow: Logo, Pflichtfelder, Tags.
// Die Inline-Create-Card aus SubscriptionsPage wurde hierher migriert (v0.2.8).

import { useEffect, useRef, useState } from 'react'
import TagManagementModal from './TagManagementModal'
import TagSelector from './TagSelector'
import { createSubscription, uploadSubscriptionLogo } from '../api/subscriptions'
import { setSubscriptionTags } from '../api/tags'
import type { BillingInterval, SubscriptionRead } from '../types/subscription'
import type { TagRead } from '../types/tag'
import { INTERVAL_LABELS, parseAmount } from '../types/subscription'
import './SubscriptionCreateModal.css'

const INTERVALS: BillingInterval[] = ['monthly', 'quarterly', 'semiannual', 'yearly', 'biennial']
const EMPTY_FORM = { name: '', amount: '', started_on: '', interval: 'monthly' as BillingInterval }

// Unterscheidet in welcher Phase ein Fehler aufgetreten ist.
// 'create' = kein Abo entstanden → Retry erlaubt
// 'tags'   = Abo existiert, Tags fehlgeschlagen → Create sperren
// 'logo'   = Abo existiert, Logo fehlgeschlagen → Retry-Logo oder Schließen
type ErrorPhase = 'create' | 'tags' | 'logo'

interface SubscriptionCreateModalProps {
  allTags: TagRead[]
  onClose: () => void
  onCreated: (subscription: SubscriptionRead) => void
  onTagsChanged: () => Promise<void> | void
}

export default function SubscriptionCreateModal({
  allTags,
  onClose,
  onCreated,
  onTagsChanged,
}: SubscriptionCreateModalProps) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [tagIds, setTagIds] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorPhase, setErrorPhase] = useState<ErrorPhase | null>(null)
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null)
  // Bereits erstelltes Abo (nach Teil-Erfolg) — verhindert doppeltes Create
  const [createdSub, setCreatedSub] = useState<SubscriptionRead | null>(null)
  const [showTagModal, setShowTagModal] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Object-URL freigeben wenn sich die Vorschau ändert oder das Modal unmountet
  useEffect(() => {
    return () => {
      if (logoPreviewUrl) URL.revokeObjectURL(logoPreviewUrl)
    }
  }, [logoPreviewUrl])

  // Tag-Auswahl bereinigen wenn allTags sich ändert (z. B. nach Tag-Löschung)
  useEffect(() => {
    const validIds = new Set(allTags.map(t => t.id))
    setTagIds(prev => {
      const cleaned = prev.filter(id => validIds.has(id))
      return cleaned.length === prev.length ? prev : cleaned
    })
  }, [allTags])

  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    if (logoPreviewUrl) URL.revokeObjectURL(logoPreviewUrl)
    setLogoFile(file)
    setLogoPreviewUrl(file ? URL.createObjectURL(file) : null)
  }

  // Schließen: Falls ein Abo teilweise erstellt wurde, trotzdem in die Liste übernehmen
  function handleClose() {
    if (createdSub) onCreated(createdSub)
    onClose()
  }

  // TagManagementModal erwartet () => void — Promise-Rückgabewert wird ignoriert
  function handleTagsChangedInModal() {
    void onTagsChanged()
  }

  async function handleRetryLogo() {
    if (!createdSub || !logoFile) return
    setError(null)
    setLoading(true)
    try {
      const updated = await uploadSubscriptionLogo(createdSub.id, logoFile)
      onCreated(updated)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Logo-Upload fehlgeschlagen.')
      setErrorPhase('logo')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setErrorPhase(null)

    const amountNum = parseAmount(form.amount)
    if (isNaN(amountNum) || amountNum < 0) {
      setError('Bitte einen gültigen Betrag eingeben (z. B. 9,99).')
      return
    }

    setLoading(true)
    try {
      // Schritt 1: Abo anlegen
      let sub = await createSubscription({
        name: form.name,
        amount: amountNum,
        interval: form.interval,
        // started_on nur mitschicken wenn der User ein Datum eingetragen hat
        started_on: form.started_on || undefined,
      })

      // Schritt 2: Tags zuweisen (optional)
      if (tagIds.length > 0) {
        try {
          const assigned = await setSubscriptionTags(sub.id, { tag_ids: tagIds })
          sub = { ...sub, tags: assigned }
        } catch (err) {
          // Abo existiert bereits — kein zweites Create
          setCreatedSub(sub)
          setError(err instanceof Error ? err.message : 'Tag-Zuweisung fehlgeschlagen.')
          setErrorPhase('tags')
          return
        }
      }

      // Schritt 3: Logo hochladen (optional)
      if (logoFile) {
        try {
          sub = await uploadSubscriptionLogo(sub.id, logoFile)
        } catch (err) {
          // Abo existiert — Create sperren, Logo-Retry anbieten
          setCreatedSub(sub)
          setError(err instanceof Error ? err.message : 'Logo-Upload fehlgeschlagen.')
          setErrorPhase('logo')
          return
        }
      }

      onCreated(sub)
      onClose()
    } catch (err) {
      // Fehler im Create-Schritt: kein Abo entstanden, Retry erlaubt
      setError(err instanceof Error ? err.message : 'Fehler beim Anlegen.')
      setErrorPhase('create')
    } finally {
      setLoading(false)
    }
  }

  // Formular sperren sobald ein Abo bereits existiert (Teil-Erfolg)
  const formDisabled = loading || errorPhase === 'tags' || errorPhase === 'logo'

  return (
    <>
      {/* Backdrop übernimmt das Scrollen — Modal selbst hat kein overflow-y,
          damit das Tag-Dropdown nicht abgeschnitten wird */}
      <div className="create-modal-backdrop">
        <div className="create-modal">

          {/* ── Kopfzeile ── */}
          <div className="create-modal-header">
            <div>
              <h2 className="create-modal-title">Neues Abo anlegen</h2>
              <p className="create-modal-subtitle">Trag die wichtigsten Infos ein — das Wichtigste zuerst.</p>
            </div>
            <button
              type="button"
              className="create-modal-close"
              onClick={handleClose}
              aria-label="Schließen"
            >
              ✕
            </button>
          </div>

          <form onSubmit={handleSubmit}>

            {/* ── Sektion 1: Logo + Name ── */}
            <div className="create-modal-section">
              <div className="create-modal-identity">

                {/* Logo-Zone: Upload-Fläche oder Vorschau mit ×-Badge */}
                <div className="create-modal-logo-zone">
                  {logoPreviewUrl ? (
                    <>
                      {/* Vorschau — klickbar zum Wechseln */}
                      <button
                        type="button"
                        className="create-modal-logo-preview-btn"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={formDisabled}
                        title="Logo ändern"
                      >
                        <img src={logoPreviewUrl} alt="Logo-Vorschau" className="create-modal-logo-img" />
                      </button>
                      {/* × in der Ecke zum Entfernen */}
                      {!formDisabled && (
                        <button
                          type="button"
                          className="create-modal-logo-remove"
                          onClick={() => {
                            URL.revokeObjectURL(logoPreviewUrl)
                            setLogoFile(null)
                            setLogoPreviewUrl(null)
                            if (fileInputRef.current) fileInputRef.current.value = ''
                          }}
                          aria-label="Logo entfernen"
                        >
                          ×
                        </button>
                      )}
                    </>
                  ) : (
                    /* Upload-Fläche wenn noch kein Logo gewählt */
                    <button
                      type="button"
                      className="create-modal-logo-upload"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={formDisabled}
                      title="Logo auswählen"
                    >
                      <span className="create-modal-upload-icon">↑</span>
                      <span className="create-modal-upload-text">Logo</span>
                    </button>
                  )}
                </div>

                <div className="create-modal-identity-fields">
                  <label className="create-modal-label" htmlFor="cm-name">
                    Name deines Abos
                  </label>
                  <input
                    id="cm-name"
                    className="create-modal-input"
                    placeholder="z. B. Netflix, Spotify, GitHub …"
                    value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                    required
                    autoFocus
                    disabled={formDisabled}
                  />
                </div>
              </div>

              {/* Datei-Input — unsichtbar, wird per Klick auf die Logo-Zone ausgelöst */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="create-modal-file-input"
                onChange={handleLogoChange}
                disabled={formDisabled}
              />
            </div>

            {/* ── Sektion 2: Betrag, Intervall, Datum ── */}
            <div className="create-modal-section">
              <p className="create-modal-section-heading">Details zu deinem Abo</p>

              <div className="create-modal-two-col">
                <div className="create-modal-field">
                  <label className="create-modal-label" htmlFor="cm-amount">
                    Wie viel zahlst du?
                  </label>
                  {/* type="text" damit Komma als Dezimaltrennzeichen akzeptiert wird */}
                  <input
                    id="cm-amount"
                    className="create-modal-input"
                    placeholder="z. B. 9,99"
                    value={form.amount}
                    onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
                    required
                    disabled={formDisabled}
                  />
                </div>

                <div className="create-modal-field">
                  <label className="create-modal-label" htmlFor="cm-interval">
                    Abrechnungszeitraum
                  </label>
                  <select
                    id="cm-interval"
                    className="create-modal-select"
                    value={form.interval}
                    onChange={e => setForm(f => ({ ...f, interval: e.target.value as BillingInterval }))}
                    disabled={formDisabled}
                  >
                    {INTERVALS.map(iv => (
                      <option key={iv} value={iv}>{INTERVAL_LABELS[iv]}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="create-modal-field">
                <label className="create-modal-label" htmlFor="cm-date">
                  Seit wann läuft das Abo?{' '}
                  <span className="create-modal-optional">(optional — leer = heute)</span>
                </label>
                <input
                  id="cm-date"
                  className="create-modal-input create-modal-input-date"
                  type="date"
                  value={form.started_on}
                  onChange={e => setForm(f => ({ ...f, started_on: e.target.value }))}
                  disabled={formDisabled}
                />
              </div>
            </div>

            {/* ── Sektion 3: Tags ── */}
            <div className="create-modal-section create-modal-section-tags">
              <p className="create-modal-section-heading">
                Möchtest du Tags hinzufügen?{' '}
                <span className="create-modal-optional">(optional)</span>
              </p>
              <TagSelector
                allTags={allTags}
                selectedIds={tagIds}
                onChange={setTagIds}
                onManageTags={() => setShowTagModal(true)}
              />
            </div>

            {/* ── Fehleranzeige ── */}
            {error && <p className="create-modal-error">{error}</p>}

            {/* ── Aktions-Buttons ── */}
            <div className="create-modal-actions">
              {errorPhase === 'logo' ? (
                <>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={handleRetryLogo}
                    disabled={loading}
                  >
                    {loading ? 'Hochladen…' : 'Logo erneut versuchen'}
                  </button>
                  <button type="button" className="btn-outline" onClick={handleClose}>
                    Schließen
                  </button>
                </>
              ) : errorPhase === 'tags' ? (
                <button type="button" className="btn-outline" onClick={handleClose}>
                  Schließen
                </button>
              ) : (
                <>
                  <button type="submit" className="btn-primary" disabled={formDisabled}>
                    {loading ? 'Speichern…' : 'Abo anlegen'}
                  </button>
                  <button type="button" className="btn-outline" onClick={handleClose}>
                    Abbrechen
                  </button>
                </>
              )}
            </div>

          </form>
        </div>
      </div>

      {showTagModal && (
        <TagManagementModal
          onClose={() => setShowTagModal(false)}
          onTagsChanged={handleTagsChangedInModal}
        />
      )}
    </>
  )
}

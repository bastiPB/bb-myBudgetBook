# Design Guide — BB-myBudgetBook

> **Zweck dieses Dokuments:**
> Wer eine neue Seite oder ein neues Modul baut, findet hier alles was er braucht
> um konsistent mit dem Rest der App auszusehen — ohne etwas erfinden zu müssen.
>
> Architektur-Entscheidung dahinter: [ADR 0009](adr/0009-css-custom-properties-neutral-design-system.md)

---

## 1. Grundprinzipien

- **Keine Inline-Styles.** Styling gehört in CSS-Dateien, nicht in JSX-Attribute.
- **Keine hardcodierten Farben.** Immer CSS-Variablen verwenden (`var(--color-accent)` statt `#4a6fa5`).
- **Kein CSS-Framework.** Kein Tailwind, kein MUI, kein Bootstrap.
- **Neutral und ruhig.** Gedämpftes Blau als Akzentfarbe, keine Knallfarben.

---

## 2. Theme-System

Die App unterstützt Light und Dark Mode über ein `data-theme`-Attribut am `<html>`-Element.

```
data-theme="light"   → Standard
data-theme="dark"    → Dunkel
```

**Wie es funktioniert:**

1. `AppLayout.tsx` liest das gespeicherte Theme aus `localStorage` (`bb-theme`).
2. Bei Klick auf den Toggle wird `document.documentElement.setAttribute('data-theme', ...)` gesetzt.
3. CSS-Variablen in `AppLayout.css` reagieren automatisch auf `[data-theme="dark"]`.
4. Öffentliche Seiten (Login, Register) setzen das Theme selbst beim Laden:

```tsx
useEffect(() => {
  const savedTheme = localStorage.getItem('bb-theme') ?? 'light'
  document.documentElement.setAttribute('data-theme', savedTheme)
}, [])
```

**Neue öffentliche Seite?** Diesen `useEffect` oben einfügen — fertig.

---

## 3. CSS-Variablen

Alle Variablen sind in `frontend/src/components/AppLayout.css` unter `:root` definiert.
Dark-Mode-Werte stehen im `[data-theme="dark"]`-Block direkt darunter.

### Farben

| Variable | Light | Dark | Verwendung |
|---|---|---|---|
| `--color-bg` | `#f4f5f7` | `#12141a` | Seitenhintergrund |
| `--color-surface` | `#ffffff` | `#1c1f28` | Karten, Panels, Dropdown |
| `--color-sidebar` | `#f8f9fb` | `#181b24` | Sidebar-Hintergrund |
| `--color-border` | `#e2e5ea` | `#2c3044` | Rahmen, Trennlinien |
| `--color-text` | `#1c2029` | `#e2e5ec` | Haupttext |
| `--color-text-muted` | `#6b7585` | `#8f97aa` | Labels, Sekundärtext, Hinweise |
| `--color-accent` | `#4a6fa5` | `#6b9fd4` | Buttons, aktive Links, Fokus |
| `--color-accent-hover` | `#3a5988` | `#88b5e0` | Hover-Zustand von Accent |
| `--color-accent-light` | `#eef3fa` | `#1e2940` | Hintergrund bei Hover / Fokus-Ring |

### Maße

| Variable | Wert | Verwendung |
|---|---|---|
| `--header-height` | `56px` | Höhe des App-Headers |
| `--footer-height` | `36px` | Höhe des App-Footers |
| `--sidebar-width` | `220px` | Breite der Sidebar |

---

## 4. CSS-Klassen-Referenz

### 4.1 App-Shell (`AppLayout.css`)

Diese Klassen werden von `AppLayout.tsx` intern verwendet.
Normalerweise musst du sie nicht selbst setzen.

| Klasse | Beschreibung |
|---|---|
| `.app-shell` | Gesamt-Grid (Header / Body / Footer) |
| `.app-header` | Obere Leiste (sticky) |
| `.app-body` | Flex-Container: Sidebar + Main nebeneinander |
| `.app-sidebar` | Linke Navigationsleiste |
| `.app-main` | Hauptinhalt (scrollbar) |
| `.app-footer` | Untere Leiste |

### 4.2 Navigation (`AppLayout.css`)

| Klasse | Beschreibung |
|---|---|
| `.nav-link` | NavLink-Klasse in der Sidebar |
| `.nav-link.active` | Wird von react-router-dom **automatisch** gesetzt |
| `.nav-divider` | Horizontale Trennlinie (`<hr>`) in der Sidebar |
| `.nav-section-label` | Kleines Label über einer Gruppe (z. B. „Admin") |

### 4.3 Inhalts-Karten (`AppLayout.css`)

Das sind die Blöcke die im Hauptbereich der geschützten Seiten verwendet werden.

| Klasse | Beschreibung |
|---|---|
| `.page-title` | H1 oben im Hauptbereich |
| `.card` | Weiße Box mit Rahmen — Standardcontainer für Inhalte |
| `.card h2` | Kleines Label oben in der Karte (automatisch gestylt) |
| `.amount-large` | Große Zahl (z. B. Gesamtkosten) innerhalb einer `.card` |
| `.onboarding-card` | Karte mit Akzent-Rand — für Hinweise und Einstiegsscreen |
| `.upcoming-list` | `<ul>` für Fälligkeitslisten |
| `.upcoming-date` | Datum / Zusatzinfo rechts in einem Listeneintrag |
| `.pending-view` | Zentrierte Warte-Ansicht (für Nutzer ohne Rolle) |
| `.btn-primary` | Blauer Haupt-Button |

**Beispiel — neue Inhalts-Seite:**

```tsx
export default function MeineSeite() {
  return (
    <div>
      <h1 className="page-title">Mein Modul</h1>

      <div className="card">
        <h2>Abschnitt</h2>
        <p>Inhalt hier.</p>
      </div>

      <div className="card">
        <h2>Noch ein Abschnitt</h2>
        <button className="btn-primary">Aktion</button>
      </div>
    </div>
  )
}
```

### 4.4 Auth-Seiten (`LoginPage.css`)

Für öffentliche Seiten wie Login und Register.
`RegisterPage.css` importiert `LoginPage.css` per `@import` — kein doppelter Code.

| Klasse | Beschreibung |
|---|---|
| `.login-page` | Full-Height-Wrapper, zentriert |
| `.login-card` | Formular-Karte (max. 380px) |
| `.login-info-card` | Info-Screen-Karte (bereits eingeloggt, Erfolg etc.) |
| `.login-logo` | Logo-Bereich oben in der Karte |
| `.login-logo-text` | App-Name neben dem Logo |
| `.login-form` | Flex-Column-Wrapper für Formularfelder |
| `.form-field` | Label + Input als Block |
| `.login-error` | Fehlermeldung (rot, Light + Dark gestylt) |
| `.login-submit` | Submit-Button, volle Breite, Primärfarbe |
| `.login-btn-secondary` | Outline-Button (für Info-Screens) |
| `.login-footer-text` | Kleiner Text unter dem Formular |
| `.login-link` | Link-artiger Button (kein Rahmen, Akzentfarbe) |

---

## 5. Logo

Das Logo ist ein kleines SVG — ein abgerundetes Quadrat in der Akzentfarbe mit weißem „BB"-Text.
Aktuell in `AppLayout.tsx` und `LoginPage.tsx` als lokale Funktion `LogoIcon()` inline.

```tsx
function LogoIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <rect width="26" height="26" rx="6" fill="var(--color-accent)" />
      <text x="3" y="19" fontFamily="system-ui, sans-serif" fontWeight="800" fontSize="14" fill="white">
        BB
      </text>
    </svg>
  )
}
```

> **TODO:** Sobald eine dritte Stelle das Logo braucht → in `src/components/Logo.tsx` auslagern.

---

## 6. Neue Seite oder Modul anlegen — Checkliste

**Geschützte Seite (mit App-Shell):**

- [ ] Neue Datei in `src/pages/MeineSeite.tsx`
- [ ] Route in `App.tsx` eintragen: `<Route path="/mein-pfad" element={<Layout><MeineSeite /></Layout>} />`
- [ ] Kein eigenes `<header>` oder `<nav>` — das macht AppLayout
- [ ] Kein eigener Logout-Button — liegt im User-Menü im Header
- [ ] Styling: `.page-title` für den H1, `.card` für Inhaltsblöcke, `.btn-primary` für Buttons
- [ ] Farben nur über CSS-Variablen

**Öffentliche Seite (ohne App-Shell, z. B. weitere Auth-Seiten):**

- [ ] Neue Datei in `src/pages/MeineSeite.tsx`
- [ ] `import './RegisterPage.css'` (oder eigene CSS-Datei mit `@import './LoginPage.css'`)
- [ ] `useEffect` für Theme-Initialisierung (siehe Abschnitt 2)
- [ ] `.login-page` als äußersten Wrapper
- [ ] `.login-card` oder `.login-info-card` für den Inhalt

**Neues Modul:**

- [ ] Eintrag in `src/modules/registry.ts` (key, label, navLabel, route)
- [ ] Backend-Freigabe in Admin-Einstellungen (app_settings.modules)
- [ ] Seite nach obigem Schema aufbauen
- [ ] Sidebar-Link erscheint automatisch über `activeModules`

---

## 7. Do / Don't

| ✅ Do | ❌ Don't |
|---|---|
| `color: var(--color-text)` | `color: #1c2029` |
| `background: var(--color-surface)` | `background: #ffffff` |
| `className="btn-primary"` | `style={{ background: '#4a6fa5' }}` |
| Neue Karte mit `className="card"` | Inline-`style`-Objekte für Abstände und Farben |
| Dark-Mode-Test nach jeder Änderung | Nur im Light Mode testen |
| Variablen in `AppLayout.css` für neue Tokens | Neue Farben irgendwo im Komponent-CSS definieren |

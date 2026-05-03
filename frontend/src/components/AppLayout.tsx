// AppLayout.tsx — Wiederverwendbare UI-Shell für alle geschützten Seiten.
//
// Struktur:
//   ┌─────────────────────────────────────┐
//   │  HEADER  (Logo | Theme-Toggle User) │
//   ├──────────┬──────────────────────────┤
//   │ SIDEBAR  │  HAUPTINHALT (children)  │
//   ├──────────┴──────────────────────────┤
//   │  FOOTER  (Versionsnummer)           │
//   └─────────────────────────────────────┘
//
// Verwendung in App.tsx:
//   <Layout><MeineSeite /></Layout>
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import { logoutUser } from '../api/auth'
import { useAuth } from '../context/useAuth'
import { useModules } from '../context/useModules'
import './AppLayout.css'

// Versionsnummer die im Footer angezeigt wird.
// Manuell gepflegt — kann später aus package.json importiert werden.
const APP_VERSION = 'v0.2.1'

// Mondsichel — Feather Icons "moon"-Pfad, bewährt und sauber
function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}

// Sonne mit 8 Strahlen — Feather Icons "sun"-Pfad
function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1"  x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22"   x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1"  y1="12" x2="3"  y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78"  x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64"  x2="19.78" y2="4.22" />
    </svg>
  )
}

// SVG-Logo — einfaches "BB"-Symbol in einem abgerundeten Quadrat
function LogoIcon() {
  return (
    <svg
      width="26"
      height="26"
      viewBox="0 0 26 26"
      fill="none"
      aria-hidden="true"
    >
      {/* Hintergrund-Rechteck mit abgerundeten Ecken */}
      <rect width="26" height="26" rx="6" fill="var(--color-accent)" />
      {/* "BB"-Text in Weiß */}
      <text
        x="3"
        y="19"
        fontFamily="system-ui, sans-serif"
        fontWeight="800"
        fontSize="14"
        fill="white"
      >
        BB
      </text>
    </svg>
  )
}

interface AppLayoutProps {
  /** Der Seiteninhalt der im Hauptbereich angezeigt wird */
  children: React.ReactNode
}

export default function AppLayout({ children }: AppLayoutProps) {
  const { user, setUser } = useAuth()
  const { activeModules } = useModules()
  const navigate = useNavigate()

  // Theme aus localStorage laden — Standard: 'light'
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('bb-theme') as 'light' | 'dark') ?? 'light'
  })

  // User-Dropdown ist zu (false) oder offen (true)
  const [menuOpen, setMenuOpen] = useState(false)

  // Referenz auf das Dropdown-Element, damit Klicks außerhalb erkannt werden
  const menuRef = useRef<HTMLDivElement>(null)

  // Wenn das Theme wechselt: data-theme-Attribut am <html>-Element setzen.
  // CSS-Variablen reagieren automatisch darauf — kein weiteres JS nötig.
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('bb-theme', theme)
  }, [theme])

  // Klick außerhalb des Dropdown-Bereichs → Menü schließen
  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    // Event-Listener nur anhängen wenn Menü offen ist
    if (menuOpen) {
      document.addEventListener('mousedown', handleOutsideClick)
    }
    // Aufräumen wenn Menü geschlossen wird oder Komponente entfernt wird
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [menuOpen])

  // Abmelden: Backend informieren, Session lokal löschen, zur Login-Seite
  async function handleLogout() {
    await logoutUser()
    // Flag setzen damit LoginPage die "Erfolgreich abgemeldet"-Meldung zeigt
    sessionStorage.setItem('justLoggedOut', 'true')
    setUser(null)
    navigate('/login')
  }

  // Initialen für den runden User-Button (erste 2 Zeichen der E-Mail, groß)
  const initials = (user?.email ?? 'U').slice(0, 2).toUpperCase()

  return (
    <div className="app-shell">

      {/* ────── HEADER ────── */}
      <header className="app-header">

        {/* Linke Seite: Logo + App-Name — Link statt NavLink, da kein Active-Stil gebraucht wird */}
        <Link to="/dashboard" className="app-logo">
          <LogoIcon />
          <span>my-BB</span>
        </Link>

        {/* Rechte Seite: Theme-Schalter + User-Menü */}
        <div className="header-right">

          {/* Hell/Dunkel-Schalter — Sliding Toggle */}
          <button
            className={`theme-toggle-switch ${theme === 'dark' ? 'is-dark' : 'is-light'}`}
            onClick={() => setTheme(t => t === 'light' ? 'dark' : 'light')}
            title={theme === 'light' ? 'Dark Mode aktivieren' : 'Light Mode aktivieren'}
            aria-label="Theme wechseln"
          >
            {/* Gleitender Daumen */}
            <span className="toggle-thumb" />
            {/* Icon — immer auf der Seite gegenüber dem Daumen */}
            <span className="toggle-icon">
              {theme === 'dark' ? <MoonIcon /> : <SunIcon />}
            </span>
          </button>

          {/* User-Button mit Dropdown */}
          <div className="user-menu-wrapper" ref={menuRef}>
            <button
              className="user-btn"
              onClick={() => setMenuOpen(o => !o)}
              aria-label="Benutzermenü öffnen"
              aria-expanded={menuOpen}
            >
              {initials}
            </button>

            {/* Dropdown — nur sichtbar wenn menuOpen === true */}
            {menuOpen && (
              <div className="user-menu-dropdown" role="menu">

                {/* E-Mail des eingeloggten Nutzers — nur zur Info */}
                <div className="user-menu-email">{user?.email}</div>

                {/* Link zu den Profil-Einstellungen */}
                <Link
                  to="/profile/settings"
                  className="user-menu-item"
                  onClick={() => setMenuOpen(false)}
                >
                  Einstellungen
                </Link>

                {/* Passwort ändern — Ziel ist vorerst dieselbe Seite (kommt in späterem Release) */}
                <Link
                  to="/profile/settings"
                  className="user-menu-item"
                  onClick={() => setMenuOpen(false)}
                >
                  Passwort ändern
                </Link>

                {/* Hilfe — Platzhalter, wird in späterem Release verlinkt */}
                <button
                  className="user-menu-item"
                  onClick={() => setMenuOpen(false)}
                >
                  Hilfe
                </button>

                {/* Trennlinie vor dem Abmelden-Eintrag */}
                <hr className="user-menu-divider" />

                <button className="user-menu-item" onClick={handleLogout}>
                  Abmelden
                </button>

              </div>
            )}
          </div>
        </div>
      </header>

      {/* ────── APP-BODY: Sidebar + Hauptinhalt ────── */}
      <div className="app-body">

        {/* ────── SIDEBAR ────── */}
        <nav className="app-sidebar" aria-label="Hauptnavigation">

          {/* Dashboard-Link — immer sichtbar für eingeloggte Nutzer */}
          <NavLink to="/dashboard" className="nav-link">
            Dashboard
          </NavLink>

          {/* Modul-Links — nur aktive Module werden hier angezeigt (ADR 0008) */}
          {activeModules.map(module => (
            <NavLink
              key={module.key}
              to={module.route}
              className="nav-link"
            >
              {module.navLabel}
            </NavLink>
          ))}

          {/* Admin-Bereich — nur für Nutzer mit der Rolle "admin" sichtbar */}
          {user?.role === 'admin' && (
            <>
              {/* Trennlinie zwischen normalen und Admin-Links */}
              <hr className="nav-divider" />
              <span className="nav-section-label">Admin</span>

              <NavLink to="/admin" className="nav-link">
                Benutzerverwaltung
              </NavLink>
              <NavLink to="/settings" className="nav-link">
                Systemeinstellungen
              </NavLink>
            </>
          )}
        </nav>

        {/* ────── HAUPTINHALT ────── */}
        {/* Hier wird die jeweilige Seite (children) eingebettet */}
        <main className="app-main">
          {children}
        </main>

      </div>

      {/* ────── FOOTER ────── */}
      <footer className="app-footer">
        <span>{APP_VERSION}</span>
      </footer>

    </div>
  )
}

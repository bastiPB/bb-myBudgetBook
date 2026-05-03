# ADR 0009: CSS Custom Properties und neutrales Design-System ohne Framework

## Status
Accepted

## Kontext

Mit v0.2.1 wurde eine gemeinsame UI-Shell eingeführt (Header, Sidebar, Footer).
Damit stand die Entscheidung an: Wie stylen wir die App langfristig konsistent?

Drei Anforderungen standen im Vordergrund:

1. **Hell/Dunkel-Modus** — Nutzer sollen zwischen Light und Dark Mode wechseln können,
   Präferenz wird gespeichert und gilt appweit (auch auf öffentlichen Seiten wie Login).
2. **Konsistenz** — Neue Module, Seiten und Komponenten sollen ohne großen Aufwand
   zum bestehenden Look passen.
3. **Wartbarkeit für Anfänger** — Der Projekt-Owner ist kein erfahrener Frontend-Entwickler.
   Das Styling-System muss verständlich und gut dokumentiert sein.

## Entscheidung

**CSS Custom Properties (CSS-Variablen) als zentrale Styling-Schicht.**
**Kein CSS-Framework** (kein Tailwind, kein MUI, kein Bootstrap).
**Neutrales Farbschema** — gedämpftes Blau als Akzent, keine Knallfarben.

Theme-Wechsel über `data-theme`-Attribut am `<html>`-Element.
Alle Farbwerte ausschließlich über Variablen — niemals hardcodiert.

Sämtliche globalen Variablen und Layout-Klassen leben in `AppLayout.css`.
Auth-Seiten (Login, Register) teilen sich `LoginPage.css`.

## Alternativen

### Tailwind CSS
- Utility-First: Styling direkt im JSX (`className="flex items-center gap-2 text-sm"`)
- Sehr beliebt, gutes Ökosystem
- **Verworfen:** Hohe Lernkurve für Anfänger. Unleserliche Klassenketten im JSX.
  Dark Mode über Konfiguration statt einfacher CSS-Variablen.
  Bindet das Projekt stark an Tailwind-Konzepte.

### Material UI (MUI)
- Fertige React-Komponenten mit eigenem Design-System
- **Verworfen:** Zu viel Overhead, eigenwilliges Theming-System (Theme-Provider, sx-Prop).
  Schwer zu überschreiben. Fügt eine große Abhängigkeit hinzu.

### Inline-Styles überall (wie v0.1)
- Kein separates CSS nötig
- **Verworfen:** Kein Dark Mode ohne massiven JS-Aufwand. Kein einheitliches Farbsystem.
  Code wird schnell unlesbar (style-Objekte im JSX). Nicht wartbar.

### CSS Modules (je Komponente)
- Lokale Scoping — keine Namenskonflikte
- **Verworfen (vorerst):** Für ein Projekt dieser Größe ist globales Scoping mit klaren
  Namenskonventionen ausreichend. CSS Modules können später ergänzt werden.

## Konsequenzen

**Positiv:**
- Theme-Wechsel kostet 0 JS — nur ein `setAttribute` und CSS erledigt den Rest
- Neue Seiten und Module müssen nur die bestehenden Klassen nutzen — fertig
- Ein Blick in `AppLayout.css` oder den Design Guide erklärt das gesamte System
- Keine Build-Zeit-Abhängigkeit (kein PostCSS, kein Tailwind-JIT nötig)
- Voll kompatibel mit dem bestehenden Vite-Setup

**Negativ / Risiken:**
- Globaler CSS-Scope: bei wachsender Codebasis können Klassennamen kollidieren
  → Mitigiert durch klare Präfix-Konventionen (`.nav-`, `.login-`, `.card-` usw.)
- Kein automatisches Tree-Shaking für ungenutztes CSS
- Auth-Seiten importieren `LoginPage.css` — TODO: in `auth.css` umbenennen

**Offene Punkte:**
- `LoginPage.css` → `auth.css` umbenennen wenn weitere Auth-Seiten hinzukommen
- `LogoIcon`-Komponente ist in AppLayout.tsx und LoginPage.tsx dupliziert
  → in eigene `Logo.tsx` auslagern sobald eine dritte Stelle entsteht

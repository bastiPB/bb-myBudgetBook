# ADR 0008: Introduce two-tier module visibility model

## Status
Accepted

## Kontext
Das Modul-System (v0.2.0) stellt die Frage: Wer entscheidet, welche Module ein User
sieht und nutzen kann?

Zwei berechtigte Interessen stehen sich gegenüber:
- Der **Admin** will kontrollieren, welche Module im System überhaupt angeboten werden —
  z.B. um halbfertige Module zurückzuhalten oder instanzspezifische Entscheidungen zu treffen.
- Der **User** will selbst bestimmen, was in seinem Dashboard erscheint —
  nicht jeder braucht jeden Baustein.

Die Speicherung der Konfiguration (JSONB) ist eine separate Entscheidung — siehe ADR 0007.

### Abgrenzung zu ADR 0005
ADR 0005 hält fest, dass Rollen künftig Domänenkontexten (Spaces) zugeordnet werden können.
**Dieses ADR ist davon unabhängig:** Modul-Sichtbarkeit ist in v0.2.0 **user-global** —
es gibt keine Verschränkung mit einem Kontext-Modell.
Die Frage "Darf ein User Modul X in Kontext A sehen, aber nicht in Kontext B?" ist
explizit auf v0.2.x+ verschoben.
Wenn das Kontext-Modell (ADR 0005) eingeführt wird, wird dieses ADR superseded.

Kurz-Merkhilfe:
- ADR 0005 = "Später können Spaces/Kontexte kommen."
- ADR 0008 = "Heute (v0.2.0) rechnen wir noch ohne Spaces, nur global pro User."

Beispiel:
- Heute (v0.2.0): Urlaubskasse ist für User U entweder an oder aus (global).
- Später (mit Spaces): Urlaubskasse kann für denselben User U in Kontext A an,
  in Kontext B aber aus sein.

### Verstaendnishilfe (fuer das "in 6 Monaten ich")

Warum ist das kein Widerspruch zwischen ADR 0005 und ADR 0008?

- ADR 0005 beantwortet die Frage: "Welche Sicherheits- und Rollenarchitektur darf spaeter
  wachsen?" -> Antwort: mit Kontexten/Spaces erweiterbar.
- ADR 0008 beantwortet die Frage: "Wie berechnen wir Modul-Sichtbarkeit jetzt in v0.2.0?"
  -> Antwort: global pro User, ohne Kontexte.

Das ist bewusst ein Zwei-Phasen-Modell:
- Phase 1 (jetzt): einfache, robuste globale Logik.
- Phase 2 (spaeter): gleiche Idee, aber pro Kontext aufgeloest.

Kurz gesagt:
- ADR 0005 ist die Zukunftsschiene.
- ADR 0008 ist die aktuelle Betriebsregel.

#### Entscheidungs-Tabelle (v0.2.0)

| Admin-Freigabe (`app_settings.modules[key]`) | User-Aktivierung (`user_settings.modules[key]`) | Ergebnis |
|---|---|---|
| false | false | Modul unsichtbar |
| false | true  | Modul unsichtbar (Admin sticht) |
| true  | false | Modul unsichtbar (User will es nicht) |
| true  | true  | Modul sichtbar und nutzbar |

Merksatz: Admin ist Gatekeeper, User ist Opt-in.

#### Mini-Entscheidungsbaum

1. Ist das Modul vom Admin freigegeben?
   - Nein -> sofort unsichtbar.
   - Ja -> weiter zu Schritt 2.
2. Hat der User das Modul fuer sich aktiviert?
   - Nein -> unsichtbar.
   - Ja -> sichtbar.

#### Was aendert sich spaeter mit Spaces?

Heute (v0.2.0):
- Sichtbarkeit ist global pro User.

Spaeter (mit Kontextmodell):
- Sichtbarkeit wird pro Kontext berechnet.
- Die Logik bleibt gleich (Admin-Gate AND User-Opt-in), aber mit Kontextparameter.

Von:
`visible(module, user) = admin_global(module) AND user_global(user, module)`

Zu:
`visible(module, user, context) = admin_in_context(context, module) AND user_in_context(user, context, module)`

Das ist der Grund fuer "superseded":
- Nicht weil ADR 0008 falsch ist,
- sondern weil die spaetere Regel eine strengere, kontextfaehige Version derselben Idee ist.

#### Praktische Folgen fuer Implementierung in v0.2.0

- Keine Kontexte in API-Pfaden noetig (`/settings`, `/profile/settings` reichen).
- Keine Kontext-ID in Frontend-States noetig.
- Keine Matrix-Tests pro Kontext noetig.

Damit bleibt v0.2.0 bewusst klein, testbar und release-faehig.

---

## Entscheidung

Modul-Sichtbarkeit wird durch zwei unabhängige Stufen gesteuert, die **beide** erfüllt
sein müssen:

```
Stufe 1 — Admin (app_settings.modules)
  "Ist dieses Modul im System generell verfügbar?"
  Nur wenn true: erscheint das Modul überhaupt in der User-Auswahl.

           ↓  nur freigegebene Module gelangen in Stufe 2

Stufe 2 — User (user_settings.modules)
  "Will ich dieses Modul in meinem Dashboard?"
  Nur wenn true: erscheint das Modul in Navigation und Routing.
```

**Ein Modul ist aktiv genau dann, wenn:**
`app_settings.modules[key] === true` **AND** `user_settings.modules[key] === true`

### Verhalten bei Admin-Deaktivierung

Deaktiviert der Admin ein Modul, verschwindet es **sofort** bei allen Usern —
unabhängig von deren persönlicher Einstellung.
Die User-Einstellung (`user_settings.modules[key]`) bleibt in der DB erhalten und
wird reaktiviert, sobald der Admin das Modul erneut freigibt.
Der User verliert keine Daten und muss nichts neu einstellen.

### Backend-Validierung

Ein User darf kein Modul aktivieren das Admin-seitig gesperrt ist.
`PATCH /profile/settings` mit einem gesperrten Modul → HTTP 400.
Validiert gegen `app_settings.modules` zum Zeitpunkt des Requests.

### Frontend-Umsetzung

Die Logik lebt im `ModulesContext` (drei Dateien nach react-refresh-Regel, ADR 0006):

```
activeModules = MODULE_REGISTRY
  .filter(m => app_settings.modules[m.key] === true)   // Stufe 1
  .filter(m => user_settings.modules[m.key] === true)   // Stufe 2
```

Aus `activeModules` werden **automatisch** React-Router-Routen und Navigationseinträge
generiert. Inaktive Module sind weder im Menü sichtbar noch über die URL erreichbar.

### Onboarding-Konsequenz

Ein neuer User hat `user_settings.modules = {}` (leer).
→ `activeModules` ist leer → Dashboard zeigt Onboarding-Card.
Die Card verschwindet automatisch sobald der User mindestens ein Modul aktiviert.

---

## Alternativen

### Alternative A — Nur Admin entscheidet (keine User-Auswahl)
- Pro: einfacher, kein Onboarding-Flow nötig
- Contra: Admin muss für jeden User konfigurieren; User hat keine Kontrolle über sein
  Dashboard — widerspricht dem Selfhosted-Gedanken (persönliche Anpassung)

### Alternative B — Nur User entscheidet (kein Admin-Gate)
- Pro: maximale User-Autonomie
- Contra: Admin kann halbfertige oder instanzspezifisch unerwünschte Module nicht
  zurückhalten; fehlende Kontrollebene für Multi-User-Betrieb

### Alternative C — Rollen-basierte Sichtbarkeit (z.B. `editor` sieht mehr als `viewer`)
- Pro: passt zum RBAC-Modell aus ADR 0005
- Contra: Module sind keine Berechtigungsgrenzen sondern Funktions-Bausteine;
  Rollen und Modul-Präferenzen sind orthogonale Konzepte — Vermischung erhöht Komplexität
  ohne Mehrwert für v0.2.0

---

## Konsequenzen

**Pro:**
- Klare Verantwortungstrennung: Admin = systemweite Freigabe, User = persönliche Auswahl
- Admin-Sperrung wirkt sofort, ohne User-Daten zu zerstören (reversibel)
- Onboarding-Zustand ergibt sich automatisch aus leerem `user_settings.modules`
- Navigation und Routen sind immer konsistent mit dem tatsächlichen Aktivierungszustand

**Contra / Risiken:**
- Zwei API-Calls beim App-Start nötig (`GET /settings` + `GET /profile/settings`);
  können aber parallel gefeuert werden
- Ein Admin der sein eigenes Profil einrichtet, hat zwei getrennte UIs
  (`/settings` für Systemverwaltung, `/profile/settings` für persönliche Module) —
  das ist gewollt (Separation), aber erklärungsbedürftig

**Offene Punkte (v0.2.x+):**
- Wenn Spaces/Kontexte eingeführt werden (ADR 0005), muss Stufe 1 pro Kontext
  auflösbar sein → dieses ADR wird dann superseded
- GIN-Index auf `app_settings.modules` und `user_settings.modules` bei hoher
  Query-Last ergänzen (für v0.2.0 nicht nötig)

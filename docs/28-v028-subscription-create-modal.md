---
doc: feature-plan
release: v0.2.8
status: released
---

# v0.2.8 - Subscription-Erstellung im Modal

Erstellt: 2026-05-15  
Abgeschlossen: 2026-05-15  
Status: Umgesetzt

---

## 1. Ziel

Das Anlegen einer Subscription soll nicht mehr inline in der Übersichtsseite passieren.
Stattdessen öffnet der Button "+ Neues Abo" ein kompaktes Modal, in dem alle wichtigen
Angaben fokussiert erfasst werden können.

Die bestehende Funktionalität bleibt erhalten und wird um einen direkten Logo-Upload beim
Erstellen ergänzt.

---

## 2. Problem

Aktuell erscheint das Formular zum Anlegen eines neuen Abos inline zwischen Seitenheader und
Liste. Das hat mehrere Nachteile:

- Die Übersicht springt optisch nach unten.
- Der Erstellprozess wirkt weniger fokussiert.
- Die Seite mischt Listenansicht und Formularzustand zu stark.
- Ein Abo ohne Logo wirkt nach dem Erstellen unfertiger, weil der Upload erst auf der Detailseite möglich ist.

---

## 3. Fachliche Entscheidungen

| Thema | Entscheidung | Begründung |
|---|---|---|
| Darstellung | Kompaktes Modal statt Inline-Formular | Fokus auf genau eine Aufgabe: neues Abo anlegen |
| Schließen per Overlay | Nein | Verhindert versehentlichen Verlust eingegebener Daten |
| Schließen | Nur über "Abbrechen" oder X-Button | Bewusste Nutzeraktion |
| Formularumfang | Kompakt | Es sind nur wenige Pflichtangaben nötig |
| Tags | Tags auswählen und "Tags verwalten" im Modal erlauben | Der Create-Flow bleibt vollständig |
| Logo | Logo direkt im Modal auswählbar | Professioneller erster Eindruck, weniger Nacharbeit |
| Abschlussdatum leer | Frontend sendet `started_on` nicht mit | Backend setzt dann `date.today()` |
| Backend-Änderung | Keine geplant | Bestehende Endpunkte reichen aus |

---

## 4. MVP-Scope

### Enthalten

- Button "+ Neues Abo" öffnet ein Modal.
- Das bisherige Inline-Erstellformular wird entfernt.
- Modal enthält:
  - Logo-Auswahl mit Vorschau oder Initialen-Fallback
  - Name
  - Betrag
  - Abschlussdatum optional
  - Intervall
  - Tag-Auswahl
  - Einstieg in "Tags verwalten"
- Leeres Abschlussdatum bedeutet: kein `started_on` im Request, Backend setzt heute.
- Klick auf den Overlay-Hintergrund schließt das Modal nicht.
- `Abbrechen` und X schließen das Modal.
- Während des Speicherns sind Eingaben und Buttons deaktiviert.
- Fehler werden im Modal angezeigt.
- Nach erfolgreichem Speichern erscheint das neue Abo in der Liste.

### Nicht enthalten

- Mehrstufiger Wizard.
- Duplikat-Erkennung bei ähnlichen Abo-Namen.
- Drag-and-drop Upload.
- Bildzuschnitt oder Bildbearbeitung.
- Neuer Backend-Endpunkt für Multipart-Create.
- Grundlegender Modal-System-Refactor.

---

## 5. Technischer Ablauf

Der vorhandene Logo-Upload braucht eine bereits existierende Subscription-ID:

```text
POST /subscriptions/{id}/logo
```

Deshalb speichert das Modal in mehreren Schritten:

1. Subscription mit `POST /subscriptions` anlegen.
2. Falls Tags ausgewählt wurden: Tags mit `PUT /subscriptions/{id}/tags` setzen.
3. Falls ein Logo ausgewählt wurde: Logo mit `POST /subscriptions/{id}/logo` hochladen.
4. Lokalen Listen-State mit der finalen Subscription aktualisieren.
5. Modal schließen und Formularzustand zurücksetzen.

Wichtig: Schritt 1 ist der fachlich entscheidende Create-Schritt. Tags und Logo sind nachgelagerte
Ergänzungen. Fehler nach Schritt 1 dürfen nicht dazu führen, dass der Nutzer durch erneutes Speichern
versehentlich ein zweites Abo anlegt.

---

## 6. Fehlerfälle

### 6.1 Create schlägt fehl

- Modal bleibt offen.
- Fehlermeldung wird im Formular angezeigt.
- Kein Abo wurde angelegt.
- Nutzer kann Daten korrigieren und erneut speichern.

### 6.2 Tag-Zuweisung schlägt nach erfolgreichem Create fehl

- Abo existiert bereits.
- Modal zeigt einen spezifischen Fehler:
  "Abo wurde erstellt, aber die Tags konnten nicht gespeichert werden."
- Nutzer kann schließen; das Abo bleibt in der Liste.
- Optional für später: erneuter Tag-Speichern-Versuch im Modal.

### 6.3 Logo-Upload schlägt nach erfolgreichem Create fehl

- Abo existiert bereits.
- Modal zeigt einen spezifischen Fehler:
  "Abo wurde erstellt, aber das Logo konnte nicht hochgeladen werden."
- Nutzer bekommt zwei Aktionen:
  - "Logo erneut versuchen"
  - "Schließen"
- Beim Schließen erscheint das Abo ohne Logo in der Liste.

---

## 7. Betroffene Dateien

### Frontend

```text
frontend/src/pages/SubscriptionsPage.tsx
frontend/src/pages/SubscriptionsPage.css
frontend/src/components/SubscriptionCreateModal.tsx   # neu
frontend/src/components/SubscriptionCreateModal.css   # neu
```

### Dokumentation

```text
docs/28-v028-subscription-create-modal.md
CHANGELOG.md
```

Backend-Dateien sind für den MVP nicht betroffen.

---

## 8. Komponenten-Verantwortung

### `SubscriptionsPage.tsx`

- Lädt Abos und Tags.
- Öffnet und schließt das Create-Modal.
- Übergibt `allTags`, `onTagsChanged` und `onCreated`.
- Aktualisiert die Liste, wenn das Modal ein neues Abo erfolgreich erstellt hat.
- Enthält kein Inline-Create-Formular mehr.

### `SubscriptionCreateModal.tsx`

- Hält den Formularzustand für den Create-Flow.
- Validiert den Betrag wie bisher über `parseAmount`.
- Sendet `started_on` nur, wenn ein Datum eingetragen wurde.
- Orchestriert Create, Tag-Zuweisung und Logo-Upload.
- Zeigt Ladezustände und Fehler an.
- Verhindert Schließen durch Overlay-Klick.

### `SubscriptionCreateModal.css`

- Eigenes Modal-Styling, angelehnt an vorhandene Modal-Muster.
- Responsive Breite und maximale Höhe.
- Scrollbarer Inhalt bei kleinen Viewports.
- Keine Inline-Styles für Layout, Farben oder Abstände.

---

## 9. UX-Details

- Modal-Titel: "Neues Abo anlegen"
- Primäraktion: "Speichern"
- Sekundäraktion: "Abbrechen"
- Logo-Bereich oben im Modal:
  - Wenn Datei gewählt: lokale Vorschau per `URL.createObjectURL`.
  - Wenn keine Datei gewählt: Initiale aus dem Namen, sonst neutrales Platzhalterfeld.
- Abschlussdatum-Label:
  - "Abgeschlossen am"
  - Hilfetext: "Leer lassen, wenn das Abo ab heute starten soll."
- Betrag akzeptiert Komma und Punkt als Dezimaltrennzeichen.
- Intervall nutzt die bestehenden Labels aus `INTERVAL_LABELS`.
- Tags nutzen den bestehenden `TagSelector`.

---

## 10. Akzeptanzkriterien

- Gegeben ich bin auf der Abo-Übersicht, wenn ich "+ Neues Abo" klicke, dann öffnet sich ein Modal.
- Gegeben das Modal ist offen, wenn ich auf den abgedunkelten Hintergrund klicke, dann bleibt das Modal geöffnet.
- Gegeben ich klicke "Abbrechen" oder den X-Button, dann wird das Modal geschlossen und kein Abo erstellt.
- Gegeben ich lasse "Abgeschlossen am" leer, wenn ich speichere, dann sendet das Frontend kein `started_on` und das Backend setzt das heutige Datum.
- Gegeben ich fülle gültige Daten aus, wenn ich speichere, dann wird das Abo erstellt und in der Liste angezeigt.
- Gegeben ich wähle Tags aus, wenn ich speichere, dann sind die Tags dem neuen Abo zugewiesen.
- Gegeben ich wähle ein gültiges Logo aus, wenn ich speichere, dann wird das Logo direkt nach dem Erstellen hochgeladen.
- Gegeben der Create-Request schlägt fehl, dann bleibt das Modal offen und zeigt den Fehler.
- Gegeben der Logo-Upload schlägt nach erfolgreichem Create fehl, dann wird kein zweites Abo erzeugt und der Nutzer kann schließen oder den Logo-Upload erneut versuchen.
- Gegeben ich nutze einen schmalen Bildschirm, dann bleibt das Modal bedienbar und Inhalte überlappen nicht.

---

## 11. Test-Checkliste

- Neues Abo ohne Abschlussdatum erstellen: Datum ist heute.
- Neues Abo mit Abschlussdatum in Vergangenheit erstellen.
- Neues Abo mit Abschlussdatum in Zukunft erstellen.
- Neues Abo mit Tags erstellen.
- Im Create-Modal Tags verwalten, neuen Tag erstellen, danach auswählen.
- Neues Abo mit Logo erstellen.
- Ungültigen Betrag eingeben.
- Ungültiges Logo hochladen, z. B. falscher Dateityp.
- Zu großes Logo hochladen.
- Overlay-Klick testen: Modal bleibt offen.
- `Abbrechen` und X testen.
- Light Mode prüfen.
- Dark Mode prüfen.
- Mobile Breite prüfen.

---

## 12. Build-Plan

### Chunk 1 - Modal-Komponente anlegen

Ziel: Der neue Create-Flow lebt in einer eigenen Komponente.

Aufgaben:

- `frontend/src/components/SubscriptionCreateModal.tsx` anlegen.
- `frontend/src/components/SubscriptionCreateModal.css` anlegen.
- Props definieren:
  - `allTags: TagRead[]`
  - `onClose: () => void`
  - `onCreated: (subscription: SubscriptionRead) => void`
  - `onTagsChanged: () => Promise<void> | void`
- Formular-State aus dem bisherigen Inline-Create-Formular übernehmen.
- Overlay-Klick darf das Modal nicht schließen.
- X-Button und "Abbrechen" schließen das Modal.

Akzeptanz für diesen Chunk:

- Modal rendert ohne API-Aktion.
- Eingaben lassen sich befüllen.
- Schließen funktioniert nur über X oder "Abbrechen".

### Chunk 2 - Bestehenden Create-Flow migrieren

Ziel: Die bisherige Inline-Erstellung wird funktional identisch ins Modal verschoben.

Aufgaben:

- `handleCreate` aus `SubscriptionsPage.tsx` in die Modal-Komponente übertragen.
- `parseAmount`, `INTERVAL_LABELS` und `INTERVALS` weiterverwenden.
- `started_on` nur senden, wenn ein Datum eingetragen wurde.
- `createSubscription` im Modal aufrufen.
- Erfolgreich erstellte Subscription über `onCreated` an die Seite zurückgeben.
- Inline-Create-Card aus `SubscriptionsPage.tsx` entfernen.
- Button "+ Neues Abo" öffnet nur noch das Modal.

Akzeptanz für diesen Chunk:

- Abo ohne Tags und ohne Logo kann über das Modal erstellt werden.
- Liste aktualisiert sich nach erfolgreichem Create.
- Leeres Abschlussdatum wird nicht gesendet.

### Chunk 3 - Tags integrieren

Ziel: Tags bleiben im Create-Flow vollständig nutzbar.

Aufgaben:

- Bestehenden `TagSelector` im Modal verwenden.
- `createTagIds` in der Modal-Komponente verwalten.
- Nach erfolgreichem Create optional `setSubscriptionTags` ausführen.
- `TagManagementModal` weiterhin aus dem Create-Modal heraus öffnen können.
- Nach Tag-Änderungen `onTagsChanged` aufrufen und lokale Auswahl bereinigen, falls nötig.

Akzeptanz für diesen Chunk:

- Abo kann mit ausgewählten Tags erstellt werden.
- "Tags verwalten" ist aus dem Modal erreichbar.
- Neu angelegte Tags können anschließend ausgewählt werden.

### Chunk 4 - Logo-Auswahl und Vorschau

Ziel: Nutzer kann vor dem Speichern ein Logo auswählen und sieht eine Vorschau.

Aufgaben:

- File-Input im Modal ergänzen.
- Erlaubte Typen im Input: `image/jpeg,image/png,image/webp`.
- Gewählte Datei im State halten.
- Vorschau über `URL.createObjectURL` anzeigen.
- Object-URL bei Dateiwechsel und Unmount freigeben.
- Wenn kein Logo gewählt ist: Initialen-Fallback anzeigen.

Akzeptanz für diesen Chunk:

- Logo-Datei kann gewählt werden.
- Vorschau erscheint vor dem Speichern.
- Dateiwechsel aktualisiert die Vorschau.

### Chunk 5 - Logo-Upload nach Create

Ziel: Das Logo wird nach dem erfolgreichen Anlegen direkt hochgeladen.

Aufgaben:

- Nach `createSubscription` und optionaler Tag-Zuweisung `uploadSubscriptionLogo(newSub.id, file)` ausführen.
- Die finale Subscription aus dem Logo-Upload für `onCreated` verwenden.
- Bei fehlendem Logo diesen Schritt überspringen.
- Während der Sequenz Formular und Buttons deaktivieren.

Akzeptanz für diesen Chunk:

- Abo mit Logo wird erstellt.
- Listenansicht zeigt das Logo direkt nach dem Speichern.
- Abo ohne Logo funktioniert weiterhin.

### Chunk 6 - Fehlerzustände absichern

Ziel: Nach erfolgreichem Create darf kein versehentliches zweites Abo entstehen.

Aufgaben:

- Unterschiedliche Fehlerzustände abbilden:
  - Create-Fehler: Abo existiert nicht, Speichern erneut erlauben.
  - Tag-Fehler nach Create: Abo existiert, erneutes Create blockieren.
  - Logo-Fehler nach Create: Abo existiert, erneutes Create blockieren.
- Bei Logo-Fehler Aktionen anbieten:
  - "Logo erneut versuchen"
  - "Schließen"
- Beim Schließen nach Teil-Erfolg das bereits erstellte Abo in die Liste übernehmen.

Akzeptanz für diesen Chunk:

- Fehler beim Create erzeugt kein Abo.
- Fehler nach Create erzeugt kein zweites Abo.
- Nutzer kann nach Logo-Fehler schließen oder erneut hochladen.

### Chunk 7 - Responsive Styling und UI-Polish

Ziel: Modal fühlt sich wie ein nativer Teil der App an.

Aufgaben:

- CSS an vorhandene Modal-Muster anlehnen.
- Farben ausschließlich über CSS-Variablen.
- Keine Inline-Styles für Layout, Farben oder Abstände.
- Maximalbreite und `max-height` setzen.
- Inhalt bei kleinen Viewports scrollbar machen.
- Fokus-, Hover- und Disabled-Zustände prüfen.

Akzeptanz für diesen Chunk:

- Modal ist in Light und Dark Mode konsistent.
- Mobile Breite bleibt bedienbar.
- Keine sichtbaren Überlappungen.

### Chunk 8 - Verifikation

Ziel: Der Flow ist manuell und technisch geprüft.

Aufgaben:

- TypeScript-Build ausführen.
- Frontend-Lint ausführen, falls im Projekt verfügbar.
- Manuelle Browserprüfung:
  - ohne Datum
  - mit Tags
  - mit Logo
  - Logo-Fehler
  - Overlay-Klick
  - Mobile Breite
- Bei Bedarf Screenshots oder kurze Notizen im PR/Umsetzungsprotokoll festhalten.

Akzeptanz für diesen Chunk:

- Build läuft grün.
- Die Test-Checkliste aus Abschnitt 11 ist abgearbeitet.

---

## 13. Entwicklerauftrag

Baue die Subscription-Erstellung von einem Inline-Formular zu einem kompakten Modal um.
Extrahiere den Create-Flow in `SubscriptionCreateModal.tsx`, entferne die Inline-Create-Card
aus `SubscriptionsPage.tsx` und integriere direkten Logo-Upload nach erfolgreichem Create.
Verwende die bestehenden API-Funktionen (`createSubscription`, `setSubscriptionTags`,
`uploadSubscriptionLogo`) und bestehenden Tag-Komponenten. Das Backend bleibt unverändert.

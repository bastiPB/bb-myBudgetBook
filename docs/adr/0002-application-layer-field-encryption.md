# ADR 0002: Application-layer field encryption for sensitive financial data

## Status
Accepted

## Kontext
Das Projekt ist selfhosted und soll „out of the box“ ohne Host-spezifische Disk-Encryption (z.B. LUKS/dm-crypt) funktionieren.
Wir wollen trotzdem Schutz erreichen, falls DB-Volume/Backups kopiert werden.

PostgreSQL bietet Verschlüsselung auf mehreren Ebenen. Spaltenverschlüsselung via pgcrypto ist möglich, aber die Doku weist darauf hin, dass Klartext und Schlüssel beim Entschlüsseln kurzzeitig auf dem DB-Server vorhanden sind. (Siehe externe Referenzen in den Projekt-Notizen.)

## Entscheidung
Wir verschlüsseln **sensible Felder** im Backend (Application Layer), bevor sie in Postgres gespeichert werden.
Nicht-sensitive Felder (z.B. Beträge/Datum/Intervalle) bleiben im Klartext, damit Filter/Sort/Summen effizient bleiben.

## Alternativen
1) Host-level Disk Encryption (LUKS/dm-crypt)
   - Pro: starke At-rest Absicherung
   - Contra: widerspricht „out of the box“ Requirement

2) pgcrypto (DB-level field encryption)
   - Pro: Verschlüsselung in DB möglich
   - Contra: Schlüsselmanagement & Klartext/Key kurzzeitig auf Server; komplexere Queries

3) Keine Verschlüsselung, nur Access Controls
   - Pro: simpel
   - Contra: DB-Kopie/Backup wäre im Klartext lesbar

## Konsequenzen
- Pro:
  - DB-Kopie/Backup enthält für sensible Felder nur Ciphertext
  - Kein Host-Setup nötig
- Contra:
  - Auf verschlüsselten Feldern sind nur eingeschränkte Queries möglich (kein LIKE/Fulltext ohne Zusatzkonzepte)
  - Key Management wird Teil der Deployment-Doku (Secrets dürfen nicht im Repo landen)
- Follow-ups:
  - Festlegen, welche Felder „sensibel“ sind (Docs + ggf. Tests)
  - Ergänzen von Backup/Restore Guidelines (Key muss gesichert werden)

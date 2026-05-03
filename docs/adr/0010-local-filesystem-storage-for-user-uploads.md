# ADR 0010: Lokales Dateisystem für User-Uploads (Logos)

## Status
Accepted

## Kontext

Ab v0.2.2 (Slice D) können Nutzer ein Provider-Logo je Abo hochladen.
Das Logo muss irgendwo gespeichert werden und per URL abrufbar sein.

Das Projekt wird selfhosted auf einem einzelnen Server per docker-compose betrieben —
kein Cloud-Zwang, keine automatische Infrastruktur für Object Storage.

Drei Optionen wurden verglichen:

| Option | Beschreibung |
|---|---|
| A (gewählt) | Lokales Dateisystem (`/uploads/logos/`), Static-Files-Mount in FastAPI |
| B | Object Storage (MinIO lokal / S3 in Prod) — `boto3`-Abhängigkeit |
| C | BYTEA/Base64 direkt in der Datenbank — nicht empfohlen |

## Entscheidung

**Option A** — lokales Dateisystem.

Umsetzung:
- FastAPI empfängt den Upload (Multipart), speichert die Datei unter einem UUID-Dateinamen in `/uploads/logos/`.
- In der DB-Spalte `logo_url` steht ein **relativer Pfad** (`logos/<uuid>.png`), keine absolute URL.
- Das Frontend baut die vollständige URL dynamisch aus `VITE_API_BASE + "/uploads/" + logo_url`.
- FastAPI mountet `/uploads` als Static Files.

Der relative Pfad in der DB ist der wichtigste Entwurfsentscheid:
wenn später auf Object Storage migriert wird, ändert sich nur der Upload-Handler und die URL-Generierung im Frontend — die DB-Spalte und das Datenbankschema bleiben kompatibel.

## Alternativen

**Option B — Object Storage (MinIO/S3)**
- Vorteil: stateless Backend, CDN-fähig, skaliert auf mehrere Instanzen
- Nachteil: erfordert lokalen MinIO-Container (eigener Service), `boto3`-Abhängigkeit,
  Bucket-Konfiguration, Credentials — für ein Single-Node-Selfhosted-Deployment aktuell Overengineering

**Option C — BYTEA/Base64 in der Datenbank**
- Vorteil: einfaches Backup (DB = alles)
- Nachteil: bläht jede Datenbank-Abfrage auf; PostgreSQL ist kein Bild-Server;
  keine HTTP-Caching-Header möglich — nicht empfohlen

## Konsequenzen

Positiv:
- Keine neue Infrastruktur-Abhängigkeit
- Sofort lauffähig im bestehenden docker-compose-Setup
- Migrationspfad zu Object Storage ist durch relativen Pfad in DB offen gehalten

Bekannte Lücke:
- **Backup**: Upload-Dateien liegen außerhalb der Datenbank und werden von einem
  reinen `pg_dump` nicht erfasst. Nutzer müssen das Volume `/uploads` explizit sichern.
  → Dieses Risiko ist dokumentiert und in Icebox EPIC 06 (Backup-Anleitung & Datensicherung)
  zur mittelfristigen Adressierung vorgemerkt.

Gilt für alle zukünftigen Module:
- Jedes Modul, das User-Uploads speichert, verwendet dieselbe Konvention:
  `/uploads/<modul>/` als Verzeichnis, relativer Pfad in der DB.

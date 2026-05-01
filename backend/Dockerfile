# Dockerfile — Beschreibt, wie das Backend-Image gebaut wird.
#
# Docker liest diese Datei von oben nach unten und führt jeden Schritt aus.
# Das Ergebnis ist ein in sich geschlossenes Image, das überall läuft.

# --- Basis-Image ---
# python:3.12-slim ist eine schlanke Python-Version ohne unnötige Tools
FROM python:3.12-slim

# Arbeitsverzeichnis im Container — alle folgenden Befehle laufen hier
WORKDIR /app

# --- Abhängigkeiten zuerst kopieren ---
# Warum zuerst nur pyproject.toml? Docker cacht jeden Schritt.
# Solange sich pyproject.toml nicht ändert, wird pip install nicht neu ausgeführt.
# Das spart beim Entwickeln viel Zeit.
COPY pyproject.toml .

# Abhängigkeiten installieren (ohne den eigentlichen Quellcode)
RUN pip install --no-cache-dir .

# --- Quellcode kopieren ---
# Kommt nach pip install, damit Code-Änderungen den Cache nicht invalidieren
COPY . .

# Entrypoint-Skript ausführbar machen
# Ohne diesen Schritt würde Linux die Datei nicht als Programm starten
RUN chmod +x entrypoint.sh

# Port dokumentieren — der eigentliche Port wird in docker-compose.yml gemappt
EXPOSE 8000

# Beim Container-Start: erst Migrationen, dann Server (siehe entrypoint.sh)
CMD ["./entrypoint.sh"]

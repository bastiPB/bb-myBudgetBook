# Dockerfile — Multi-Stage Build für das Frontend.
#
# Zwei Phasen ("Stages"):
#   1. builder  → Node.js installiert Abhängigkeiten und baut dist/
#   2. runtime  → nginx kopiert nur dist/ aus Phase 1 und startet
#
# Warum Multi-Stage?
# Node.js (mit node_modules) würde das Image ~300 MB groß machen.
# Das finale Image enthält nur nginx + die fertigen HTML/CSS/JS-Dateien — ~25 MB.
# Node.js ist im Produktions-Container nicht mehr vorhanden (kleinere Angriffsfläche).

# =============================================================
# Stage 1: Builder
# node:20-alpine = Node.js 20 auf Alpine Linux (sehr schlankes Basis-Image)
# =============================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Zuerst nur die Paket-Dateien kopieren.
# Docker cacht jeden Schritt: Solange package.json und package-lock.json
# unverändert sind, wird npm ci nicht neu ausgeführt — spart Zeit beim Bauen.
COPY package.json package-lock.json ./

# npm ci = "clean install" — installiert exakt die Versionen aus package-lock.json.
# Schneller und deterministischer als npm install.
RUN npm ci

# Jetzt erst den Quellcode kopieren (nach npm ci, damit Code-Änderungen
# nicht den npm-Cache invalidieren)
COPY . .

# Vite baut die App: TypeScript → JS, alle Assets nach dist/
RUN npm run build

# =============================================================
# Stage 2: Runtime
# nginx:alpine = nginx auf Alpine Linux — nur ~25 MB
# =============================================================
FROM nginx:alpine

# Unsere nginx-Konfiguration einspielen
# (überschreibt die Default-Config von nginx)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Den fertigen Build aus Stage 1 kopieren
# --from=builder verweist auf den Stage-Namen oben
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx im Vordergrund starten (kein "daemon mode" — Docker braucht einen Vordergrundprozess)
CMD ["nginx", "-g", "daemon off;"]

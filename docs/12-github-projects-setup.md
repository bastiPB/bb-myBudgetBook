---
doc: github-projects-setup
status: living
---

# GitHub Projects Setup (Backlog + Roadmap)

Dieses Dokument beschreibt, wie das Projekt-Tracking in GitHub organisiert wird.
Ziel: **Backlog, Planung und Roadmap** direkt neben dem Code – ohne Tool-Sprawl.

GitHub Projects ist ein flexibles Tool zum Planen und Tracken von Arbeit, das mit Issues/PRs integriert ist und mehrere Views (Table/Board/Roadmap) sowie Custom Fields unterstützt.

## 1) Grundprinzip: Labels vs. Project Fields

### Labels = Taxonomie (Klassifikation)
Labels geben Themen/Kategorien an (z.B. type:*, area:*, target:*, risk:*, privacy:*).

### Project Fields = Planung (exklusivere Metadaten)
Für Priority, Effort, Iteration, Start/Target Date eignen sich Project Fields.

## 2) Projekt anlegen (einmalig)
Erstelle ein GitHub Project (User- oder Org‑Level) und nutze Table/Board/Roadmap Views.

Empfohlener Name:
- Finanztool — Planning

## 3) Views (empfohlenes Set)
- Table: Backlog (sortieren/filtern)
- Board: In Progress (Status-Fluss)
- Roadmap: Roadmap (Timeline)

## 4) Empfohlene Project Fields (Minimal, aber stark)
- Priority (Single select): P0/P1/P2/P3
- Effort (Single select): S/M/L (oder 1/2/3/5/8)
- Target (Single select): v0.1/v0.2/Icebox
- Start date (Date field)
- Target date (Date field)
Optional:
- Iteration (Iteration field)
- Risk (Single select): Low/Medium/High
- Privacy (Single select): Low/Medium/High

## 5) Triage Workflow (Kurz)
- Neue Issues: status:needs-triage + type:* + target:* → ins Project
- Nach Triage: status:ready + Priority/Effort setzen
- Umsetzung: status:in-progress → status:done

## 6) MVP Bezug
- target:v0.1 muss MVP-Fit haben (docs/01-mvp.md)
- target:icebox wird nicht gegen MVP geprüft, bis promoted

## 7) Definition of Done & Release Gate
- DoD: docs/06-definition-of-done.md
- Release Checklist: docs/04-release-readiness-checklist.md

---
doc: labels
status: living
---

# Labels & Triage

## Ziel
Labels machen Issues filterbar und planbar. Wir nutzen Präfixe als Kategorien.

## Kategorien (sollten i.d.R. exklusiv genutzt werden)
- type:* (genau 1)
- target:* (genau 1)
- status:* (genau 1)
Optional:
- risk:* (max 1)
- privacy:* (max 1)

## Kategorien (nicht exklusiv)
- area:* (0..n)

## Core Labels
Type:
- type:bug, type:feature, type:docs, type:chore, type:epic

Target:
- target:v0.1, target:v0.2, target:icebox

Status:
- status:needs-triage, status:ready, status:blocked, status:in-progress, status:done

Area:
- area:core, area:integration, area:ecosystem, area:security, area:ops, area:ux

Risk:
- risk:low, risk:medium, risk:high

Privacy:
- privacy:low, privacy:medium, privacy:high

Community:
- good first issue, help wanted

## Triage Workflow (kurz)
1) Neues Issue kommt rein → status:needs-triage + type:* + target:* setzen
2) Wenn klar → status:ready
3) Wenn Arbeit startet → status:in-progress
4) Blocker → status:blocked
5) Erledigt → status:done
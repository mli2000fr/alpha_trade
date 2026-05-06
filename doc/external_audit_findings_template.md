# Rapport d'audit externe — Template

> Sprint S25.2 — à compléter par l'auditeur externe.

## 1. Résumé exécutif

* **Auditeur** : (Nom / société)
* **Période** : YYYY-MM-DD → YYYY-MM-DD
* **Tag git audité** : `vX.Y.Z` (commit `<sha>`)
* **Note globale** : __ / 10
* **Décision** : `GO PROD` / `GO CONDITIONNEL` / `NO-GO`

### Synthèse en 5 lignes

(à compléter)

## 2. Méthodologie

* Lecture documentation (h)
* Code review (h)
* Reproduction tests (h)
* Pen-test léger (h)
* Total (j/h)

Outils : (mypy, ruff, semgrep, custom scripts, …)

## 3. Findings

### P0 — Critique (bloquant)

| ID | Titre | Fichier | Description | Recommandation |
|---|---|---|---|---|
| EX-001 | … | … | … | … |

### P1 — Majeur

| ID | Titre | Fichier | Description | Recommandation |
|---|---|---|---|---|

### P2 — Mineur

### P3 — Cosmétique / amélioration

## 4. Points forts

* (à compléter — minimum 5 points positifs si revue indépendante)

## 5. Points d'amélioration stratégique

* Architecture : …
* Code qualité : …
* Sécurité : …
* Observabilité : …
* Conformité : …

## 6. Plan correctif proposé

| Finding | Action | Owner | Date cible |
|---|---|---|---|

## 7. Annexes

* `report.md.sig` — signature PGP ASCII-armored.
* `report.md.sha256` — checksum (output de `sha256sum report.md`).


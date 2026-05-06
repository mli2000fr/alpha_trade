# Findings du pré-audit interne — registre

> Sprint S25.1 — Phase G.

Template de tracking des findings émis par
`scripts/run_pre_audit_checklist.py` ou par revue manuelle.

## Format

| ID | Sévérité | Section | Description | Owner | Cible | Statut | Fix commit |
|---|:---:|---|---|---|---|:---:|---|
| F-001 | (P0/P1/P2/P3) | Architecture | … | … | YYYY-MM-DD | ✅/⚠️/❌ | sha |

## Sévérités

* **P0** — bloque l'audit externe / production. Fix < 48 h.
* **P1** — risque significatif. Fix < 1 sprint.
* **P2** — amélioration recommandée. Fix < 1 trimestre.
* **P3** — cosmétique / dette tech. Fix opportuniste.

## Workflow

1. `python scripts/run_pre_audit_checklist.py --out artifacts/pre_audit/`.
2. Parcourir `artifacts/pre_audit/<date>/report.md`.
3. Pour chaque ❌ ou ⚠️ : créer une entrée `F-NNN` ci-dessous.
4. Affecter owner + date cible.
5. Re-runner avant audit externe S25.2.

## Findings ouverts

| ID | Sévérité | Section | Description | Owner | Cible | Statut |
|---|:---:|---|---|---|---|:---:|

*(à compléter au premier run)*

## Findings clos

| ID | Sévérité | Description | Fix commit | Date close |
|---|:---:|---|---|---|


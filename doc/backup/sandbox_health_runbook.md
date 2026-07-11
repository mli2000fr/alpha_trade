# Runbook — Sandbox health (régression nightly)

> Sprint S24.2 — Phase G.

## Déclencheur

* Streak rouge ≥ 1 nuit (`artifacts/sandbox_runs/_rollup.json` ⇒
  `n_failure > 0` et `streak_green < 30`).
* Notification Slack `#alpha-trade-ops`.

## T+0 — Triage (≤ 15 min)

1. Ouvrir IHM page **🟢 Sandbox health** ; identifier la date d'échec.
2. Télécharger l'artefact `sandbox-nightly-<run_id>` depuis GitHub
   Actions ; consulter `log/` et `artifacts/sandbox_nightly/`.
3. Identifier l'étape en échec :
   * `Schema` ⇒ migration alembic cassée ;
   * `Pre-live checklist` ⇒ secrets / connectivité ;
   * `Screener` / `Selector` / `Risk` ⇒ régression métier ;
   * `Execution (paper)` ⇒ adapter Alpaca ;
   * `Broker reconciliation` ⇒ divergence broker ;
   * `Verify audit chain` ⇒ corruption HMAC.

## T+15 → T+60 — Stabilisation

* Si secret expiré ⇒ régénérer + relancer le workflow en
  `workflow_dispatch`.
* Si bug code ⇒ ouvrir un PR hotfix avec test de non-régression.
* Si dépendance externe (Alpaca paper down) ⇒ documenter dans
  `doc/runbook_provider_incident.md` puis attendre rétablissement.

## T+60 — Décision Go/No-Go production

* Si streak rouge isolée et cause connue + corrigée ⇒ **continuer**.
* Si > 2 échecs sur 7 j ou cause structurelle inconnue ⇒
  **bloquer prod live** jusqu'à analyse complète.

## Post-mortem

* Ajouter une entrée datée dans `doc/incident_postmortems.md`
  (créer le fichier si absent).
* Compléter la suite de tests pour empêcher la régression.


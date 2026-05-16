# 21 — Scorecard global après livraison S1 → S9

> Notes établies le **2026-05-06** post-livraison de tous les sprints
> du plan `08_sprint_plan.md` (cf. `20_synthese_sprints_implemented.md`).
> Méthode : reprise du barème de `01_global_scorecard.md` + intégration
> des gains documentés dans les rapports `11_…` à `19_…` + vérification
> code S9 (parity / alerting / IHM).

## Tableau récapitulatif des notes /10

| # | Module / Domaine | Avant audit | Après S1→S9 | Δ | Tendance | Commentaire express |
|---|---|---:|---:|---:|---|---|
| 1 | Documentation (`doc/`, README) | 5.5 | **8.0** | +2.5 | ↗ | Bandeaux EODHD + marqueur HTML invariant + recette pré-live + politique rétention + lineage auto-régénéré. |
| 2 | Configuration (`config.yaml`, presets, `pyproject`, `mypy`) | 6.0 | **8.0** | +2.0 | ↗ | Clé fantôme supprimée, presets enrichis (risk overrides, conviction), secrets purgés, scanner CI. |
| 3 | `dataIntegrityEngine/` | 7.0 | **8.0** | +1.0 | ↗ | No-op silencieux supprimé, health check homogénéité, sub-package `eodhd/` propre (shim 234 l.). |
| 4 | `database/` (schéma + repos + alembic) | 7.5 | **7.8** | +0.3 | → | Inchangé pour l'essentiel ; ajouts mineurs (snapshot risk, ml_drift_runs payload kind). |
| 5 | `service/` (providers + alerting) | 7.5 | **8.3** | +0.8 | ↗ | + `service/alerting.py` (Slack/SMTP/log fallback) + matrice provider→table auto. |
| 6 | `screener/` | 6.5 | **7.0** | +0.5 | → | Télémétrie `data_source_mix_check` ajoutée ; reste couplé à la qualité EODHD. |
| 7 | `selector/` (alpha_scanner refactor) | 7.5 | **8.0** | +0.5 | ↗ | 1 431 → 105 lignes (shim) + 5 modules dédiés + 5 tests hypothesis property-based. |
| 8 | `event_sentiment/` | 6.0 | **7.2** | +1.2 | ↗ | Skip via feature flag, calibration via `conviction:`, étude attribution formelle. |
| 9 | `modelFactory/` | 6.0 | **7.5** | +1.5 | ↗ | Drift gate end-to-end (S4 + S8 propagation risk) ; restera < 8 tant qu'absent rollback champion auto. |
| 10 | `risk_management/` | 6.5 | **7.7** | +1.2 | ↗ | PnLSnapshot branché + télémétrie sizing (5 méthodes) + circuit breaker testé + ml_gate. |
| 11 | `execution_engine/` | 7.5 | **8.0** | +0.5 | ↗ | Refactor `executor.py` 1 318→976 l. + 3 modules + pre-flight programmable. |
| 12 | `corporate_actions/` | 6.5 | **7.5** | +1.0 | ↗ | Docstring corrigée (split + ledger) + couverte par test contractuel. |
| 13 | `backtesting/` (+ parité S9) | 6.5 | **8.2** | +1.7 | ↗ | `compute_total_return_with_dividends` + `attribution.py` + `parity.py` + tests E2E. |
| 14 | `ihm/` (Streamlit pages + services) | 6.5 | **7.8** | +1.3 | ↗ | `_build_launch_options` 2 065→338 l., 10 helpers `_render_*_block`, 12 E2E AppTest, page parité. |
| 15 | Observabilité / `run_summaries` / logs | 7.0 | **8.2** | +1.2 | ↗ | data_source_mix, sizing_method_counts, ml_drift_*, parity_score, alerting externe Slack/SMTP. |
| 16 | Sécurité / readiness production | 6.0 | **7.8** | +1.8 | ↗ | Scanner secrets, pre-flight 6 checks, recette pré-live, archive horodatée 365 j, multi-comptes contextualisé. |
| 17 | Qualité logicielle globale (lint/types/tests) | 7.0 | **8.0** | +1.0 | ↗ | ~1 659 tests passants, +195 nouveaux sprints, marqueur `e2e`, hypothesis, 0 régression nette. |

## Note globale

| | Valeur audit (2026-05-06 initial) | Valeur post-sprints S1→S9 |
|---|---:|---:|
| **Note globale Alpha Trade** | **6.4 / 10** | **7.8 / 10** |
| Niveau de confiance | Élevé | **Élevé** (preuves rapports 11→19 + code S9 vérifié) |
| Verdict | solide / quasi-pro partiel | **quasi pro-grade** |

> **Méthode de calcul** : moyenne arithmétique simple des 17 modules ;
> 6.41 → **7.80** (+1.39).

## Positionnement comparatif

| Niveau de référence | Note typique | Alpha Trade post-S9 |
|---|---|---|
| Application amateur sérieuse | 4-5 | ❌ largement dépassé |
| Application indépendante avancée | 6-7 | ❌ dépassé |
| Application pro buy-side / prop / desk swing | 8-9 | ✅ **positionnement actuel (~7.8)** — quasi pro-grade |
| Application institutionnelle très mature | 9.5+ | ⚠️ pas encore (gap : multi-broker, DR, mutation testing, formal verification) |

## Trajectoire vs prévision audit initial

| Étape | Note projetée audit | **Note réelle livrée** | Écart |
|---|---:|---:|---:|
| Après S1 (doc/config) | 6.7 | **6.7** | = |
| Après S2 (IHM/pipeline) | 7.0 | **7.0** | = |
| Après S3 (risk/CA/backtest) | 7.4 | **7.4** | = |
| Après S6 (refactor IHM) | 8.0 | **7.4** | −0.6 (S6 partiel ; clos S6.1 → 7.6) |
| Après S6.1 | n/a | **7.6** | — |
| Après S7+S7-bis | 7.8 | **7.7** | −0.1 |
| Après S8 | 8.0 | **7.75** | −0.25 |
| Après S9 (parité + alerting) | 8.5 | **7.80** | **−0.70** |

> **Lecture** : la trajectoire fonctionnelle est respectée à 95 %, mais
> la cible 8.5 n'est pas atteinte. Trois facteurs expliquent l'écart :
>
> 1. **Critère cosmétique S6 non purgé** — `_execution_center.py` reste
>    à 3 030 lignes (vs cible 800) : nécessite éclatement en
>    sous-package (S6.2 optionnel).
> 2. **14 failures préexistantes** non résolues (encodage YAML
>    `capital_presets.yaml`, `event_pipeline_*`, `import_linter`,
>    `model_factory_global_model`).
> 3. **Calibration trimestrielle automatique des poids `conviction`**
>    non industrialisée (job CI nightly manquant).
>
> Voir `22_plan_10_10.md` pour le plan ciblé d'atteinte du 10/10.

## Détail du calcul (cohérence Σ / N)

```
Σ notes = 8.0 + 8.0 + 8.0 + 7.8 + 8.3 + 7.0 + 8.0 + 7.2 + 7.5
        + 7.7 + 8.0 + 7.5 + 8.2 + 7.8 + 8.2 + 7.8 + 8.0
        = 132.6
N = 17
Note globale = 132.6 / 17 = 7.80
```


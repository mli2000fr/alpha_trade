# Couverture des pages IHM

Cette matrice est dérivée de `ihm/services/navigation.py`. Une page officielle doit avoir une source et au moins un chapitre opérateur. Les helpers internes sous `ihm/pages/_...` ne sont pas des pages de navigation autonomes.

| Section | Page / clé | Source | Guide principal |
|---|---|---|---|
| Accueil | Vue d’ensemble / `overview` | `ihm/pages/overview.py` | [workflow](02_workflow_quotidien.md) |
| Workflow | Pipeline / `pipeline` | `ihm/pages/pipeline.py` | [pipeline](03_pipeline.md) |
| Workflow | Supervision Ops / `supervision_ops` | `ihm/pages/supervision_ops.py` | [supervision](09_supervision_parite.md) |
| Workflow | Infra & Backups / `ops_infra` | `ihm/pages/ops_infra.py` | [infra/DB](14_infra_backups_et_db.md) |
| Trading | Execution / `execution` | `ihm/pages/execution.py` | [exécution](07_execution.md) |
| Trading | Risk / `risk` | `ihm/pages/risk.py` | [risque](06_risque.md) |
| Trading | Régime Marché / `market_regime` | `ihm/pages/market_regime.py` | [régime/comptes](13_regime_et_comptes.md) |
| Trading | Comptes Alpaca / `alpaca_accounts` | `ihm/pages/alpaca_accounts.py` | [régime/comptes](13_regime_et_comptes.md) |
| Recherche | Screening / `screening` | `ihm/pages/screening.py` | [screening](04_screening.md) |
| Recherche | Backtesting / `backtesting` | `ihm/pages/backtesting/` | [backtesting](08_backtesting.md) |
| Recherche | Calibrations poids / `weights_calibration_runs` | `ihm/pages/weights_calibration_runs.py` | [calibrations/diagnostic](15_calibrations_et_diagnostic_ml.md) |
| Recherche | Parité / `parity` | `ihm/pages/parity.py` | [supervision/parité](09_supervision_parite.md) |
| Recherche | ML / Prédictions / `ml` | `ihm/pages/ml.py` | [ML/prédictions](05_ml_predictions.md) |
| Recherche | Diagnostic ML / `ml_diagnostics` | `ihm/pages/ml_diagnostics.py` | [calibrations/diagnostic](15_calibrations_et_diagnostic_ml.md) |
| Recherche | Fondamentaux / `fundamentals` | `ihm/pages/fundamentals.py` | [fondamentaux](16_fondamentaux.md) |
| Configuration | Paramètres / Santé / `settings` | `ihm/pages/settings.py` | [paramètres](11_parametres_administration.md) |
| Conformité | Compliance & Audit / `compliance_audit` | `ihm/pages/compliance_audit.py` | [conformité](17_conformite_fiscalite_sandbox.md) |
| Conformité | Tax Compliance / `tax_compliance` | `ihm/pages/tax_compliance.py` | [conformité](17_conformite_fiscalite_sandbox.md) |
| Conformité | Sandbox health / `sandbox_health` | `ihm/pages/sandbox_health.py` | [conformité](17_conformite_fiscalite_sandbox.md) |
| Conformité | Corporate Actions / `corporate_actions` | `ihm/pages/corporate_actions.py` | [corporate actions](10_conformite_corporate_actions.md) |
| Conformité | Administration DB / `db_admin` | `ihm/pages/db_admin.py` | [infra/DB](14_infra_backups_et_db.md) |
| Conformité | Glossaire / `glossary` | `ihm/pages/glossary.py` | [glossaire/aide](18_glossaire_et_aide.md) |

## Contrôle de maintenance

Lorsqu’une entrée change dans `NAVIGATION_PAGES` ou `get_navigation_sections()`, mettre à jour cette matrice, le schéma du README et le chapitre concerné. Vérifier ensuite les services appelés par la page : un libellé de bouton ne suffit pas à documenter ses effets.


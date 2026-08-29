# Documentation Alpha Trade — référentiel refactorisé

Cette arborescence documente l'application telle qu'elle existe dans le code source au 29 août 2026. Les documents historiques de `doc/` ont servi de contexte, mais ne constituent pas la source de vérité. En cas d'écart, l'ordre d'autorité est : code exécutable, migrations et schéma SQL, `config.yaml`, tests contractuels, puis cette documentation.

## Parcours conseillé pour un nouvel arrivant

1. [Vue fonctionnelle](01_vue_fonctionnelle.md) : ce que fait le produit et les concepts métier.
2. [Architecture globale](02_architecture_globale.md) : flux, frontières et dépendances.
3. [Installation et prise en main](03_installation_et_demarrage.md).
4. [Pipeline quotidien](04_pipeline_quotidien.md) : ordre canonique des 14 étapes.
5. [Données et univers PIT](05_donnees_et_univers_pit.md).
6. [ML : vue d'ensemble](06_ml_vue_ensemble.md), puis les documents spécialisés Global Ranking et Oracle Extreme.
7. [Risque et portefeuille](09_risque_et_portefeuille.md), [régime de marché](10_regime_marche.md), puis [exécution](11_execution_et_protections.md).
8. [Backtesting et validation](12_backtesting_validation.md).

## Index par domaine

| Domaine | Document | Code principal |
|---|---|---|
| Produit et vocabulaire | [01](01_vue_fonctionnelle.md) | tout le dépôt |
| Architecture | [02](02_architecture_globale.md) | `core/`, `common/`, packages métier |
| Démarrage | [03](03_installation_et_demarrage.md) | `pyproject.toml`, `run.py`, `ihm/app.py` |
| Orchestration | [04](04_pipeline_quotidien.md) | `ihm/services/pipeline_runner.py`, `flows/` |
| Données, qualité, PIT | [05](05_donnees_et_univers_pit.md) | `dataIntegrityEngine/`, `common/tradable_universe.py` |
| ML général | [06](06_ml_vue_ensemble.md) | `modelFactory/` |
| Global Ranking | [07](07_ml_global_ranking.md) | `modelFactory/global_ranking.py` |
| Oracle Extreme | [08](08_ml_oracle_extreme.md) | `modelFactory/oracle/` |
| Risque | [09](09_risque_et_portefeuille.md) | `risk_management/` |
| Régimes | [10](10_regime_marche.md) | `service/market/`, `risk_management/regime_*` |
| Exécution | [11](11_execution_et_protections.md) | `run_execution.py`, `execution_engine/` |
| Backtest | [12](12_backtesting_validation.md) | `backtesting/` |
| Sentiment et sélection | [13](13_screener_selector_sentiment.md) | `screener/`, `selector/`, `event_sentiment/` |
| Services externes | [14](14_services_externes.md) | `service/` |
| Base de données | [15](15_base_de_donnees.md) | `database/`, `alembic/` |
| IHM et opérations | [16](16_ihm_et_operations.md) | `ihm/`, `reporting/`, `lineage/` |
| Corporate actions | [17](17_corporate_actions.md) | `corporate_actions/` |
| Configuration | [18](18_reference_configuration.md) | `config.yaml`, classes de configuration |
| Tests et contribution | [19](19_tests_et_contribution.md) | `tests/`, `formal/` |
| Glossaire | [20](20_glossaire.md) | contrats transverses |
| Catalogue du code | [21](21_catalogue_modules.md) | tous les packages Python |
| Runbook opérateur | [22](22_runbook_exploitation.md) | pipeline, risque, exécution, reprise |

## Règles de lecture importantes

- **Production et recherche sont séparées.** Un contrat de labels ou un lifecycle de recherche n'est pas automatiquement le contrat d'exécution réel.
- **PIT signifie point-in-time.** Une donnée, un univers ou une prédiction doit être résolu à la date considérée sans information future.
- **ML-first.** Le scope nominal vient de l'univers tradable complet ; le ML décide le côté et le rang. Les scores scanner/selector servent de features, diagnostics ou vetos, pas de fallback autonome.
- **Train n'est pas quotidien.** Le pipeline quotidien consomme un champion déjà publié.
- **La configuration effective est composée.** Les valeurs par défaut Python, `config.yaml`, options CLI et préférences IHM peuvent se superposer ; les priorités sont détaillées dans [18](18_reference_configuration.md).

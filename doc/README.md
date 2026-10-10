# Documentation Alpha Trade — référentiel fonctionnel et opérationnel

**Mise à jour ciblée du 10 octobre 2026** : commencer par
[l'état actuel de l'implémentation](ETAT_ACTUEL_IMPLEMENTATION.md) et
[le catalogue courant des batchs](operations/catalogue_batchs_actuel.md).
Les guides centraux ont été rapprochés des sources ; les inventaires API et
les comptes rendus historiques ne sont pas intégralement régénérés.
[Périmètre et vérifications de cette mise à jour](AUDIT_MISE_A_JOUR_20261010.md).

Suivi exhaustif des archives : [migration de `doc/backup`](MIGRATION_BACKUP.md).

Les textes anciens conservés pour traçabilité sont isolés dans [sources historiques](sources_historiques/README.md). Ils ne font pas partie du parcours normatif.

Migration de tous les autres fichiers de l’ancien `doc` : [registre complémentaire](MIGRATION_RESTE_DOC.md).

En cas d'écart, vérifier le code exécutable, le schéma effectivement déployé,
la configuration effective et les tests du composant avant ce guide. Les fichiers
US, CN et FR sont séparés : `config.yaml` n'est pas l'unique configuration.
Une fonctionnalité implémentée ou un batch activé ne prouvent ni autorisation
de trading ni disponibilité des données.

## Parcours conseillé pour un nouvel arrivant

1. [Vue fonctionnelle](01_vue_fonctionnelle.md) : ce que fait le produit et les concepts métier.
2. [Architecture globale](02_architecture_globale.md) : flux, frontières et dépendances.
3. [Installation et prise en main](03_installation_et_demarrage.md).
4. [Pipeline quotidien](04_pipeline_quotidien.md) : 14 étapes disponibles, sélection explicite et batch US.
5. [Données et univers PIT](05_donnees_et_univers_pit.md).
6. [ML : vue d'ensemble](06_ml_vue_ensemble.md), puis les documents spécialisés Global Ranking et Oracle Extreme.
7. [Risque et portefeuille](09_risque_et_portefeuille.md), [régime de marché](10_regime_marche.md), puis [exécution](11_execution_et_protections.md).
8. [Backtesting et validation](12_backtesting_validation.md).
9. [Batchs et marchés dans l'IHM](guide_utilisateur/19_batchs_et_marches.md),
   [marché CN](cn/README.md) et [marché FR](fr/README.md).

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
| Global Ranking détaillé | [Dossier](ml/global_ranking/README.md) | univers, targets PIT, championnat, inférence, persistance et cascade |
| Modèle per-symbol détaillé | [Dossier](ml/per_symbol/README.md) | dataset séquentiel, challengers, champion, artefacts et serving |
| Modèle per-sector détaillé | [Dossier](ml/per_sector/README.md) | pooling sectoriel, targets, champions tabulaires et fallback |
| Oracle Extreme | [08](08_ml_oracle_extreme.md) | `modelFactory/oracle/` |
| Oracle Extreme détaillé | [Dossier Oracle](ml/oracle/README.md) | labels, tables, anti-fuite, walk-forward, inférence et gate |
| Oracle TOP20 tradable | [Backtest et live](ml/oracle_tradable_top20_backtest_live.md) | filtre PIT, recalcul des percentiles, direction et abstention |
| Risque | [09](09_risque_et_portefeuille.md) | `risk_management/` |
| Régimes | [10](10_regime_marche.md) | `service/market/`, `risk_management/regime_*` |
| Exécution | [11](11_execution_et_protections.md) | `run_execution.py`, `execution_engine/` |
| Backtest | [12](12_backtesting_validation.md) | `backtesting/` |
| Sentiment et sélection | [13](13_screener_selector_sentiment.md) | `screener/`, `selector/`, `event_sentiment/` |
| Services externes | [14](14_services_externes.md) | `service/` |
| Base de données | [15](15_base_de_donnees.md) | `database/`, `alembic/` |
| IHM et opérations | [16](16_ihm_et_operations.md) | `ihm/`, `reporting/`, `lineage/` |
| Alerting et métriques | [Notifications](operations/alerting_et_metriques.md) | `service/alerting.py`, Prometheus, notifications IHM |
| Corporate actions | [17](17_corporate_actions.md) | `corporate_actions/` |
| Configuration | [18](18_reference_configuration.md) | `config.yaml`, classes de configuration |
| État multi-marchés actuel | [Synthèse](ETAT_ACTUEL_IMPLEMENTATION.md) | contextes, router DB, parcours US/CN/FR |
| Collectes et sauvegardes | [Catalogue batchs](operations/catalogue_batchs_actuel.md) | YAML US/CN/FR, launchers, page Batch |
| Tests et contribution | [19](19_tests_et_contribution.md) | `tests/`, `formal/` |
| Glossaire | [20](20_glossaire.md) | contrats transverses |
| Catalogue du code | [21](21_catalogue_modules.md) | tous les packages Python |
| Runbook opérateur | [22](22_runbook_exploitation.md) | pipeline, risque, exécution, reprise |
| Fiscalité | [Wash sale](operations/fiscalite_wash_sale.md) | `tax/wash_sale.py` |
| Recherche quantitative | [Recherche](research/README.md) | branches non automatiquement promues |
| Expériences historiques | [Synthèses](experiences/README.md) | enseignements durables, séparés des contrats courants |
| Guide utilisateur | [Manuel complet](guide_utilisateur/README.md) | navigation et procédures issues des pages actuelles |
| Couverture historique | [Matrice des 178 anciens Markdown](COUVERTURE_DOCUMENTS_HISTORIQUES.md) | référence, synthèse ou archive pour chaque ancien sujet |
| Inventaires API | [API](api/README.md) | classes et fonctions extraites du code courant |
| Couverture du code | [Matrice](COVERAGE_CODE.md) | contrôle code → documentation |
| Audit de remplacement | [Audit](AUDIT_REMPLACEMENT.md) | autonomie vis-à-vis des anciens documents |

## Règles de lecture importantes

- **Production et recherche sont séparées.** Un contrat de labels ou un lifecycle de recherche n'est pas automatiquement le contrat d'exécution réel.
- **PIT signifie point-in-time.** Une donnée, un univers ou une prédiction doit être résolu à la date considérée sans information future.
- **ML-first, selon le parcours.** Les modèles directionnels/rankings et la branche Oracle-only sont distincts. Oracle estime l'amplitude, pas LONG/SHORT. Le filtre GPT prospectif PAPER est une option séparée ; les scores scanner/selector ne sont pas un fallback autonome.
- **Train n'est pas quotidien.** Le pipeline quotidien consomme un champion déjà publié.
- **La configuration effective est composée.** Les valeurs par défaut Python, `config.yaml`, options CLI et préférences IHM peuvent se superposer ; les priorités sont détaillées dans [18](18_reference_configuration.md).

## Politique concernant les anciens documents d'expérience

Les comptes rendus d'expériences restent disponibles dans les dossiers de recherche,
notamment `doc/ml`, `doc/cn` et `doc/fr`, et dans les archives. Leurs dates,
protocoles et résultats ne sont pas réécrits lors d'une mise à jour opérationnelle.

Ne sont volontairement pas reproduits : tableaux détaillés par batch, listes de seeds, journaux d'itérations, prompts d'analyse, variantes abandonnées et métriques intermédiaires. Une expérience n'est décrite comme fonctionnalité que si le code actuel l'intègre effectivement et que la configuration permet de l'activer.

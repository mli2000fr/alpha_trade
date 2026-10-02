# Sprints 0–1 France — audit de référence et route isolée

État : 2 octobre 2026. Voir l'[ADR de décision](adr_0001_contrat_marche_et_isolation.md) et le [planning complet](sprint_planning_integration_marche_francais.md). Ce rapport décrit ce qui a été **vérifié**, non les sprints futurs.

## Sprint 0 — constat du code et de la base

Révision de référence observée : `b19d6ccd94796fa5387d404e80c6111c73e64bba`. La base `alpha_trade_fr` répond en lecture seule, `SELECT DATABASE()` renvoie `alpha_trade_fr`, `information_schema` rapporte **0 table**, charset `utf8mb4`, collation `utf8mb4_0900_ai_ci`. Aucun `CREATE TABLE`, migration, entraînement, backtest ou batch n'a été lancé pour ce sprint.

Baseline ciblée **avant changement** avec `pytest -q -o addopts=''` : 37 tests de contexte/routage/scope/broker et 23 tests calendrier/parité, tous passants. La configuration pytest globale impose `--cov-fail-under=70`, ce qui fait échouer artificiellement une sélection de quelques fichiers malgré tous les tests verts ; le seuil a été désactivé **uniquement sur ces commandes ciblées**, sans modifier sa configuration dans le dépôt. L'ancien avertissement de dépréciation de `python -m execution_engine` reste inchangé.

Les artefacts des batches US/CN et backtests historiques cités dans l'ancien fil n'étaient pas présents aux emplacements attendus lors de cet audit. Leurs hashes de données/PnL n'ont donc **pas** été figés ; les tests golden remplacent provisoirement cette preuve, sans prétendre constituer une parité économique intégrale. Avant Sprint 13 ou une modification du backtest commun, choisir et archiver des runs représentatifs réellement accessibles.

| Couche | État du code au Sprint 0 | Suite prévue |
| --- | --- | --- |
| Contexte | `common/market_context.py` connaissait US_EQ, CN_A, CN_BJ, pas FR_EQ | Sprint 1 : déclaration FR désactivée |
| Base | `database/router.py` et `config/databases.yaml` isolaient US/CN | Sprint 1 : `fr_primary` figé sur `alpha_trade_fr` |
| Instrument | `database/repositories/instruments.py` avait les MIC US/CN uniquement | Sprint 1 : MIC XPAR explicite ; master FR au Sprint 2 |
| Calendrier/PIT | `common/market_calendar.py` : NYSE/CN ; `dataset_cutoffs.yaml` : US/CN | Sprint 4 : calendrier et cutoffs XPAR ; pas de fallback FR avant |
| ML | `modelFactory/config.py` a SPY par défaut ; panneaux CN séparés | Sprints 7–10 : profils/labels/modèles FR sans SPY implicite |
| Backtest | `backtesting/cli/_impl.py` contient NYSE, USD, SPY et coûts Alpaca | Sprint 12 : moteur/coûts FR, pas de CLI US utilisée pour FR |
| IHM | `ihm/services/cn_research_market.py` et pages Pipeline/Diagnostic/Backtest ne proposent que US/CN | Sprint 14 : vue FR recherche isolée |
| Broker | `execution_engine/broker_router.py` autorise seulement US_EQ | Conserver le refus FR jusqu'au Sprint 17 optionnel |
| SQL | SQL US (`stock_bars_daily`, `model_predictions`, `global_oracle_labels`) cible `alpha_trade` | Sprint 2 : SQL/migrations FR dédiés, sans réutiliser ce DDL tel quel |

Périmètre décidé : actions ordinaires sur la ligne XPAR, EUR, recherche d'abord ; Euronext Growth et actions multi-venues à clarifier dans le master. Les sources prix/benchmarks/frais ne sont **pas** considérées validées. Pour les accès, les secrets FR dédiés restent à installer ; la vérification lecture seule de la base a utilisé les identifiants existants sans les afficher.

## Sprint 1 — changements et garde-fous

Créés : `config/markets/market_fr.yaml` (désactivé), `config_fr.yaml`, `tests/test_database_router_fr.py`. Modifiés : `common/market_context.py`, `config/databases.yaml`, `database/router.py`, la table MIC du repository, tests de contexte/scope/calendrier et README du registre.

Contrôles automatiques ajoutés : FR n'est résolu que sur `fr_primary`, devise EUR et XPAR ; US/CN→FR et FR→US/CN refusés ; `DB_NAME_FR` ne peut changer le schéma ; secrets US non réutilisés implicitement ; `database_override`, URL et `verify_schema=False` ne peuvent désactiver la barrière France ; mauvais `SELECT DATABASE()` dispose le moteur puis échoue ; XNYS rejeté comme MIC FR ; calendrier/cutoff FR indisponibles échouent au lieu de retomber sur NYSE ; broker FR reste bloqué avant création du client.

Les fingerprints des contextes existants relevés après changement sont US_EQ `ac71a3039fb43e25ac732d0393a7748bca85272db35ee89472d46368809546e2`, CN_A `428aee24c2ae09ab9659af003f823bd1e4b54fad5df53670d520ce49220fa712`, CN_BJ `92027ad6930ba37ec32cf82fa855a5d6935370cb4322331e23f255c0f752df44`. Les fichiers YAML US/CN n'ont pas été modifiés ; ces valeurs servent de référence aux tests suivants. FR_EQ a son fingerprint propre, qui changera lorsque le benchmark/profil seront arrêtés.

Validation finale après changement : **146 tests passants** sur contexte/routage/broker/calendrier/parité/Oracle US-CN, repositories d'instruments, migration US et politique de capitalisation. Commandes ciblées avec `-o addopts=''` pour ne pas déclencher le seuil global de couverture sur un sous-ensemble. `git diff --check` ne signale aucune erreur de patch (les messages CRLF sont des avertissements de normalisation Git sous Windows). Un warning de dépréciation préexistant `python -m execution_engine` demeure.

## Gate et travail restant

- **GO technique Sprint 1** : route/configuration FR prête, isolée et volontairement inactive ; tests de refus présents.
- **Sprint 0 : baseline de code et décision d'architecture obtenues**, mais comparaison bit-à-bit de runs historiques réels non disponible faute d'artefacts accessibles. Cette réserve reste ouverte avant la validation économique.
- **Aucune ingestion FR encore possible** : 0 table, aucun calendrier/cutoff FR ni fournisseur/benchmark qualifié. L'étape suivante est Sprint 2 (schéma FR/Alembic/SQL), puis Sprint 3 (qualification de la source historique).

Rollback des Sprints 0–1 : retirer la seule déclaration `FR_EQ`, `fr_primary`, les deux YAML FR, le MIC FR et les tests/documents associés ; aucune donnée n'a été écrite en base.

# Plan d’implémentation — vers un backtest beaucoup plus fidèle au pipeline live

Date: 2026-05-03

## 0. Objectif

Transformer le backtest actuel, qui est surtout un moteur de replay de signaux/portefeuille, en un backtest **beaucoup plus fidèle au pipeline live 1→12**.

Objectif cible :
- conserver la vitesse et la lisibilité du backtest actuel pour la recherche,
- ajouter un mode de **replay PIT end-to-end**,
- réduire au maximum les écarts entre :
  - pipeline live IHM / CLI,
  - backfill PIT,
  - backtest standard,
  - décisions risk,
  - simulation d’exécution.

Le résultat attendu n’est pas seulement un meilleur PnL simulé, mais une **traçabilité par étape** permettant d’expliquer où et pourquoi le backtest diverge du live.

---

## 1. État actuel résumé

### 1.1 Ce que le backtest actuel fait bien
- charge les `OHLCV` depuis `stock_bars_daily`,
- charge les snapshots PIT depuis `stock_scores_history` quand disponibles,
- recharge ou reconstruit partiellement le sentiment / le ML si nécessaire,
- reconstruit les signaux de conviction,
- applique un moteur de simulation avec contraintes de compte, microstructure et overlays de risque,
- produit un rapport exploitable.

### 1.2 Ce qui manque pour être fidèle au live
Le backtest actuel **ne rejoue pas réellement** les étapes live suivantes :
- recalcul complet et contrôlé des snapshots PIT amont par date,
- `modelFactory` en mode vraiment PIT/walk-forward orchestré comme en production,
- `risk_management` via le vrai chemin `RiskRepository` + `PortfolioBuilder` + persistance des décisions,
- `execution_engine` via le vrai moteur `ProductionExecutor`, l’OCO synthétique, les transitions d’état, la réconciliation et le TCA.

### 1.3 Conclusion de départ
Le backtest actuel est utile pour la recherche, mais ce n’est pas un **jumeau opérationnel** du pipeline live.

---

## 2. Principe directeur

Créer deux niveaux explicites :

1. **Backtest research**
   - rapide,
   - orienté alpha / ranking / robustesse,
   - conserve l’architecture actuelle.

2. **Backtest pipeline-fidèle**
   - plus lent,
   - beaucoup plus proche du live,
   - rejoue la chaîne PIT décisionnelle et une partie croissante de l’exécution.

La roadmap ci-dessous concerne surtout le niveau **pipeline-fidèle**.

---

## 3. Plan concret en 3 phases

# Phase 1 — Verrouiller la fidélité PIT amont (données, scores, ML, versionnage)

## 3.1 But
Faire en sorte que les entrées du backtest soient **strictement cohérentes avec ce qu’aurait vu le pipeline live à la date J**.

## 3.2 Périmètre
Couvrir de manière robuste les étapes live amont suivantes :
- 1 / 2 : bars + sanitation déjà persistés et figés pour le replay,
- 3 / 6 / 8 : screener + alpha scanner + signal aggregator,
- 7 : consommation contrôlée des features sentiment,
- 9 / 10 : cohérence PIT des prédictions ML.

## 3.3 Travaux à réaliser

### A. Introduire un mode de dataset PIT explicite
Créer une notion formelle de **jeu de données PIT par séance** :
- `snapshot_date`
- `capital_preset_key`
- `config_fingerprint`
- source des scores (`final_score`, `final_score_sentiment`, `final_score_walk_forward`)
- source des prédictions ML
- état de couverture des overlays (quotes, earnings, sentiment, ML)

Modules probablement concernés :
- `backtesting/data_loader.py`
- `backtesting/backfill_scores_history.py`
- `backtesting/resilience.py`
- `common/capital_presets.py`
- `event_sentiment/signal_aggregator.py`
- `modelFactory/*`

### B. Geler le contrat PIT pour les scores
Renforcer le rôle de `stock_scores_history` comme **source de vérité du replay** :
- interdire silencieusement le fallback non PIT dans le mode pipeline-fidèle,
- enrichir les diagnostics quand une journée n’est pas historisée,
- tracer précisément les colonnes manquantes et les fallbacks appliqués.

### C. Introduire une stratégie ML réellement PIT
Créer un mode de backtest qui choisit explicitement entre :
- `use_persisted_predictions`
- `rebuild_predictions_from_frozen_artifacts`
- `walk_forward_train_then_predict`

Le troisième mode doit permettre un vrai replay de la logique live-like ML :
- entraînement sur l’historique disponible jusqu’à J,
- sélection de champion sans fuite d’information,
- prédiction à J.

Modules probablement concernés :
- `backtesting/resilience.py`
- `backtesting/cli/_impl.py`
- `modelFactory/predictor.py`
- `modelFactory/orchestrator.py`
- `modelFactory/cli.py`

### D. Créer un manifeste de fidélité PIT
Pour chaque run pipeline-fidèle, sauvegarder un manifeste JSON/Markdown indiquant :
- quelles tables ont été utilisées,
- quelles reconstructions ont été faites,
- quelles journées ont subi des fallbacks,
- quels composants étaient absents.

## 3.4 Livrables Phase 1
- nouveau mode CLI, par ex. `python -m backtesting run-pipeline` ou `--engine-mode pipeline`
- contrat PIT documenté
- diagnostics de couverture PIT
- ML PIT explicite
- artefact `fidelity_manifest.json`

## 3.5 Critères d’acceptation
- aucune lecture de `stock_scores` courant dans le mode pipeline-fidèle,
- tout fallback est explicitement journalisé et exposé dans le rapport,
- possibilité de rejouer une période avec preset capital cohérent,
- possibilité de distinguer clairement un run “strict PIT” d’un run “PIT dégradé”.

## 3.6 Tests à ajouter
- tests unitaires `load_scores()` sans fallback implicite en mode strict,
- tests de cohérence `capital_preset_key` / `config_fingerprint`,
- tests `rebuild-missing` avec diagnostics complets,
- tests PIT ML sans fuite d’information.

---

# Phase 2 — Rejouer les vraies décisions risk et rapprocher fortement l’exécution

## 4.1 But
Faire en sorte que le backtest ne se contente plus d’un simple replay `signals -> vectorbt`, mais rejoue la logique réelle de :
- construction des décisions risk,
- sizing,
- contraintes portefeuille,
- préparation des intentions d’exécution,
- simulation de fills plus fidèle.

## 4.2 Périmètre
Couvrir au maximum les étapes :
- 11 : `risk_management`
- 12 : `execution`

## 4.3 Travaux à réaliser

### A. Brancher le backtest sur le vrai chemin risk
Au lieu de s’arrêter à `replay_signals(...)`, créer un chemin qui appelle réellement :
- `RiskRepository.load_candidates_asof(...)`
- `PortfolioBuilder`
- logique de `risk_management/cli.py`

Objectif : produire des objets très proches de ceux du live :
- décisions,
- motifs de rejet,
- poids cibles,
- tailles de position,
- contraintes de corrélation / Kelly / caps sectoriels.

Modules probablement concernés :
- `risk_management/cli.py`
- `risk_management/db_io.py`
- `risk_management/portfolio_builder.py`
- `backtesting/*`

### B. Introduire un `ExecutionSimulationRepository`
Créer un repository de simulation compatible avec `ExecutionRepository` afin de pouvoir réutiliser le moteur d’exécution sans broker réel.

Idée :
- garder les mêmes objets métier,
- remplacer les appels broker externes par une simulation déterministe/rejouable,
- persister les événements simulés dans des tables ou artefacts dédiés.

Modules probablement concernés :
- `execution_engine/db_io.py`
- `execution_engine/executor.py`
- `execution_engine/order_intents.py`
- `execution_engine/reconciliation.py`
- `execution_engine/tca.py`
- nouveau module `backtesting/execution_simulation.py`

### C. Réutiliser `ProductionExecutor` en mode simulé
Faire tourner le vrai orchestrateur avec :
- broker adapter simulé,
- clock simulée,
- market data simulée,
- latence paramétrable,
- fills synthétiques construits à partir des OHLCV/quotes disponibles.

Cible minimale :
- soumission des intentions,
- fill partiel/total simulé,
- stop / take-profit / trailing simulés,
- annulations OCO logiques,
- calcul TCA simplifié.

### D. Introduire plusieurs niveaux de fidélité d’exécution
Exposer explicitement des profils :
- `execution_fidelity = basic`
- `execution_fidelity = broker_like`
- `execution_fidelity = replay_from_logs`

Avec :
- `basic` = proche du moteur actuel,
- `broker_like` = état/transitions/partial fills plus réalistes,
- `replay_from_logs` = quand on possède déjà des ordres/fills réels historiques.

## 4.4 Livrables Phase 2
- intégration du vrai `PortfolioBuilder` dans le mode pipeline-fidèle,
- simulation d’exécution branchée sur le vrai modèle métier de l’`execution_engine`,
- artefacts de run simulés : intentions, ordres, fills, réconciliation, TCA,
- rapport d’écart entre “signal brut” et “portefeuille effectivement exécutable”.

## 4.5 Critères d’acceptation
- les motifs de rejet risk du backtest sont comparables à ceux du live,
- le portefeuille simulé ne dépend plus seulement de `max_positions`,
- l’exécution simulée produit un journal d’événements comparable au live,
- possibilité d’expliquer une divergence PnL par : score, risk, exécution, ou données.

## 4.6 Tests à ajouter
- tests intégrés `scores_history -> RiskRepository -> PortfolioBuilder`,
- tests de simulation d’ordres / fills / trailing / OCO,
- tests de réconciliation simulée,
- tests de TCA backtest vs cas synthétiques contrôlés.

---

# Phase 3 — Construire un replay end-to-end comparable au live et un cadre de validation de dérive

## 5.1 But
Ne plus seulement “simuler”, mais **mesurer l’écart au pipeline live** et industrialiser la fidélité.

## 5.2 Travaux à réaliser

### A. Créer un orchestrateur de replay complet par séance
Créer un service unique, par exemple `BacktestPipelineReplayService`, qui pour chaque séance :
1. résout l’état PIT,
2. charge/reconstruit les scores,
3. charge/reconstruit les prédictions,
4. passe dans `risk_management`,
5. passe dans `execution_engine` simulé,
6. persiste les artefacts,
7. compare aux runs live quand ils existent.

Modules probablement concernés :
- nouveau `backtesting/pipeline_replay.py`
- `backtesting/cli/_impl.py`
- `risk_management/*`
- `execution_engine/*`

### B. Introduire un mode `shadow / compare`
Quand des runs live existent, produire automatiquement un rapport de dérive :
- candidats live vs candidats backtest,
- targets live vs targets simulées,
- ordres live vs ordres simulés,
- fills live vs fills simulés,
- PnL live vs simulé,
- attribution de l’écart par étape.

### C. Créer un rapport de fidélité
Ajouter un rapport structuré avec sections :
- fidélité des données,
- fidélité des décisions,
- fidélité de l’exécution,
- écarts résiduels non simulables,
- score global de confiance.

### D. Instituer une validation continue
Ajouter des campagnes automatiques sur quelques fenêtres de référence :
- petite période bull,
- période volatile,
- petite capitalisation,
- cas avec overlays disponibles / indisponibles,
- cas compte cash / margin.

Objectif : empêcher qu’une régression rende le backtest moins fidèle sans alerte.

## 5.3 Livrables Phase 3
- orchestrateur end-to-end de replay,
- mode `compare-to-live`,
- rapport de fidélité,
- jeux de validation de référence.

## 5.4 Critères d’acceptation
- un run pipeline-fidèle produit un artefact comparable au live,
- les écarts sont attribuables par composant,
- un tableau de bord permet d’évaluer le niveau de confiance du backtest,
- le projet dispose d’une boucle de non-régression sur la fidélité.

## 5.5 Tests à ajouter
- tests intégrés end-to-end sur fenêtres courtes,
- tests de non-régression sur divergence max acceptable,
- tests `compare-to-live` sur jeux figés,
- tests de rapports de fidélité.

---

## 6. Ordre d’implémentation recommandé

1. **Phase 1** d’abord : sans entrées PIT solides, toute fidélité aval est illusoire.
2. **Phase 2** ensuite : brancher le vrai risk et une simulation d’exécution compatible avec les objets live.
3. **Phase 3** enfin : industrialiser la comparaison, les métriques de dérive et la validation continue.

---

## 7. Fichiers / zones de code les plus concernés

### Backtesting
- `backtesting/cli/_impl.py`
- `backtesting/data_loader.py`
- `backtesting/resilience.py`
- `backtesting/signal_replay.py`
- `backtesting/simulator.py`
- `backtesting/backfill_scores_history.py`
- nouveaux modules :
  - `backtesting/pipeline_replay.py`
  - `backtesting/execution_simulation.py`
  - `backtesting/fidelity_report.py`

### Risk
- `risk_management/cli.py`
- `risk_management/db_io.py`
- `risk_management/portfolio_builder.py`
- `risk_management/config.py`

### Execution
- `execution_engine/executor.py`
- `execution_engine/db_io.py`
- `execution_engine/config.py`
- `execution_engine/order_intents.py`
- `execution_engine/reconciliation.py`
- `execution_engine/tca.py`
- `execution_engine/oco_manager.py`

### ML / Sentiment / PIT
- `modelFactory/*`
- `event_sentiment/signal_aggregator.py`
- `common/capital_presets.py`

### Tests
- `tests/test_backtesting.py`
- `tests/test_backfill_scores_history.py`
- `tests/test_risk_management_cli.py`
- `tests/test_portfolio_builder.py`
- tests exécution / replay à étendre

---

## 8. Ce qu’on pourra dire après ces 3 phases

Après ces 3 phases, on pourra dire :

- que le backtest est **beaucoup plus fidèle** au pipeline live,
- qu’il rejoue une part beaucoup plus grande de la chaîne réelle,
- qu’il sait **mesurer** ses propres écarts au live,
- qu’il devient défendable pour des décisions de production et non plus seulement de recherche.

Mais on ne pourra **toujours pas** dire honnêtement qu’il est “100% identique au live” dans tous les cas.

---

## 9. Pourquoi on n’aura pas encore un jumeau 100% live

Même avec cette roadmap, certains écarts restent structurellement difficiles voire impossibles à annuler complètement :

### A. Le marché réel n’est pas rejouable parfaitement
- ordre de passage réel dans le carnet intraday,
- liquidité instantanée,
- latence réelle,
- microstructure exacte intrabar,
- comportements broker et matching engine.

### B. Les systèmes externes ne sont pas parfaitement déterministes
- APIs broker,
- providers de données,
- retards de disponibilité,
- corrections tardives,
- trous de couverture,
- états transitoires.

### C. L’état réel du compte est historique et parfois incomplet
- buying power exact au moment précis,
- settled cash dynamique,
- positions partiellement remplies,
- exécutions concurrentes,
- modifications manuelles ou opérationnelles.

### D. Le live contient des événements non purement logiciels
- coupures réseau,
- timeouts,
- refus broker,
- délais d’acknowledgement,
- interventions humaines,
- incidents opérationnels.

Conclusion :
Un backtest peut devenir **très proche** du live, mais le “100% identique” est en pratique limité par l’irréversibilité et la non-déterminisme du monde réel.

---

## 10. Peut-on encore avancer vers le 100% ?

Oui, on peut encore s’en rapprocher fortement.

### Leviers supplémentaires possibles
1. **Replay à partir des logs live réels**
   - réutiliser ordres, fills, événements broker, snapshots compte.
2. **Archivage intraday plus riche**
   - quotes, spreads, timestamps d’événements, états intermédiaires.
3. **Mode digital twin par date**
   - figer les inputs externes et rejouer exactement les transitions connues.
4. **Calibration des modèles de fills / slippage**
   - entraînés sur les fills live historiques.
5. **Shadow runs systématiques**
   - exécuter en parallèle un backtest/replay et comparer au live chaque jour.

### Limite finale
On peut tendre vers un **jumeau opérationnel très haute fidélité**, mais pas garantir une identité parfaite universelle pour des runs non encore observés dans le monde réel.

---

## 11. Recommandation finale

Décision recommandée :
- conserver le moteur actuel comme **backtest research**,
- construire en parallèle un **mode pipeline-fidèle**,
- instituer une **mesure explicite de fidélité** plutôt que d’affirmer une équivalence totale au live.

Le vrai objectif ne doit pas être de déclarer “100% identique”, mais de pouvoir dire :

> “Nous savons exactement quelle part du pipeline live est rejouée, quelle part est approximée, et quelle est la dérive mesurée entre les deux.”


# Audit professionnel et plan de refactor — `backtesting`

_Date : 2026-05-20_

## 1. Objectif

Réévaluer le module `backtesting/` après les évolutions majeures de `selector`, `modelFactory`, `risk_management` et `execution_engine`, vérifier qu'il reste adapté au chemin canonique live, identifier les incohérences résiduelles, puis proposer un plan exécutable **sprint par sprint**.

---

## 2. Périmètre relu

### Cœur backtest
- `backtesting/cli/_impl.py`
- `backtesting/signal_replay.py`
- `backtesting/resilience.py`
- `backtesting/fidelity.py`
- `backtesting/simulator.py`
- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/execution_lifecycle_replay.py`
- `backtesting/protection_watcher_replay.py`
- `backtesting/exit_lifecycle_replay.py`
- `backtesting/report.py`
- `backtesting/report_schema.py`

### Modules amont / aval relus pour compatibilité
- `selector/*`
- `modelFactory/*`
- `risk_management/*`
- `execution_engine/*`
- `core/conviction.py`

### Références existantes consolidées
- `refactor/backtesting/audit_plan.md`
- `refactor/backtest_vs_live_roadmap.md`
- `prompt/archive/refactor/audit_backtesting.md`
- `prompt/refactor_selector.md`
- `prompt/modelFactory_refactor.md`
- `prompt/refactor_risk.md`
- `prompt/refactor_executor.md`

---

## 3. Verdict exécutif

## 3.1 Niveau global
Le backtest est **nettement plus mature qu’au moment des audits historiques**.

Les progrès déjà visibles et réellement câblés sont importants :
- cascade de score mieux structurée ;
- microstructure configurable ;
- overlays risk activables ;
- mode `pipeline` avec manifeste de fidélité ;
- pont Phase 2 → 7 vers `risk_management` / `execution_engine` ;
- meilleure instrumentation des artefacts et du reporting ;
- tests ciblés plus nombreux.

## 3.2 Conclusion courte
Le module reste **adapté** pour un usage de recherche avancée et pour un rapprochement progressif avec le live, **mais il n’est pas encore au niveau “digital twin canonique” complet**.

Il est aujourd’hui :
- **bon** pour le replay journalier enrichi ;
- **crédible** pour comparer plusieurs variantes de logique d’investissement ;
- **partiellement aligné** avec la chaîne live complète ;
- encore **fragile** sur certaines zones de convergence inter-modules et sur la gouvernance de fidélité fine.

## 3.3 Note synthétique
- Architecture : **8.5/10**
- Réalisme pipeline/live : **7.5/10**
- Observabilité : **8/10**
- Robustesse métier : **8/10**
- Niveau production institutionnel : **7/10**

---

## 4. Ce qui est désormais bien fait

## 4.1 Convergence structurelle réelle
Le backtest ne se limite plus à un simple simulateur daily isolé :
- `signal_replay.py` réutilise `core.conviction` ;
- `risk_bridge.py` branche `risk_management.portfolio_builder` ;
- `execution_replay.py` et les phases 4/5/7 rapprochent le lifecycle d’exécution ;
- `fidelity.py` explicite les dégradations PIT.

## 4.2 Réalisme opérationnel en nette hausse
Par rapport aux audits historiques, plusieurs points précédemment “à faire” sont déjà livrés :
- slippage configurable ;
- stop initial dur ;
- filtre de gap ;
- arbitrage intrabar paramétrable ;
- overlays régime / sector cap / drawdown breaker / sizing ;
- cash settlement / PDT / swing-only ;
- reporting enrichi et artefacts structurés.

## 4.3 Instrumentation utile
Le couple `resilience.py` + `fidelity.py` donne déjà un langage métier important :
- fallback score ;
- rebuild sentiment/ML ;
- stratégie PIT ML ;
- manifeste de dégradation.

## 4.4 Trajectoire compatible avec le live
Le module a désormais une vraie trajectoire de convergence avec :
- `selector` pour l’univers et les scores ;
- `modelFactory` pour l’inférence ;
- `risk_management` pour les targets ;
- `execution_engine` pour les intents/fills/protections.

---

## 5. Anomalies / incohérences résiduelles identifiées

## 5.1 Correctif immédiat déjà appliqué dans cette passe
### A1 — Divergence de source de score entre replay “research” et bridge Phase 2 risk
**Constat** : le chemin `phase2_mode != off` utilisait le `scores_df` brut côté `risk_bridge`, sans toujours reprendre la même cascade de score que `signal_replay` (`final_score_walk_forward` → `final_score_sentiment` → `final_score`).

**Impact** : divergence silencieuse possible entre :
- le backtest standard ;
- le backtest branché sur le vrai moteur `risk_management`.

**Correction appliquée** :
- `backtesting/risk_bridge.py` utilise désormais la même logique de sélection de score ;
- `backtesting/cli/_impl.py` propage le `score_column` choisi jusqu’au Phase 2 bridge.

**Bénéfice** : meilleure parité entre la variante “research” et la variante branchée risk réel.

## 5.2 Observabilité de couverture sentiment / ML insuffisante au niveau opérateur
**Constat** : les diagnostics comptaient les manques, mais n’exposaient pas clairement la **liste des symboles** concernés.

**Impact** : difficile d’identifier rapidement si une fenêtre backtest est dégradée à cause de quelques symboles clés.

**Correction appliquée dans cette passe** :
- ajout de listes de symboles manquants dans `SentimentPreparationDiagnostics` et `MlPreparationDiagnostics` ;
- logs opérateur explicites dans `backtesting/cli/_impl.py`.

## 5.3 Gap de fidélité encore présent entre “prédiction manquante” et “modèle absent / inutilisable”
**Constat** : le backtest raisonne surtout en prédictions manquantes, alors que l’exploitation veut parfois distinguer :
- pas de run predict ;
- modèle absent ;
- artefact corrompu ;
- artefact présent mais non compatible.

**Impact** : diagnostic encore trop agrégé côté ML.

**Action recommandée** : propager un motif explicite par symbole depuis `modelFactory.predictor` / `resilience.py` jusqu’au manifeste de fidélité.

## 5.4 Le backtest Phase 2+ reste encore “target-faithful” plus que “account-state-faithful”
**Constat** : la branche Phase 2/3/4/5/7 améliore fortement la fidélité des ordres et protections, mais elle ne reconstruit pas encore complètement :
- l’état compte historique exact ;
- les lots historiques réels ;
- les conflits inter-runs / réconciliations réelles ;
- les transitions broker-like plus riches (partial fills, retries, stale orders).

**Impact** : très bon replay logique, mais pas encore véritable jumeau opérationnel complet.

## 5.5 Contrat de fidélité encore trop global et pas assez “par séance / par composant”
**Constat** : `fidelity_manifest` est utile, mais reste surtout un résumé de run.

**Il manque encore** :
- une granularité par séance ;
- une granularité par symbole critique ;
- une matrice “persisté / reconstruit / fallback / absent”.

## 5.6 Couplage encore fort entre CLI monolithique et orchestration métier
`backtesting/cli/_impl.py` reste une façade très chargée :
- chargement ;
- préparation PIT ;
- replay des signaux ;
- branchements phase2→7 ;
- reporting ;
- sauvegarde artefacts.

Le module reste lisible, mais la densité augmente le coût de maintenance et le risque de régression transverse.

## 5.7 Écart persistant entre backtest “fenêtre historique” et “comparaison live run-à-run”
Le module sait mieux rejouer qu’avant, mais il n’a pas encore un vrai mode standardisé de :
- matching backtest ↔ live ;
- attribution structurée des écarts ;
- score de confiance consolidé.

C’est l’un des plus gros sujets encore ouverts au niveau “expertise pro”.

---

## 6. Recommandations de niveau expert

## 6.1 Direction stratégique
Ne pas refondre brutalement le backtest.

La bonne stratégie est désormais :
1. **stabiliser les contrats de fidélité** ;
2. **mesurer les écarts** ;
3. **durcir les zones encore approximatives** ;
4. **figer des fenêtres de référence**.

## 6.2 Principe directeur
Le backtest doit évoluer d’un moteur “riche et configurable” vers un système capable de répondre à trois questions :
- qu’a-t-on relu vs recalculé ?
- pourquoi le résultat diffère-t-il du live ?
- cette divergence est-elle acceptable, expliquée et stable ?

---

## 7. Plan d’exécution par sprint

## Sprint 1 — Fidélité observable par composant
### Objectif
Rendre le manifeste de fidélité actionnable pour l’exploitation et le debug.

### Livrables
- granularité par composant : bars / scores / sentiment / ML / walk-forward / risk / execution ;
- listes de symboles manquants normalisées ;
- causes de dégradation normalisées ;
- compatibilité `report.json` / IHM.

### Tâches
- enrichir `fidelity.py` avec une taxonomie stricte des motifs ;
- ajouter un bloc “coverage” structuré pour sentiment et ML ;
- préparer un résumé exploitable côté IHM.

### Critères d’acceptation
- aucun fallback critique n’est silencieux ;
- on peut identifier immédiatement quels symboles dégradent un run.

## Sprint 2 — Convergence PIT amont 3→10
### Objectif
Mieux aligner le replay des entrées critiques avec le pipeline réel.

### Livrables
- contrat clair de provenance pour scores / sentiment / prédictions ;
- delta explicite entre persisté et reconstruit ;
- fenêtre courte de replay diagnostique.

### Tâches
- formaliser la provenance des snapshots selector/modelFactory ;
- distinguer “prediction manquante”, “modèle absent”, “artefact invalide” ;
- journaliser les écarts sur une fenêtre courte.

### Critères d’acceptation
- un run peut expliquer précisément pourquoi une ligne n’a pas de couverture ML/sentiment.

## Sprint 3 — Convergence candidate → target
### Objectif
Verrouiller la parité métier entre replay de conviction et cibles `risk_management`.

### Livrables
- contrat unique `score_source / score_used / conviction_source` ;
- comparaison déterministe entre `signal_replay` et `risk_bridge` ;
- artefacts d’écart ciblés.

### Tâches
- centraliser encore davantage la logique de score/conviction ;
- exposer les motifs de rejet risk dans le rapport backtest ;
- comparer systématiquement les tops candidats et targets produits.

### Critères d’acceptation
- toute divergence entre replay research et branchage risk réel est mesurable et attribuable.

## Sprint 4 — Exécution broker-like enrichie
### Objectif
Rapprocher le lifecycle simulé de la sémantique broker réelle.

### Livrables
- états ordres enrichis (partial / canceled / retry / stale) ;
- simulation plus riche des protections ;
- meilleure cohérence des fills et OCO.

### Tâches
- enrichir `execution_replay.py` ;
- rapprocher les transitions du watcher et des exits ;
- préparer une matrice d’écart fills/backtest vs fills/live.

### Critères d’acceptation
- un lifecycle d’ordre complexe reste lisible et stable dans les artefacts.

## Sprint 5 — Compare-to-live professionnel
### Objectif
Construire un rapport canonique de divergence backtest ↔ live.

### Livrables
- comparateur structuré : candidats / targets / intents / fills / exits / PnL ;
- score de fidélité ;
- top divergences classées.

### Tâches
- définir les clés de matching ;
- produire un JSON + Markdown lisible IHM ;
- intégrer les métriques de confiance.

### Critères d’acceptation
- sur un run de référence, le rapport met en évidence les divergences majeures sans investigation SQL manuelle.

## Sprint 6 — Baselines de non-régression fidélité
### Objectif
Empêcher toute régression silencieuse du niveau de fidélité.

### Livrables
- catalogue versionné `config/fidelity_baseline_catalog.json` ;
- snapshot canonique de run `fidelity_baseline_snapshot.json` ;
- comparatif `fidelity_baseline_comparison.json` + `fidelity_baseline_comparison_checks.csv` ;
- seuils de divergence acceptables par métrique ;
- tests automatiques de fidélité + cohérence IHM.

### Tâches
- figer des snapshots représentatifs ;
- écrire des tests de dérive max ;
- exposer les options baseline dans la CLI et l’IHM ;
- documenter la procédure de promotion d’une baseline.

### Critères d’acceptation
- une régression de fidélité devient détectable automatiquement en CI/local ;
- l’IHM reste compatible historique et affiche passivement les nouveaux artefacts lorsqu’ils sont présents.

---

## 8. Priorisation recommandée

Ordre conseillé :
1. Sprint 1
2. Sprint 3
3. Sprint 2
4. Sprint 5
5. Sprint 4
6. Sprint 6

### Pourquoi
- il faut d’abord améliorer la lisibilité de la fidélité ;
- puis verrouiller la cohérence score → target ;
- ensuite enrichir les causes amont ;
- puis construire la comparaison live ;
- seulement après raffiner encore l’exécution ;
- enfin figer les baselines.

---

## 9. Actions immédiates recommandées après cette passe

### Déjà traité maintenant
- logs explicites des symboles sans couverture sentiment / ML ;
- réalignement de la source de score utilisée par le bridge Phase 2 risk.
- taxonomie normalisée des motifs de dégradation dans `backtesting/fidelity.py` ;
- granularité par composant dans le manifeste (`bars`, `scores`, `sentiment`, `ml`, `walk_forward`, `risk`, `execution`) ;
- bloc `coverage` structuré pour sentiment / ML avec ratios, compteurs et listes de symboles ;
- artefact `coverage_summary.json` produit à chaque run avec `output_dir` ;
- résumé de fidélité affichable côté `ihm/pages/backtesting/__init__.py` sans casser le contrat racine de `report.json` ;
- tests ciblés ajoutés sur le manifeste Sprint 1, les artefacts et le rendu IHM.
- test de non-régression `signal_replay` vs `risk_bridge` ajouté sur plusieurs cascades de score (`auto`, `final_score_sentiment`, `final_score`) ;
- premier slice Sprint 2 livré avec bloc `provenance` pour `scores`, `sentiment` et `ml` ;
- normalisation des causes ML manquantes : `prediction_missing`, `artifact_missing`, `artifact_invalid`, `rebuild_unavailable` ;
- résumé IHM enrichi pour afficher la provenance et les causes ML normalisées.

### Clôture Sprint 1 — état réel après implémentation
Le Sprint 1 est **livré sur son axe principal**, avec un périmètre volontairement additif et compatible avec l’existant.

#### Livré
- `report.json[fidelity]` enrichi avec :
  - `taxonomy_version` ;
  - `degraded_reason_details` ;
  - `coverage` ;
  - `component_status` ;
  - `summary.enabled_components / degraded_components`.
- `fidelity_manifest.json` aligné sur ce contrat enrichi.
- `coverage_summary.json` ajouté comme artefact structuré dédié exploitation/debug.
- `backtesting/cli/_impl.py` alimente désormais des détails composant pour :
  - `bars` (fenêtre chargée, warm-up, cardinalités) ;
  - `risk` (activation + diagnostics bridge) ;
  - `execution` (activation + diagnostics phases 2/3/4/5/7).
- l’IHM backtesting affiche désormais un résumé de fidélité du run :
  - statut PIT ;
  - run dégradé ou non ;
  - vue composant par composant ;
  - coverage sentiment / ML ;
  - motifs normalisés.

#### Vérification de cohérence IHM
- le contrat a été gardé **strictement additif** dans `report.json` ;
- aucune nouvelle clé racine n’a été introduite ;
- l’IHM continue à lire `report.json` et peut ignorer les nouveaux sous-blocs si absents ;
- `coverage_summary.json` reste un artefact complémentaire, la source principale pour l’IHM demeurant `report.json[fidelity]`.

#### Limites encore ouvertes après Sprint 1
- la granularité reste principalement **au niveau run**, pas encore par séance complète ;
- le détail ML ne distinguait pas encore finement `prediction_missing` / `artifact_missing` / `artifact_invalid` avant l’ouverture du slice Sprint 2 ;
- la matrice explicite `persisté / reconstruit / fallback / absent` n’est pas encore formalisée par symbole ;
- l’IHM expose un résumé opérateur utile, mais pas encore une navigation analytique avancée composant ↔ symbole ↔ séance.

### Clôture Sprint 2 — état réel après cette passe
Le Sprint 2 est désormais **clos sur son périmètre opérationnel principal**, avec un contrat additif, testable et exploitable côté backtest + IHM.

#### Livré dans ce slice Sprint 2
- ajout d’un bloc `provenance` additif dans `report.json[fidelity]`, `fidelity_manifest.json` et `coverage_summary.json` ;
- provenance explicitée pour :
  - `scores` : source PIT historisée vs fallback snapshot courant ;
  - `sentiment` : persisté / rebuild snapshot / fallback `final_score` / overlay walk-forward ;
  - `ml` : persisté / rebuild / manquants résiduels + stratégie effective.
- enrichissement des diagnostics ML avec :
  - `missing_cause_breakdown` ;
  - `missing_causes_by_symbol`.
- première normalisation opératoire des causes ML :
  - `prediction_missing` ;
  - `artifact_missing` ;
  - `artifact_invalid` ;
  - `rebuild_unavailable`.
- compatibilité IHM vérifiée :
  - ajout d’une vue `Provenance Sprint 2 — scores / sentiment / ML` ;
  - ajout d’une vue `Causes ML normalisées` ;
  - contrat conservé additif, sans nouvelle clé racine.
- ajout d’un artefact de replay diagnostique court par séance :
  - `replay_diagnostic_summary.json` (canonique, orienté debug) ;
  - `replay_diagnostic_sessions.csv` (aplati, lisible rapidement) ;
  - résumé par `trade_date` de la couverture score/sentiment/ML, des sélections et des sources de score.
- enrichissement du replay diagnostique court avec :
  - `degraded_components` par séance ;
  - `component_attribution` par séance ;
  - `critical_symbol` et `critical_symbols` ;
  - `provenance_refs` (snapshot scores, runs ML, refs risk/execution lorsque disponibles).
- compatibilité IHM vérifiée aussi pour cet artefact :
  - ajout d’une vue `Replay diagnostique court par séance` ;
  - lecture passive depuis `report.json[artifacts]` ;
  - aperçu enrichi avec composants dégradés, symbole critique et référence de provenance ;
  - aucun impact sur les rapports historiques dépourvus de cet artefact.

#### Critères Sprint 2 désormais couverts
- un run peut expliciter la provenance de ses entrées critiques (`scores`, `sentiment`, `ML`) ;
- un run peut distinguer les principales causes ML manquantes (`prediction_missing`, `artifact_missing`, `artifact_invalid`, `rebuild_unavailable`) ;
- un opérateur peut repérer par séance quels composants sont dégradés et quel symbole est le plus critique ;
- l’IHM peut consommer ces informations sans rupture de contrat.

#### Limites résiduelles après clôture Sprint 2
- le contrat amont `selector snapshot id / model run id / artifact lineage id` reste encore partiellement implicite selon les sources disponibles ;
- le replay diagnostique court reste un résumé compact, pas encore un journal exhaustif d’attribution live/backtest ;
- la distinction fine des cas ML repose encore partiellement sur l’état runtime du predictor, donc utile mais encore best-effort ;
- l’attribution détaillée par date-clé reste à approfondir si l’objectif devient une comparaison live/backtest complète.

### Clôture Sprint 3 — état réel après cette passe
Le Sprint 3 est désormais **clos sur son incrément prioritaire de convergence `candidate -> target`**, avec des artefacts de parité, des champs de contrat explicites et un affichage IHM passif compatible.

#### Livré dans ce Sprint 3
- contrat plus explicite `score_source / score_used / conviction_source` sur les signaux research et les signaux phase2 risk ;
- enrichissement des signaux phase2 avec :
  - `conviction_score` ;
  - `conviction_source` ;
  - `predicted_proba` ;
  - `decision_reason_code`.
- ajout d’un artefact dédié de parité `candidate -> target` :
  - `candidate_target_parity_summary.json` ;
  - `candidate_target_parity_sessions.csv`.
- ajout d’un premier artefact canonique `compare-to-live` strictement additif :
  - `compare_to_live_summary.json` ;
  - `compare_to_live_sessions.csv` ;
  - `compare_to_live_summary.md`.
- comparaison systématique par séance entre :
  - candidats research retenus ;
  - targets risk effectivement acceptés ;
  - cibles rejetées avec motifs ;
  - symboles `research_only` / `risk_only`.
- comptage des rejets risk par `decision_reason_code` ;
- exposition passive côté IHM avec une vue `Parité candidate → target`.

#### Critères Sprint 3 désormais couverts
- la parité `signal_replay` vs `risk_bridge` sur la cascade de score est verrouillée par test ;
- les divergences `candidate -> target` sont mesurables par séance ;
- les motifs de rejet risk deviennent visibles dans un artefact structuré ;
- l’IHM peut consulter ce comparatif sans rupture de contrat historique.

#### Limites résiduelles après clôture Sprint 3
- le comparatif reste un résumé de parité et non encore une attribution causale exhaustive de tous les écarts live/backtest ;
- les écarts `research_only` / `risk_only` sont identifiés, mais pas encore reliés à une hiérarchie métier consolidée de gravité ;
- la convergence `candidate -> target` est maintenant observable, mais pas encore reliée à une fenêtre `compare-to-live` réelle.

### Clôture Sprint 4 — état réel après cette passe
Le Sprint 4 est désormais **livré sur un slice broker-like additif et exploitable**, centré sur la lisibilité du lifecycle d’ordre Phase 3 → 7, sans casser les contrats historiques de `report.json`, des CSV déjà produits ni les vues IHM existantes.

#### Livré dans ce Sprint 4
- ajout d’un **journal canonique broker-like** commun aux phases 3/4/5/7 avec :
  - `intent_id` parent / enfants ;
  - `order_group_id` ;
  - `oco_group_id` ;
  - `intent_role` ;
  - `order_status` ;
  - `broker_state` ;
  - `state_reason` ;
  - dates d’activation / terminaison.
- enrichissement des signaux Phase 3/4/7 avec des champs additifs de lifecycle :
  - entrée : `entry_intent_id`, `entry_broker_order_id`, `entry_order_status`, `order_group_id`, `oco_group_id` ;
  - protections : `replay_*_intent_id`, `replay_*_order_status`, `replay_oco_group_id` ;
  - exit terminal : `replay_exit_intent_id`, `replay_exit_order_status`, `replay_canceled_sibling_intent_ids`.
- sémantique broker-like explicitée sur les états aujourd’hui réellement simulés :
  - `filled` ;
  - `working` ;
  - `held` ;
  - `canceled` ;
  - `stale`.
- transition watcher enrichie :
  - `PROTECTION_TRIGGER_HIT` ;
  - `PROTECTION_TRANSITION_COMPLETED` ;
  - annulation explicite du `initial_stop` quand le trailing devient actif.
- clôture terminale enrichie en Phase 7 :
  - fill explicite de l’ordre enfant qui gagne ;
  - annulation OCO des frères encore actifs ;
  - marquage `stale` / `EXPIRED` des protections restées ouvertes en fin de fenêtre.
- ajout d’artefacts Sprint 4 communs et additifs, réécrits au fil des phases pour refléter l’état le plus riche atteint par le run :
  - `execution_broker_like_order_lifecycle.csv` ;
  - `execution_broker_like_events.csv` ;
  - `execution_broker_like_summary.json`.
- résumé broker-like injecté aussi dans les détails de fidélité composant `execution` pour rester visible côté `report.json[fidelity]`.

#### Cohérence IHM vérifiée
- l’IHM backtesting reste **passive et compatible historique** :
  - aucun artefact racine existant n’est renommé ;
  - aucune clé racine nouvelle n’est imposée dans `report.json` ;
  - la nouvelle vue n’apparaît que si `execution_broker_like_summary.json` est présent.
- ajout d’une vue dédiée `Exécution broker-like enrichie` avec :
  - compteurs d’ordres `filled / canceled / stale` ;
  - aperçu par séance ;
  - consultation du payload brut pour debug exploitation.
- les runs historiques dépourvus de cet artefact continuent à s’afficher sans rupture.

#### Critères Sprint 4 désormais couverts sur ce slice
- un lifecycle d’ordre complexe reste **lisible** dans les artefacts ;
- les transitions watcher / exits / annulations OCO deviennent **attribuables** ;
- les protections restées ouvertes en fin de fenêtre sont **explicitement marquées `stale`** ;
- les artefacts sont **cohérents avec l’IHM** et réutilisables par les analyses futures `compare-to-live`.

#### Incrément logique Sprint 4 livré ensuite — `partial fills + retries synthétiques`
- enrichissement de `phase3_execution_replay` avec une simulation **déterministe et additive** de fills d’entrée multi-tentatives :
  - premier fill partiel synthétique ;
  - resoumission synthétique du reliquat ;
  - complétion finale dans la même séance de replay ;
  - conservation d’un `filled_qty` final agrégé côté signaux pour rester compatible avec les phases aval.
- extension du journal broker-like avec colonnes additives :
  - `attempt_no` ;
  - `cumulative_filled_qty` ;
  - `remaining_qty` ;
  - `synthetic_partial_fill` ;
  - `synthetic_retry` ;
  - `retry_reason`.
- enrichissement des événements broker-like avec comptage explicite des :
  - `ORDER_PARTIALLY_FILLED` ;
  - retries synthétiques ;
  - quantités cumulées / restantes par tentative.
- enrichissement additif des signaux Phase 3 avec :
  - `entry_attempt_count` ;
  - `entry_partial_fill_count` ;
  - `entry_retry_count`.
- durcissement Phase 4 pour agréger correctement plusieurs fills d’un même `intent_id` avant de calculer les protections/triggers.
- cohérence IHM revalidée et enrichie côté `Exécution broker-like enrichie` :
  - nouveaux compteurs `Partial fills` / `Retries` ;
  - nouvelles colonnes par séance `Partial fills`, `Retries`, `Partial fill events`, `Retry events` ;
  - compatibilité préservée pour les anciens payloads ne contenant pas ces clés.

#### Clôture effective du reste du Sprint 4 — `annulations intermédiaires explicites + retry taxonomy reject/timeout/resubmit`
- enrichissement de la taxonomie broker-like Phase 3 avec une chaîne synthétique plus réaliste pour les entrées volumineuses :
  - `partial fill` ;
  - annulation explicite du reliquat (`ORDER_CANCELED`) ;
  - premier `resubmit` rejeté (`ORDER_REJECTED`) ;
  - second `resubmit` expiré / timeout (`ORDER_TIMEOUT`) ;
  - dernier `resubmit` exécuté (`ORDER_FILLED`).
- conservation du contrat aval existant :
  - les phases 4/5/7 continuent de consommer les **fills effectivement réussis** ;
  - la quantité finale reste agrégée dans `signals_df[filled_qty]` ;
  - aucune rupture sur les artefacts historiques ni sur `report.json`.
- extension additive du journal `execution_broker_like_order_lifecycle.csv` avec :
  - `attempt_outcome` ;
  - `resubmit_of_attempt_no` ;
  - `resubmit_chain_id` ;
  - `synthetic_cancel` ;
  - `synthetic_reject` ;
  - `synthetic_timeout`.
- extension additive du flux `execution_broker_like_events.csv` avec la même taxonomie d’issue par tentative.
- enrichissement additif des signaux Phase 3 avec des compteurs dédiés :
  - `entry_resubmit_count` ;
  - `entry_cancel_count` ;
  - `entry_reject_count` ;
  - `entry_timeout_count` ;
  - `entry_retry_chain_id`.
- résumé broker-like enrichi avec compteurs globaux et par séance pour :
  - `rejected_orders` ;
  - `timed_out_orders` ;
  - `cancel_events` ;
  - `reject_events` ;
  - `timeout_events`.
- cohérence IHM revalidée une nouvelle fois :
  - ajout passif des métriques `Ordres rejetés` et `Ordres timeout` ;
  - ajout dans le tableau par séance des colonnes `Rejected`, `Timed out`, `Cancel events`, `Reject events`, `Timeout events` ;
  - les anciens payloads continuent à s’afficher correctement car toutes les nouvelles clés restent optionnelles.

#### Limites résiduelles après ce Sprint 4
- la granularité reste encore **synthétique/backtest** et non issue d’observations broker persistées réelles ;
- la taxonomie `reject -> timeout -> resubmit` est désormais présente, mais elle reste **déterministe et simplifiée** (pas encore de backoff temporel paramétrable, de throttling, ni d’erreurs broker contextualisées) ;
- les prix de fills multi-tentatives restent volontairement simples dans ce slice et n’essaient pas encore de reproduire une microstructure intraday riche ;
- les annulations/rejets/timeouts simulés restent centrés sur les **ordres d’entrée** ; les protections enfant Phase 4→7 ne simulent pas encore une taxonomie broker complète du même niveau ;
- le rapprochement avec le live exploite désormais de meilleures clés de lifecycle, mais la matrice complète `fills/backtest vs fills/live` multi-tentatives reste encore à approfondir.

### Clôture Sprint 5 — état réel après cette passe
Le Sprint 5 est maintenant **livré sur un slice étendu et directement exploitable dans l'IHM**, avec un matching live plus robuste par `risk_run_id` / `exec_run_id` quand ces identifiants sont disponibles.

#### Livré dans ce slice Sprint 5
- ajout d’un rapport additif `compare-to-live` produit à côté des autres artefacts de run ;
- conservation stricte du contrat racine de `report.json` :
  - aucune nouvelle clé racine ;
  - références d’artefacts uniquement via `report.json[artifacts]` ;
- comparaison par séance sur quatre niveaux :
  - `candidates` : sélection research vs symboles effectivement retenus côté `risk_decisions` live ;
  - `risk_decisions` : décisions backtest Phase 2 vs décisions live persistées ;
  - `portfolio_targets` : targets backtest vs `portfolio_targets` live ;
  - `execution_targets` : targets d’exécution backtest vs `execution_targets_snapshot` live (dernier run du jour) ;
- ajout d’un score global de fidélité et de scores par niveau ;
- durcissement du matching live côté exécution :
  - tentative de résolution du `exec_run_id` live via le `risk_run_id` provenant de `risk_decisions` ;
  - fallback explicite sur le dernier `execution_run` du jour si le matching par run n’est pas disponible ;
- réalignement plus fin du matching live côté risk :
  - rechargement best-effort des `risk_decisions` au `risk_run_id` exact quand il est disponible ;
  - chargement des `portfolio_targets` live au `risk_run_id` exact avant fallback daté ;
  - enrichissement additif du `matching_context` avec la base réellement utilisée pour `risk_decisions` et `portfolio_targets`.
- extension du rapport `compare-to-live` aux couches lifecycle suivantes :
  - `fills` : fills d’entrée replay vs `execution_broker_fills` live du run d’exécution matché ;
  - `exits` : exits replay vs lots live clos issus du `open_exec_run_id` matché ;
  - `pnl` : PnL réalisé replay vs PnL réalisé live reconstruit depuis `execution_position_lots` ;
- durcissement de robustesse sur les sections lifecycle :
  - normalisation des timestamps timezone-aware pour éviter les faux `missing_replay` sur les fills rejoués ;
  - inférence robuste des actions `BUY/SELL` depuis `side` côté live ;
  - inférence des quantités comparables depuis `filled_qty` / `closed_qty` lorsque `approved_shares` n’existe pas ;
  - compatibilité durcie avec `pd.NA` sur l’agrégation des sections `fills / exits / PnL`.
- ajout d’un `matching_context` par séance dans le payload pour exposer :
  - `risk_run_id` live retenu ;
  - `exec_run_id` live retenu ;
  - `match_basis` (`risk_run_id` vs fallback daté) ;
- extraction des top divergences ordonnées par séance / composant / symbole ;
- export triple :
  - JSON canonique pour automatisation ;
  - CSV aplati pour lecture rapide ;
  - Markdown synthétique pour revue humaine ;
- IHM backtesting enrichie en mode passif avec une vue `Compare-to-live professionnel`.
- cohérence IHM vérifiée et prolongée :
  - nouvelles colonnes `Fills live`, `Exits live`, `PnL live` dans l’aperçu tabulaire ;
  - chargement passif inchangé depuis `report.json[artifacts]` ;
  - compatibilité conservée pour les runs historiques sans artefact Sprint 5.

#### Critères Sprint 5 désormais couverts sur ce slice
- lorsqu’un historique live comparable existe, le run peut produire un rapport unique sans investigation SQL manuelle ;
- les divergences majeures candidates / risk / targets / execution targets / fills / exits / PnL deviennent visibles et triées ;
- le matching live n’est plus seulement journalier : il utilise le couple `risk_run_id` / `exec_run_id` quand possible ;
- les `portfolio_targets` et, best-effort, les `risk_decisions` sont désormais réalignés sur le `risk_run_id` exact quand ce contexte est disponible ;
- les sections `fills / exits / PnL` résistent mieux aux schémas live hétérogènes (timestamps timezone-aware, quantités/fills non exprimés sous `approved_shares`) ;
- l’IHM peut charger ce rapport sans casser les runs historiques dépourvus de cet artefact.

#### Limites résiduelles après ce slice Sprint 5
- les sections `fills / exits / PnL` restent best-effort et dépendent de la disponibilité des tables live `execution_broker_fills` et `execution_position_lots` ;
- le matching multi-comptes / multi-runs parallèles reste centré sur `account_id=default` dans l’intégration CLI actuelle ;
- le score global de fidélité reste volontairement simple et agrégatif ; il n’est pas encore pondéré par la gravité métier ou l’impact économique ;
- l’attribution causale détaillée des écarts broker (retries, partial fills complexes, annulations intermédiaires) peut encore être approfondie au-delà du résumé actuel.
- le réalignement `risk_decisions` sur `risk_run_id` reste best-effort et dépend des traces effectivement persistées dans les tables live ; en cas de vide, le fallback daté demeure actif.

### Prochaines actions à lancer sans attendre
1. Pondérer le score global par gravité métier / impact exécution pour éviter un score trop purement structurel.
2. Ajouter une vue IHM plus analytique (drill-down par composant puis symbole) si l’usage opérateur le justifie.
3. Étendre le lifecycle broker-like aux cas plus complexes encore ouverts (annulations intermédiaires explicites, rejects/timeouts/retries plus réalistes, reconciliations manuelles, positions adoptées).
4. Promouvoir maintenant 2 à 3 snapshots réels dans `artifacts/fidelity_baselines/...` pour alimenter le catalogue Sprint 6 avec des références live/backtest effectives.

### Clôture Sprint 6 — état réel après cette passe
Le Sprint 6 est maintenant **livré sur un premier slice complet et additif**, centré sur la mise en place des baselines de non-régression fidélité sans casser les runs historiques ni le contrat racine de `report.json`.

#### Livré dans ce Sprint 6
- ajout d’un **snapshot canonique de fidélité** produit à chaque run structuré :
  - `fidelity_baseline_snapshot.json` ;
  - métriques compactes dérivées de `fidelity_manifest`, `replay_diagnostic_summary`, `candidate_target_parity_summary`, `compare_to_live_summary` et `execution_broker_like_summary` quand disponibles ;
  - conservation d’un format volontairement compact, stable et promouvable en baseline.
- ajout d’un **comparatif baseline** opt-in :
  - `fidelity_baseline_comparison.json` ;
  - `fidelity_baseline_comparison_checks.csv` ;
  - checks exacts sur la fenêtre et la chaîne de phases ;
  - checks numériques avec tolérances `min` / `max` / `abs`.
- ajout d’un **catalogue versionné** dans `config/fidelity_baseline_catalog.json` avec plusieurs entrées de référence et leurs seuils métier initiaux.
- ajout des nouveaux flags CLI `run` :
  - `--fidelity-baseline-id` ;
  - `--fidelity-baseline-catalog`.
- enrichissement du contrat IHM / runner avec ces deux options, propagées dans `BacktestRunOptions` puis dans la commande réellement lancée.
- ajout de vues IHM passives et compatibles historique pour :
  - `Snapshot baseline fidélité (Sprint 6)` ;
  - `Non-régression fidélité vs baseline` ;
  - avec lecture passive depuis `report.json[artifacts]` comme pour les autres artefacts additifs.
- ajout de tests ciblés sur :
  - le snapshot canonique ;
  - la comparaison baseline via catalogue JSON ;
  - le parsing CLI ;
  - le runner IHM ;
  - les helpers tabulaires IHM.

#### Cohérence IHM vérifiée
- aucune nouvelle clé racine n’est imposée dans `report.json` ;
- les nouveaux artefacts restent strictement référencés via `report.json[artifacts]` ;
- les runs historiques sans artefacts Sprint 6 continuent de s’afficher normalement ;
- l’IHM expose seulement les nouveaux blocs si les artefacts correspondants existent.

#### Critères Sprint 6 désormais couverts sur ce slice
- un run structuré produit désormais une base canonique promouvable pour la non-régression fidélité ;
- une comparaison baseline peut être exécutée automatiquement en local/CI dès lors qu’un catalogue + snapshot promu existent ;
- les dérives sur la fenêtre, la chaîne de phases ou les métriques clés deviennent visibles dans un artefact structuré ;
- l’IHM reste cohérente avec ce nouveau contrat additif.

#### Limites résiduelles après ce Sprint 6
- le dépôt contient pour l’instant surtout le **mécanisme** et un **catalogue d’entrée** ; les snapshots réellement promus doivent encore être produits depuis des runs de référence ;
- les seuils initiaux sont prudents et devront être recalibrés après observation de fenêtres live plus nombreuses ;
- la comparaison reste compacte : elle vise la détection de dérive, pas encore l’explication causale exhaustive de chaque point d’écart.

---

## 10. Conclusion

Le backtest a **franchi un cap important** : il n’est plus seulement un moteur de recherche, mais déjà une base sérieuse pour une convergence live/backtest.

La priorité n’est plus une refonte générale.
La priorité est maintenant :
- **rendre les écarts explicables** ;
- **stabiliser les contrats inter-modules** ;
- **industrialiser la comparaison au live** ;
- **verrouiller les baselines de fidélité**.

C’est cette trajectoire qui amènera le module au niveau “professionnel / expertise” attendu pour l’exploitation durable du système.


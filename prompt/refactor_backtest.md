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
- 3 à 5 fenêtres de référence ;
- seuils de divergence acceptables ;
- tests automatiques de fidélité.

### Tâches
- figer des snapshots représentatifs ;
- écrire des tests de dérive max ;
- documenter la procédure de promotion d’une baseline.

### Critères d’acceptation
- une régression de fidélité devient détectable automatiquement en CI/local.

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

### Clôture partielle Sprint 2 — état réel après cette passe
Le Sprint 2 n’est **pas entièrement clos**, mais un incrément utile et testable a été livré.

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
- compatibilité IHM vérifiée aussi pour cet artefact :
  - ajout d’une vue `Replay diagnostique court par séance` ;
  - lecture passive depuis `report.json[artifacts]` ;
  - aucun impact sur les rapports historiques dépourvus de cet artefact.

#### Ce que ce slice Sprint 2 ne couvre pas encore complètement
- pas encore de contrat amont standardisé `selector snapshot id / model run id / artifact lineage id` ;
- le replay diagnostique court existe désormais, mais reste un résumé compact et non encore un journal d’attribution complet par composant + symbole + séance ;
- la distinction fine des cas ML reste basée sur l’état runtime du predictor, donc utile mais encore best-effort ;
- l’attribution des écarts reste principalement orientée run et symbole, pas encore complète par date-clé.

### Prochaines actions à lancer sans attendre
1. Formaliser un identifiant de provenance amont pour snapshots selector / runs modelFactory / artefacts de rebuild.
2. Enrichir le replay diagnostique court avec une attribution plus riche par composant / symbole critique / séance.
3. Préparer une première fenêtre `compare-to-live` courte sur un run réel récent.
4. Étendre le contrat de couverture vers une matrice par symbole / par séance si le besoin opérateur se confirme.

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


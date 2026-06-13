# Plan de transformation **long + short avec ML**

_Date : 2026-06-13_

## Checklist

- [x] Lire le code source existant côté short hors ML
- [x] Revoir l’architecture ML actuelle (features, target, entraînement, calibration, ranking, persistance, replay)
- [x] Identifier les hypothèses bullish / long-only
- [x] Définir une architecture cible long + short avec ML
- [x] Détailler les impacts backtest + pipeline live + ML
- [x] Proposer un plan de sprint complet et séquencé

---

## 1. Objet du document

Ce document complète `prompt/short/plan.md`.

Le premier plan couvrait l’intégration du **short hors ML**.
Celui-ci traite la **transformation complète de l’application en long + short avec Machine Learning**, donc :

- génération des signaux directionnels ;
- entraînement et calibration des modèles ;
- persistance des prédictions ;
- fusion ML + score quant + régime ;
- risk management ;
- backtest ;
- pipeline live ;
- reporting et gouvernance.

L’objectif n’est pas seulement de “rajouter des shorts”, mais de faire évoluer l’application d’une logique :

- **bullish / long-only / top-N descendant**

vers une logique :

- **directionnelle / long-short / allocation bilatérale / ML aware**.

---

## 2. Résumé exécutif

## 2.1 Conclusion principale

Le système actuel est **doublement long-only** :

1. **métier / exécution** : les positions, protections, PnL et contraintes sont conçus pour des achats ;
2. **ML / sélection** : les labels, probabilités, métriques et classements sont conçus pour **détecter des gagnants à l’achat**, pas pour arbitrer entre long, neutre et short.

Autrement dit, intégrer le short avec ML impose une transformation de **deux chaînes à la fois** :

- la chaîne **trading / OMS / backtest / reporting** ;
- la chaîne **data science / target / modèle / calibration / ranking / gouvernance**.

## 2.2 Ce qui est déjà réutilisable

Des briques existent déjà et peuvent servir de base :

- `execution_engine.models.ExecutionTarget.side` existe déjà ;
- `execution_engine.models.ExecutionPosition.net_qty` est signé ;
- `execution_engine.reconciliation` est partiellement compatible avec des quantités signées ;
- `risk_management.db_io.load_account_equity_breakdown()` distingue déjà long/short côté snapshots broker ;
- `modelFactory.model.LSTMAttentionClassifier` supporte déjà `num_classes`, même si tout l’écosystème autour est binaire ;
- la calibration existe déjà (`modelFactory.calibration.PlattCalibrator`) ;
- le replay des signaux et les backtests ont déjà une chaîne unifiée quant + ML + sentiment.

## 2.3 Ce qui bloque aujourd’hui

### Côté ML

- `modelFactory.features.build_target()` ne produit que des labels binaires ou pseudo-binaires (`binary`, `swing_cash`) ;
- `modelFactory.model.LSTMAttentionModule` utilise des métriques **binary** (`BinaryAccuracy`, `BinaryAUROC`, etc.) ;
- `modelFactory.evaluation` raisonne en `precision_long`, `recall_long`, `coverage_at_threshold` ;
- `core.conviction.compute_conviction()` fusionne un **score quant** et une **probabilité de hausse** ;
- `selector/ranking.py` trie en **descendant** sur `final_score` pour sortir des **meilleurs longs** ;
- `modelFactory/db_registry.py` persiste `predicted_proba`, `predicted_class`, `signal_label`, mais pas de direction canonique long/short.

### Côté trading

- `risk_management`, `backtesting`, `execution_engine` restent majoritairement long-only, comme documenté dans `prompt/short/plan.md`.

---

## 3. Lecture du code source : constats ML détaillés

## 3.1 Targets et labels actuels : bullish seulement

### Fichiers clés

- `modelFactory/features.py`
- `modelFactory/config.py`
- `modelFactory/target_optimization.py`
- `modelFactory/dataset.py`

### Constat

Dans `modelFactory/features.py`, `build_target()` ne supporte aujourd’hui que :

- `binary` :
  - `1` si rendement futur > `positive_threshold`
  - `0` sinon
- `swing_cash` :
  - `1` si rendement futur >= `positive_threshold`
  - `0` si rendement futur <= `negative_threshold`
  - `NaN` entre les deux

Cela veut dire qu’on apprend actuellement :

- “acheter ou ne pas acheter”,
- pas “acheter / ne rien faire / vendre à découvert”.

Dans `modelFactory/config.py`, `DataConfig.target_mode` n’accepte que :

- `binary`
- `swing_cash`

et `decision_threshold` est un **seuil unique** adapté à une probabilité binaire.

Dans `modelFactory/target_optimization.py`, le scoring de target repose encore sur :

- `pos_mask = target == 1`
- `neg_mask = target == 0`

Donc le moteur d’optimisation de target ne connaît pas de vraie **classe short**.

### Impact

Sans refonte de la target, tout short ML restera artificiel.
On pourrait bricoler un “short = score quant faible”, mais ce ne serait **pas** une application long+short ML complète.

---

## 3.2 Le modèle cœur est potentiellement extensible, mais tout l’écosystème est binaire

### Fichiers clés

- `modelFactory/model.py`
- `modelFactory/trainer.py`
- `modelFactory/calibration.py`
- `modelFactory/predictor.py`

### Constat

Dans `modelFactory/model.py` :

- `LSTMAttentionClassifier(..., num_classes=2)` existe déjà ;
- la tête de classification peut en théorie passer à `num_classes=3` ;
- la loss est `CrossEntropyLoss()`.

Le problème n’est donc pas le backbone réseau, mais tout ce qui l’entoure :

- métriques Lightning en `BinaryAccuracy`, `BinaryPrecision`, `BinaryRecall`, `BinaryAUROC` ;
- extraction de probabilité positive dans `modelFactory/predictor.py` via `_extract_positive_class_probability()` ;
- calibration `PlattCalibrator` fondée sur un **margin binaire** ;
- `margin_from_logits()` qui attend surtout une sortie binaire `[N,2]`.

### Impact

Le backbone LSTM n’est pas le goulot principal.
Le vrai chantier est de rendre cohérents :

- la sortie du modèle,
- les métriques d’entraînement,
- la calibration,
- la persistance,
- la consommation downstream.

---

## 3.3 La fusion quant + ML est actuellement une fusion “conviction long”

### Fichiers clés

- `core/conviction.py`
- `risk_management/portfolio_builder.py`
- `backtesting/signal_replay.py`
- `risk_management/ml_gate.py`

### Constat

`core.conviction.compute_conviction()` calcule :

- `score_weight * score_used + prediction_weight * predicted_proba`

Donc :

- le score quant est traité comme une force haussière ;
- la probabilité ML est une probabilité de hausse ;
- le résultat final est un **conviction score scalar long**.

Le replay backtest (`backtesting/signal_replay.py`) reproduit la même logique via `_vectorized_fuse()`.
Le `ml_gate` peut désactiver le ML en remettant :

- `score_weight = 1.0`
- `prediction_weight = 0.0`

mais toujours dans une logique **unidirectionnelle**.

### Impact

Pour du long+short complet, il faut remplacer la notion de “conviction scalaire long” par une notion plus riche, par exemple :

- score long,
- score short,
- conviction nette,
- certitude directionnelle,
- zone neutre.

---

## 3.4 Le ranking / selector est structurellement top-N long

### Fichiers clés

- `selector/ranking.py`
- `selector/factors.py`
- `risk_management/db_io.py`

### Constat

Le ranking actuel :

- normalise les composantes dans `[0,1]` ;
- calcule `final_score` ;
- trie **descendant** ;
- applique une neutralisation sectorielle ;
- sort les **meilleurs candidats longs**.

Il n’existe pas aujourd’hui :

- de shortlist short ;
- de `side` ;
- de ranking bilatéral ;
- de logique “meilleurs longs + meilleurs shorts”.

Même les facteurs techniques sont pensés dans une logique bullish / momentum / breakout, pas “bullish and bearish symmetry”.

### Impact

Le ranking devra devenir un composant **directionnel**.
Ce n’est pas juste un ajout de colonne `side` : il faut revoir la manière de classer les opportunités.

---

## 3.5 Les métriques ML et les seuils de décision sont orientés long

### Fichiers clés

- `modelFactory/evaluation.py`
- `tests/test_weights_calibration.py`
- `tests/test_run_ml_regime_ablation.py`

### Constat

Les métriques existantes parlent de :

- `precision_long`
- `recall_long`
- `coverage_at_threshold`
- `threshold_business_score`
- `metric_hit_rate` pour des signaux longs

Même les tests confirment cette lecture métier :

- “3 longs, 2 winners → 2/3” dans `tests/test_weights_calibration.py`
- les scripts d’ablation ML/régime comparent la contribution du ML en termes de perf globale, pas par direction.

### Impact

Tant que les métriques ne sont pas symétrisées, le tuning ML long+short sera biaisé.
Le système pourra sur-optimiser des signaux longs et dégrader les shorts sans le voir clairement.

---

## 3.6 La persistance ML ne transporte pas une direction canonique suffisante

### Fichiers clés

- `modelFactory/db_registry.py`
- `modelFactory/predictor.py`
- `execution_engine/db_io.py`
- `risk_management/db_io.py`

### Constat

`modelFactory/db_registry.py` exige notamment :

- `predicted_proba`
- `predicted_class`
- `signal_label`
- `decision_threshold`

Ce contrat est adapté à une prédiction binaire, mais insuffisant pour exprimer proprement :

- `long`
- `short`
- `flat`

ou encore :

- probabilité de long,
- probabilité de flat,
- probabilité de short,
- classe finale,
- confiance directionnelle.

### Impact

La couche de persistance ML devra être migrée, sinon on perdra l’information utile avant même le ranking ou le risk management.

---

## 4. Architecture cible recommandée pour le ML long + short

## 4.1 Représentation canonique recommandée

Je recommande de représenter la décision ML de manière **directionnelle explicite**, et non comme une simple probabilité scalaire de hausse.

### Contrat cible recommandé

Pour chaque symbole / date, le système ML doit pouvoir produire au minimum :

- `predicted_side`: `long | short | flat`
- `proba_long`
- `proba_flat`
- `proba_short`
- `predicted_side_confidence`
- `expected_return_long` (optionnel)
- `expected_return_short` (optionnel)
- `decision_policy_version`

### Pourquoi

- évite les hacks type “si proba < 0.3 alors short” ;
- rend la calibration et l’explicabilité beaucoup plus propres ;
- permet de construire un ranking bilatéral cohérent ;
- facilite les zones neutres et les garde-fous de churn.

---

## 4.2 Choix de formulation ML : recommandation

Il y a trois grandes options.

### Option A — Binaire inversé bricolé

- un modèle prédit la hausse ;
- si proba très faible, on interprète cela comme short.

#### Avantages
- mise en œuvre plus rapide.

#### Inconvénients
- fragile conceptuellement ;
- une faible proba de hausse n’est pas forcément une forte conviction short ;
- calibration et métriques peu propres.

### Option B — Classification ternaire (`long / flat / short`)

- cible en 3 classes ;
- modèle à 3 logits ;
- proba par classe ;
- classe gagnante = décision.

#### Avantages
- claire et cohérente ;
- bonne compatibilité avec le backbone actuel `CrossEntropyLoss` ;
- simple à persister et à expliquer.

#### Inconvénients
- calibration multi-classe à implémenter ;
- équilibre des classes potentiellement difficile.

### Option C — Double tête / double modèle (`long edge` et `short edge`)

- une sortie estime l’edge long ;
- une autre l’edge short ;
- la politique de décision tranche entre les deux et la zone flat.

#### Avantages
- meilleure asymétrie de marché ;
- permet des features / pertes / thresholds différents par côté ;
- probablement le meilleur design long terme.

#### Inconvénients
- plus complexe ;
- plus de dette de calibration et gouvernance.

### Recommandation

Pour une transformation complète mais pragmatique, je recommande :

## Phase 1 ML : **classification ternaire**

puis, si besoin plus tard :

## Phase 2 ML : **double tête long-edge / short-edge**

La classification ternaire est le meilleur compromis entre :

- clarté métier,
- coût d’implémentation,
- compatibilité avec l’infrastructure existante.

---

## 4.3 Target métier recommandée

### Cible ternaire proposée

À horizon `H` :

- `long` si `future_return >= long_threshold`
- `short` si `future_return <= -short_threshold`
- `flat` sinon

### Notes importantes

- `long_threshold` et `short_threshold` ne doivent **pas forcément** être symétriques ;
- les marchés étant asymétriques, il peut être rationnel d’exiger un short threshold plus strict ;
- cette zone centrale `flat` est cruciale pour éviter le churn.

### Effets dans le code

À étendre notamment dans :

- `modelFactory.features.build_target()`
- `modelFactory.config.DataConfig.target_mode`
- `modelFactory.target_optimization`
- `modelFactory.dataset`

---

## 4.4 Features : ne pas supposer la symétrie long/short

### Constat

Les features actuelles sont surtout construites pour des signaux de continuation / qualité / momentum.

### Recommandation

Ne pas partir du principe qu’un signal fort long peut être simplement inversé pour short.

### Couches de features à prévoir

#### A. Features communes

- momentum multi-horizon
- volatilité
- ATR
- volume / liquidité
- cross-sectional features
- contexte benchmark

#### B. Features spécifiques short

- accélération baissière
- gap down persistence
- weak bounce failure
- surperformance négative relative secteur / benchmark
- congestion sous résistances
- stress macro / VIX / regimes défensifs
- indicateurs de crowding / squeeze si disponibles plus tard

#### C. Features de sécurité short

- volatilité explosive
- spread / illiquidité
- petites capitalisations à éviter
- événements earnings proches

### Implication

Le plan long+short ML doit inclure un sprint de **feature engineering directionnel**, pas seulement un changement de label.

---

## 5. Transformation cible de la chaîne end-to-end

## 5.1 Chaîne cible

### Étape 1 — Data / feature layer

Le dataset produit :

- features communes
- features directionnelles
- target ternaire
- future returns alignés

### Étape 2 — Training / calibration

Le modèle apprend :

- `P(long)`
- `P(flat)`
- `P(short)`

Puis calibration multi-classe ou calibrations dérivées.

### Étape 3 — Prediction registry

La table de prédictions persiste :

- side prédit
- probas par classe
- confiance
- seuils / policy metadata

### Étape 4 — Selector / ranking

Le ranking construit :

- shortlist long
- shortlist short
- ranking séparé ou score net comparable

### Étape 5 — Risk management

Le risk engine consomme :

- opportunités long et short
- budgets séparés / caps bruts / caps nets
- règles de régime directionnelles

### Étape 6 — Backtest

Le simulateur ouvre et ferme longs et shorts de manière cohérente.

### Étape 7 — Live execution

L’OMS soumet entrées, protections et réconciliations par direction.

---

## 6. Impacts techniques détaillés par couche

## 6.1 DataConfig / target / dataset

### Fichiers impactés

- `modelFactory/config.py`
- `modelFactory/features.py`
- `modelFactory/target_optimization.py`
- `modelFactory/dataset.py`

### Changements à prévoir

- ajouter un `target_mode` de type :
  - `ternary`
  - éventuellement `dual_edge` plus tard
- ajouter des seuils explicites :
  - `target_long_threshold`
  - `target_short_threshold`
  - `neutral_band` si utile
- faire évoluer `build_target()` pour produire `{-1, 0, +1}` ou `{short, flat, long}` canonique
- adapter `target_optimization` pour scorer les targets sur des métriques par classe et non seulement trade rate / class balance binaire
- vérifier l’encodage du target dans les séquences PyTorch

### Risques

- classes déséquilibrées ;
- trop de `flat` si les seuils sont trop stricts ;
- trop de churn si la zone neutre est trop étroite.

---

## 6.2 Modèle et métriques d’entraînement

### Fichiers impactés

- `modelFactory/model.py`
- `modelFactory/trainer.py`
- `modelFactory/evaluation.py`
- tests associés

### Changements à prévoir

- passer les métriques de `Binary*` à des métriques multi-classes ou à des métriques custom par side ;
- logger au minimum :
  - précision long,
  - précision short,
  - recall long,
  - recall short,
  - confusion matrix,
  - balanced accuracy,
  - coverage par side,
  - profit proxy par side ;
- adapter la sélection de champion dans `trainer.py` si elle dépend implicitement de métriques bullish.

### Recommandation métier

Ne pas choisir le meilleur modèle uniquement sur une métrique statistique globale.
Il faut introduire un **business score long+short**, par exemple fondé sur :

- qualité long,
- qualité short,
- stabilité walk-forward,
- drawdown proxy,
- churn.

---

## 6.3 Calibration

### Fichiers impactés

- `modelFactory/calibration.py`
- `modelFactory/predictor.py`
- éventuels artefacts de calibration

### Constat

Le calibrateur actuel est un **Platt scaling binaire**.

### Options recommandées

#### Option simple v1

- calibrer deux marges dérivées :
  - marge long vs rest
  - marge short vs rest
- conserver `flat` comme classe résiduelle.

#### Option plus propre

- calibration multi-classe (temperature scaling multi-class, Dirichlet, ou softmax temperature).

### Recommandation

Pour limiter le coût du premier passage :

- **v1** : calibration one-vs-rest long et short ;
- **v2** : calibration multi-classe plus propre quand la chaîne est stabilisée.

---

## 6.4 Persistance des prédictions et schémas DB

### Fichiers impactés

- `modelFactory/db_registry.py`
- migrations Alembic pertinentes
- consommateurs aval (`predictor`, `risk_management`, `backtesting`)

### Changements à prévoir

Le registre de prédictions doit pouvoir stocker au minimum :

- `predicted_side`
- `proba_long`
- `proba_flat`
- `proba_short`
- `predicted_side_confidence`
- `decision_policy`
- `decision_threshold_long`
- `decision_threshold_short`
- `model_output_schema_version`

### Recommandation

Garder `predicted_proba` pour rétrocompatibilité éventuelle, mais la documenter comme :

- soit dépréciée,
- soit re-sémantisée explicitement.

Le mieux est d’introduire **une nouvelle version de schéma** plutôt que de surcharger silencieusement l’existant.

---

## 6.5 Ranking et selector directionnels

### Fichiers impactés

- `selector/ranking.py`
- `selector/factors.py`
- `risk_management/db_io.py`
- `backtesting/signal_replay.py`

### Recommandation d’architecture

Le selector ne doit plus sortir un seul top-N descendant.
Il doit produire l’un des deux modèles suivants.

### Modèle recommandé

#### Sortie bilatérale

- `long_candidates`
- `short_candidates`

avec pour chacun :

- score quant directionnel,
- score ML directionnel,
- conviction finale,
- rang intra-side.

### Deux stratégies possibles

#### A. Deux pipelines parallèles

- ranking long séparé,
- ranking short séparé.

#### B. Score net commun

- score signé sur une échelle commune,
- shortlist positive et négative.

### Recommandation

Commencer par **deux pipelines parallèles** :

- plus lisible ;
- plus contrôlable ;
- plus facile à gouverner.

---

## 6.6 Fusion conviction avec ML

### Fichiers impactés

- `core/conviction.py`
- `backtesting/signal_replay.py`
- `risk_management/portfolio_builder.py`

### Proposition cible

Remplacer la fusion scalaire par un schéma directionnel.

### Exemple conceptuel

- `conviction_long = fuse(score_long, proba_long, ...)`
- `conviction_short = fuse(score_short, proba_short, ...)`
- `net_conviction = conviction_long - conviction_short`
- `selected_side = argmax(conviction_long, conviction_short)` si l’écart dépasse une zone neutre

### Pourquoi

- évite de déduire le short comme “anti-long” ;
- permet des pondérations différentes par side plus tard.

---

## 6.7 Risk management long+short avec ML

### Fichiers impactés

- `risk_management/models.py`
- `risk_management/portfolio_builder.py`
- `risk_management/constraints.py`
- `risk_management/position_sizer.py`
- `risk_management/audit.py`
- `risk_management/db_io.py`
- `risk_management/cli.py`

### Impacts ML spécifiques

Le risk management devra maintenant arbitrer entre :

- opportunités long,
- opportunités short,
- budget total,
- budget par side,
- contraintes de régime.

### Recommandation

Ajouter explicitement :

- `max_long_positions`
- `max_short_positions`
- `max_long_gross_exposure`
- `max_short_gross_exposure`
- `max_net_exposure`
- `max_short_sector_exposure`
- `short_risk_multiplier`

### Sizing

Le sizing short ne doit pas forcément être égal au long.
Je recommande un multiplicateur séparé dès le début :

- `risk_per_trade_pct_long`
- `risk_per_trade_pct_short`

ou à défaut :

- `short_risk_multiplier < 1.0`

---

## 6.8 Backtest ML long+short

### Fichiers impactés

- `backtesting/signal_replay.py`
- `backtesting/risk_bridge.py`
- `backtesting/simulator.py`
- `backtesting/microstructure.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/exit_lifecycle_replay.py`
- `backtesting/report.py`
- `backtesting/fidelity.py`

### Impacts ML spécifiques

Le replay des signaux doit pouvoir rejouer :

- shortlist long,
- shortlist short,
- décisions flat,
- poids / convictions directionnels.

### Fidelity

La couche `backtesting/fidelity.py` devra comparer non seulement :

- présence / absence de prédictions,

mais aussi :

- cohérence de la direction,
- cohérence des probas par classe,
- cohérence du ranking par side.

### Métriques backtest à ajouter

- PnL long,
- PnL short,
- win rate long,
- win rate short,
- gross exposure long moyenne,
- gross exposure short moyenne,
- net exposure moyenne,
- contribution short aux drawdowns.

---

## 6.9 Pipeline live ML long+short

### Fichiers impactés

- `execution_engine/order_intents.py`
- `execution_engine/account_state.py`
- `execution_engine/executor.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/orphan_adoption.py`
- `execution_engine/reconciliation.py`
- `execution_engine/tca.py`
- `run_execution.py`

### Impacts ML spécifiques

Le live ne doit pas juste recevoir un `side`, mais aussi une **traçabilité du pourquoi ML**.

Je recommande que les targets et/ou intents persistés embarquent :

- `predicted_side`
- `predicted_side_confidence`
- `ml_policy_version`
- `ml_score_long`
- `ml_score_short`
- `selector_decision_reason`

### Pourquoi

- audit post-trade ;
- diagnostics en cas de dérive ;
- explication opérateur.

---

## 6.10 Régime de marché et ML directionnel

### Fichiers impactés

- `service/market/models.py`
- `risk_management/cli.py`
- `execution_engine/market_regime_preflight.py`
- `run_execution.py`
- `backtesting/risk_bridge.py`

### Recommandation

Le régime ne doit plus exposer seulement :

- `allow_new_entries: bool`

mais au minimum :

- `allow_long_entries: bool`
- `allow_short_entries: bool`
- `long_risk_multiplier`
- `short_risk_multiplier`
- `preferred_sides`

### Intérêt pour le ML

Le régime peut devenir un **contexte de décision** pour le modèle et/ou le policy layer :

- un signal short fort en régime bull peut être downgradé ;
- un signal short moyen en régime défensif peut être promu.

Attention : cela doit rester **explicable** et **rejouable** en backtest.

---

## 7. Recommandation produit et data science

## 7.1 Ce qu’il faut éviter

### À éviter absolument

- déduire “short” d’une simple proba long faible ;
- garder les mêmes thresholds pour long et short par symétrie naïve ;
- juger le modèle sur une métrique unique ;
- activer le short live avant un backtest directionnel crédible ;
- fusionner trop tôt long et short dans un seul score opaque.

## 7.2 Ce qu’il faut viser

### Cible raisonnable V1

- target ternaire,
- modèle 3 classes,
- calibration simple long-vs-rest / short-vs-rest,
- ranking bilatéral séparé,
- risk budgets séparés,
- exécution short sous feature flag,
- métriques long / short séparées.

---

## 8. Plan de sprint recommandé

Je recommande **7 sprints**.

---

## Sprint 0 — ADR, contrats de données et feature flags

### Objectif

Fixer le cadre avant toute implémentation.

### Travaux

- rédiger la représentation canonique :
  - `predicted_side`
  - probas multi-classes
  - `side` métier explicite
- définir les feature flags :
  - `short_selling_enabled`
  - `ml_directional_mode_enabled`
- définir le schéma de migration DB
- définir les nouveaux contrats JSON / artefacts ML

### Critères de sortie

- architecture figée ;
- schémas validés ;
- rétrocompatibilité explicitée.

---

## Sprint 1 — Refondre la target ML et la couche dataset

### Objectif

Passer d’un label binaire à un label directionnel exploitable.

### Fichiers clés

- `modelFactory/config.py`
- `modelFactory/features.py`
- `modelFactory/target_optimization.py`
- `modelFactory/dataset.py`

### Travaux

- ajouter `target_mode='ternary'`
- implémenter label `short / flat / long`
- ajouter seuils long/short distincts
- adapter l’optimisation de target
- adapter dataset + splits + validations

### Tests à ajouter

- target ternaire correcte
- respect des zones neutres
- absence de lookahead

### Critères de sortie

- dataset d’entraînement ternaire stable
- optimisation de target compatible

---

## Sprint 2 — Modèle, métriques et calibration multi-classes

### Objectif

Rendre la chaîne d’entraînement ML directionnelle.

### Fichiers clés

- `modelFactory/model.py`
- `modelFactory/trainer.py`
- `modelFactory/evaluation.py`
- `modelFactory/calibration.py`
- `modelFactory/predictor.py`

### Travaux

- convertir métriques binary → multi-class / par side
- produire probas par classe
- mettre en place calibration v1 compatible ternary
- revoir sélection du champion avec score métier long+short
- documenter la policy de décision

### Tests à ajouter

- confusion matrix cohérente
- calibration directionnelle
- prédiction `predicted_side` cohérente

### Critères de sortie

- modèle entraînable en mode directionnel
- prédictions exploitables en `long / flat / short`

---

## Sprint 3 — Persistance, registre ML et inférence

### Objectif

Transporter l’information directionnelle jusqu’aux consommateurs aval.

### Fichiers clés

- `modelFactory/db_registry.py`
- `modelFactory/predictor.py`
- migrations Alembic

### Travaux

- étendre le schéma de `model_predictions`
- persister probas par classe et side canonique
- versionner le schéma de sortie modèle
- conserver une compatibilité de lecture ancienne si nécessaire

### Tests à ajouter

- insert/load prédictions directionnelles
- fallback de lecture rétrocompatible

### Critères de sortie

- le registre ML persiste toute l’information utile au long+short

---

## Sprint 4 — Ranking, conviction et risk management bilatéraux

### Objectif

Transformer la sélection et l’allocation en pipeline long+short ML-aware.

### Fichiers clés

- `selector/ranking.py`
- `core/conviction.py`
- `risk_management/models.py`
- `risk_management/portfolio_builder.py`
- `risk_management/constraints.py`
- `risk_management/db_io.py`
- `risk_management/audit.py`
- `risk_management/cli.py`

### Travaux

- introduire shortlist long / short
- introduire `side` dans les modèles de risque
- introduire conviction directionnelle
- ajouter caps et budgets par side
- rendre le régime directionnel dans la décision d’entrée

### Tests à ajouter

- sélection mixte long+short
- caps par side
- persistance des targets directionnels

### Critères de sortie

- publication de `portfolio_targets` long+short cohérente

---

## Sprint 5 — Backtest directionnel complet avec replay ML

### Objectif

Rejouer fidèlement la stratégie long+short ML-aware.

### Fichiers clés

- `backtesting/signal_replay.py`
- `backtesting/risk_bridge.py`
- `backtesting/simulator.py`
- `backtesting/microstructure.py`
- `backtesting/report.py`
- `backtesting/fidelity.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/exit_lifecycle_replay.py`

### Travaux

- replay side-aware
- conviction side-aware
- PnL / exposure / stops / trailing directionnels
- reporting séparé long et short
- fidelity directionnelle

### Validation métier recommandée

- 2020 : vérifier la protection en crise
- 2021 : éviter l’hyper-rotation
- 2022 : vérifier la capacité du short à produire de la perf

### Critères de sortie

- backtest crédible long+short avec ML

---

## Sprint 6 — Exécution live / paper, protections et réconciliation

### Objectif

Déployer la chaîne live complète long+short.

### Fichiers clés

- `execution_engine/order_intents.py`
- `execution_engine/account_state.py`
- `execution_engine/executor.py`
- `execution_engine/protection_watcher.py`
- `execution_engine/orphan_adoption.py`
- `execution_engine/reconciliation.py`
- `execution_engine/db_io.py`
- `execution_engine/tca.py`
- `run_execution.py`

### Travaux

- entrer short côté OMS
- protections buy-to-cover correctes
- réserve de marge / checks shortable
- réconciliation long/short
- lots long/short
- TCA directionnel

### Critères de sortie

- paper trading long+short stable
- logs et audit suffisants

---

## Sprint 7 — Gouvernance ML, monitoring et industrialisation

### Objectif

Sécuriser la durée de vie du système long+short.

### Fichiers clés

- `risk_management/ml_gate.py`
- `tests/test_run_ml_regime_ablation.py`
- scripts d’ablation / calibration / monitoring
- reporting / artefacts de production

### Travaux

- drift monitoring par side
- ML gate par direction si nécessaire
- ablation ML ON/OFF séparée long et short
- dashboards long/short
- champion/challenger directionnel

### Métriques à suivre en production

- precision long
- precision short
- recall long
- recall short
- hit rate long
- hit rate short
- contribution PnL long
- contribution PnL short
- churn par side
- borrow rejection rate
- short protection missing rate

### Critères de sortie

- système gouvernable en exploitation réelle

---

## 9. Ordre de priorité recommandé

Si tu veux transformer l’application complètement, l’ordre optimal est :

1. **target + dataset ML**
2. **modèle + calibration + registre prédictions**
3. **ranking + conviction + risk bilatéral**
4. **backtest complet**
5. **live / paper execution**
6. **monitoring et gouvernance**

Je déconseille de commencer par le live short ML tant que :

- la target n’est pas directionnelle,
- la calibration n’est pas cohérente,
- le backtest n’est pas validé sur 2022.

---

## 10. Risques majeurs

## Risque 1 — Mauvaise sémantique ML

Si on garde une probabilité binaire de hausse et qu’on la détourne en signal short, on obtiendra un système peu robuste et difficile à calibrer.

## Risque 2 — Faux équilibre long/short

Les marchés ne sont pas symétriques.
Une architecture trop symétrique peut être élégante mais mauvaise en pratique.

## Risque 3 — Rétrocompatibilité cassée

Les changements sur les schémas de prédictions, targets et reports doivent être versionnés proprement.

## Risque 4 — Overfitting short

Le short peut sembler très performant sur certaines fenêtres de crise et s’effondrer hors contexte.
Il faut donc du walk-forward sérieux et des métriques par régime.

## Risque 5 — Divergence backtest / live

C’est particulièrement dangereux sur les shorts :

- disponibilité à l’emprunt,
- rejet broker,
- borrow cost,
- squeeze.

---

## 11. Recommandation finale

### Recommandation stratégique

Si tu veux une **vraie application long + short avec ML**, il faut considérer que tu lances une **V2 directionnelle** de l’application, pas une simple extension marginale.

### Recommandation technique

Le meilleur chemin est :

- conserver le socle d’exécution actuel,
- refondre d’abord le contrat ML,
- propager ensuite la direction jusqu’au backtest et au live,
- tout faire sous feature flags.

### Recommandation de démarrage concret

Commencer par :

- **Sprint 0**
- **Sprint 1**
- **Sprint 2**

puis lancer un premier protocole expérimental sur :

- target ternaire,
- validation walk-forward,
- backtests 2020 / 2021 / 2022.

---

## 12. Résumé en une phrase

Pour transformer complètement l’application en **long + short avec ML**, il faut d’abord faire évoluer le ML d’une logique **binaire bullish** vers une logique **directionnelle explicite (`long / flat / short`)**, puis propager cette direction dans le ranking, le risk management, le backtest, l’OMS live, la réconciliation et le reporting, le tout sous **feature flags** et avec validation prioritaire sur les années de stress comme **2022**.


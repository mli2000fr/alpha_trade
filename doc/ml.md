# Documentation des paramètres ML — IHM Pipeline (Model Factory)

> Page IHM : `Pipeline` → bloc **Paramètres Model Factory**
> Fichier source : `ihm/pages/_execution_center/__init__.py`
> Valeurs par défaut : `ihm/services/pipeline_runner.py`

Les paramètres sont présentés dans l'ordre exact de l'écran, de haut en bas.

---

## 1. Preset ML

| Propriété | Valeur |
|---|---|
| **Label** | `Preset ML` |
| **Type** | `selectbox` |
| **Options** | `prod swing`, `debug rapide CPU`, `debug GPU`, `custom` |
| **Défaut** | `prod swing` |

**Rôle** : Préremplit automatiquement tous les champs ML avec des valeurs recommandées adaptées au contexte. Les champs restent modifiables ensuite ; si un champ est modifié, le statut passe à « 🟡 preset modifié manuellement ».

- **prod swing** : valeurs de production (walk-forward ON, epochs 50, workers 4, accelerator auto).
- **debug rapide CPU** : entraînement léger sur CPU (walk-forward OFF, epochs 10, workers 1, debug ON).
- **debug GPU** : comme debug rapide mais force `--accelerator gpu`.
- **custom** : mode manuel, aucun préremplissage automatique.

**Impact** : Aucun impact direct sur le modèle. C'est un raccourci ergonomique pour éviter de remplir 60 champs à la main.

---

## 2. Accélérateur ML

| Propriété | Valeur |
|---|---|
| **Label** | `Accélérateur ML` |
| **Type** | `selectbox` |
| **Options** | `auto`, `cpu`, `gpu` |
| **Défaut** | `auto` |
| **CLI** | `--accelerator` |

**Rôle** : Détermine sur quel matériel l'entraînement LSTM s'exécute (LightGBM et CatBoost restent toujours sur CPU).

- **auto** : utilise le GPU si CUDA est disponible, sinon CPU.
- **cpu** : force l'entraînement sur CPU uniquement. Permet `max_workers > 1` (entraînement parallèle de plusieurs symboles).
- **gpu** : force le GPU. Si aucun GPU n'est disponible, le job échoue.

**Impact performance** : Avec GPU, `effective_workers = 1` (un seul symbole à la fois, pour éviter les OOM CUDA). Avec CPU, `effective_workers = max_workers` (jusqu'à 8+ symboles en parallèle). Pour un grand univers (>1000 symboles), le CPU multi-workers peut être plus rapide que le GPU séquentiel.

---

## 3. Mode de reconstruction ML

| Propriété | Valeur |
|---|---|
| **Label** | `Mode de reconstruction ML` |
| **Type** | `selectbox` |
| **Options** | `rebuild-all`, `rebuild-missing`, `refresh-stale` |
| **Défaut** | `rebuild-missing` |
| **CLI** | `--ml-mode` |

**Rôle** : Détermine quels symboles sont entraînés ou sautés.

- **rebuild-all** : réentraîne tous les symboles, même ceux qui ont déjà un modèle valide.
- **rebuild-missing** : n'entraîne que les symboles sans `config.json` dans `artifacts/models/{SYMBOLE}/`. Les symboles déjà entraînés sont sautés intégralement (aucune écriture DB).
- **refresh-stale** : réentraîne les symboles dont le modèle est absent, dont le `feature_fingerprint` a changé (changement de `feature_set`, `include_sentiment`, etc.), ou dont l'historique d'entraînement est en retard sur les dernières barres disponibles.

**Impact** : `rebuild-missing` est le mode le plus sûr pour un usage quotidien. `rebuild-all` est utile après un `TRUNCATE` des tables ML ou un changement global de configuration. `refresh-stale` est le plus intelligent mais plus lent.

---

## 4. Date de début du training ML

| Propriété | Valeur |
|---|---|
| **Label** | `Date de début du training ML` |
| **Type** | `date_input` |
| **Défaut** | `2020-01-01` |
| **CLI** | `--training-start-date` |
| **Format** | `YYYY-MM-DD` |

**Rôle** : Date minimale des barres daily transmises au backend Model Factory. Les barres antérieures à cette date sont ignorées.

**Impact** : Plus la fenêtre est longue, plus le modèle a de données historiques, mais plus l'entraînement est lent. 2020-01-01 donne ~5-6 ans d'historique, ce qui est suffisant pour capturer différents régimes de marché (COVID, reprise, bear market 2022, rally 2023-2025).

---

## 5. Date de fin du training ML

| Propriété | Valeur |
|---|---|
| **Label** | `Date de fin du training ML` |
| **Type** | `date_input` |
| **Défaut** | `2025-12-31` |
| **CLI** | `--training-end-date` |
| **Format** | `YYYY-MM-DD` |

**Rôle** : Date maximale incluse pour borner l'entraînement. Les barres postérieures sont exclues.

**Impact** : Sert à figer une période d'évaluation walk-forward propre. Pour un usage quotidien en production, mettre la date du jour.

---

## 6. Filtrage d'univers selector (section expandable)

### 6a. selector_signal_mode autorisés

| Propriété | Valeur |
|---|---|
| **Label** | `selector_signal_mode autorisés` |
| **Type** | `multiselect` |
| **Options** | `strict`, `sector_neutralized` |
| **Défaut** | vide (aucun filtre) |
| **CLI** | `--selector-universe-signal-modes` |

**Rôle** : Filtre l'univers d'entraînement ML pour ne conserver que les symboles ayant l'un des `selector_signal_mode` sélectionnés dans `stock_scores`. Si vide, aucun filtrage.

### 6b. candidate_rank max

| Propriété | Valeur |
|---|---|
| **Label** | `candidate_rank max` |
| **Type** | `number_input` |
| **Défaut** | `0` (désactivé) |
| **CLI** | `--selector-universe-max-candidate-rank` |

**Rôle** : Limite l'univers aux N premiers symboles selon le `candidate_rank` du selector courant. `0` = pas de limite.

### 6c. Exclure earnings_blackout

| Propriété | Valeur |
|---|---|
| **Label** | `Exclure earnings_blackout` |
| **Type** | `checkbox` |
| **Défaut** | décoché |
| **CLI** | `--selector-universe-exclude-earnings-blackout` |

**Rôle** : Exclut les symboles en période d'earnings blackout (risque de gap majeur).

---

## 7. Options principales — Colonne 1

### 7a. Inclure les features sentiment

| Propriété | Valeur |
|---|---|
| **Label** | `Inclure les features sentiment` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--include-sentiment` |

**Rôle** : Ajoute les features de sentiment FinBERT agrégées (score moyen, momentum de sentiment, ratio positive/négative) au dataset d'entraînement.

**Impact** : Améliore la capacité du modèle à anticiper les mouvements liés aux actualités. Nécessite que le pipeline Event Sentiment ait été exécuté au préalable. Si les features sentiment ne sont pas disponibles pour un symbole, l'entraînement continue sans elles.

### 7b. Inclure les features contexte selector

| Propriété | Valeur |
|---|---|
| **Label** | `Inclure les features contexte selector` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--include-selector-context` |

**Rôle** : Enrichit le dataset ML avec des features PIT-safe (Point-In-Time) issues de `stock_scores_history` : `candidate_rank`, scores de momentum, ratings composites du selector.

**Impact** : Permet au modèle d'apprendre des signaux croisés entre le scoring quantitatif et le ML. Utile en production swing.

### 7c. Comparer LightGBM local

| Propriété | Valeur |
|---|---|
| **Label** | `Comparer LightGBM local` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--compare-lightgbm` |

**Rôle** : Entraîne un modèle LightGBM tabulaire par symbole en plus du LSTM, pour servir de challenger dans la sélection champion.

**Impact** : Double le temps d'entraînement par symbole. LightGBM est un modèle gradient boosting sur features tabulaires (non séquentiel), souvent bon sur les données financières structurées.

### 7d. Comparer CatBoost local

| Propriété | Valeur |
|---|---|
| **Label** | `Comparer CatBoost local` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--enable-catboost` |

**Rôle** : Identique à LightGBM mais avec CatBoost (Yandex). CatBoost gère mieux les variables catégorielles et est souvent plus robuste sans tuning poussé.

---

## 8. Options principales — Colonne 2

### 8a. Activer la sélection automatique du champion

| Propriété | Valeur |
|---|---|
| **Label** | `Activer la sélection automatique du champion` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--select-champion` |

**Rôle** : Après entraînement, compare les modèles disponibles (LSTM, LightGBM, CatBoost, global) et sélectionne automatiquement le meilleur selon la métrique choisie. Le modèle champion est inscrit dans `model_governance` et sera servi par `ml_predict`.

**Impact** : Essentiel en production pour garantir que le meilleur modèle est utilisé. Sans cette option, seul le `default_champion` (LSTM) est servi.

### 8b. Métrique de sélection du champion

| Propriété | Valeur |
|---|---|
| **Label** | `Métrique de sélection du champion` |
| **Type** | `selectbox` |
| **Options** | `selection_score`, `business_score`, `auc` |
| **Défaut** | `selection_score` |
| **CLI** | `--champion-selection-metric` |

**Rôle** : Définit la métrique utilisée pour départager les modèles challengers.

- **selection_score** : score composite interne pondérant F1, précision, rappel, couverture.
- **business_score** : score orienté métier (hit rate, payoff ratio, couverture).
- **auc** : ROC-AUC classique (binary only, ne s'applique pas en ternaire).

**Impact** : `selection_score` est le plus équilibré pour le mode ternaire. `business_score` favorise les modèles qui génèrent le plus de rendement ajusté au risque.

### 8c. Optimiser le seuil de décision

| Propriété | Valeur |
|---|---|
| **Label** | `Optimiser le seuil de décision` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--optimize-thresholds` |

**Rôle** : Balaye les `candidate_decision_thresholds` sur l'ensemble de validation et sélectionne le seuil qui maximise le business score tout en respectant les contraintes `min_action_rate`, `max_action_rate`, `min_precision_long`.

**Impact** : Désactivé automatiquement en mode ternaire (`num_classes=3`), car l'optimisation de seuil binaire n'a pas de sens avec 3 classes.

---

## 9. Options principales — Colonne 3

### 9a. Entraîner aussi un modèle global multi-symboles

| Propriété | Valeur |
|---|---|
| **Label** | `Entraîner aussi un modèle global multi-symboles` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--enable-global-model` |

**Rôle** : Entraîne un modèle tabulaire (LightGBM ou CatBoost) sur l'ensemble des symboles d'un coup (dataset multi-symboles). Ce modèle global apprend des patterns transversaux (sectoriels, macro) que les modèles par symbole ne peuvent pas capturer.

**Impact** : Ajoute ~5-10% de temps d'entraînement total. Le modèle global est ensuite injecté dans les artefacts de chaque symbole et peut être sélectionné comme champion.

### 9b. Backend du modèle global

| Propriété | Valeur |
|---|---|
| **Label** | `Backend du modèle global` |
| **Type** | `selectbox` |
| **Options** | `catboost`, `lightgbm` |
| **Défaut** | `catboost` |
| **CLI** | `--global-model-name` |

**Rôle** : Choisit l'algorithme du modèle global. CatBoost est recommandé par défaut car il gère mieux les features hétérogènes sans préprocessing.

### 9c. Activer les features cross-sectionnelles

| Propriété | Valeur |
|---|---|
| **Label** | `Activer les features cross-sectionnelles` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--enable-cross-sectional` |

**Rôle** : Enrichit le dataset de chaque symbole avec des features calculées par rapport à l'univers du jour : rang centile du rendement, rang du volume, spread sectoriel, etc. Ces features aident le modèle à comprendre la position relative d'un titre.

**Impact** : Multiplie le nombre de features par ~1.5. Améliore significativement la performance des modèles globaux et la robustesse des LSTMs. Nécessite au moins `cross_sectional_min_universe` (20) symboles actifs par jour.

### 9d. Optimiser l'horizon / la target swing

| Propriété | Valeur |
|---|---|
| **Label** | `Optimiser l'horizon / la target swing` |
| **Type** | `checkbox` |
| **Défaut** | décoché |
| **CLI** | `--optimize-target` |

**Rôle** : Lance une recherche par grille sur les `candidate_horizons`, `candidate_up_thresholds`, et `candidate_down_thresholds` pour trouver la combinaison (horizon, seuil long, seuil short) qui maximise la performance sur l'ensemble de validation.

**Impact** : Très coûteux (× nombre de combinaisons dans la grille). À réserver pour une optimisation périodique (mensuelle/trimestrielle), pas pour l'entraînement quotidien.

---

## 10. Cible swing & horizon

### 10a. Mode de cible

| Propriété | Valeur |
|---|---|
| **Label** | `Mode de cible` |
| **Type** | `selectbox` |
| **Options** | `binary`, `swing_cash`, `ternary` |
| **Défaut** | `ternary` |
| **CLI** | `--target-mode` |

**Rôle** : Définit comment la variable cible (target) est construite à partir des rendements futurs.

- **binary** : cible binaire 0/1. `future_return > threshold` → 1, sinon 0. Ne distingue pas les shorts.
- **swing_cash** : cible asymétrique. `future_return > up_threshold` → 1 (long), `future_return < down_threshold` → -1 (short), sinon 0 (flat/cash). Génère deux colonnes `target_long` et `target_short`.
- **ternary** : cible 3-classes. `future_return > up_threshold` → +1 (long), `future_return < down_threshold` → -1 (short), sinon 0 (flat). Une seule colonne `target` avec 3 valeurs. Le modèle produit des probabilités sur 3 classes.

**Impact** : `ternary` est le mode recommandé pour le swing trading directionnel. Il permet au modèle d'apprendre simultanément les signaux long, short et flat, avec une cohérence de calibration entre les trois classes.

### 10b. Horizon de prédiction (jours)

| Propriété | Valeur |
|---|---|
| **Label** | `Horizon de prédiction (jours)` |
| **Type** | `number_input` |
| **Min/Max** | 1 / 30 |
| **Défaut** | `5` |
| **CLI** | `--forecast-horizon` |

**Rôle** : Nombre de jours dans le futur pour lequel on prédit le rendement. La target est calculée comme le rendement entre `t` et `t + horizon`.

**Impact** : 5 jours = horizon swing typique (une semaine de trading). Plus l'horizon est long, plus le signal est dilué mais plus le turnover est faible. 3 jours = plus réactif mais plus bruité. 10 jours = plus stable mais moins de signaux.

### 10c. Seuil cible UP

| Propriété | Valeur |
|---|---|
| **Label** | `Seuil cible UP` |
| **Type** | `number_input` |
| **Min/Max** | 0.0 / 0.20 |
| **Défaut** | `0.12` (+12%) |
| **CLI** | `--target-up-threshold` |

**Rôle** : Seuil de rendement futur au-dessus duquel un trade est étiqueté comme « long ». Aligné sur le take-profit (+12%).

**Impact** : Un seuil plus bas (ex: 0.02 = +2%) génère plus de labels positifs mais plus bruités. Un seuil plus haut (ex: 0.15 = +15%) génère des signaux plus rares mais plus fiables. La valeur 0.12 est alignée avec le TP du risk management pour garantir que le modèle apprend à prédire des mouvements qui couvrent le TP.

### 10d. Seuil cible DOWN

| Propriété | Valeur |
|---|---|
| **Label** | `Seuil cible DOWN` |
| **Type** | `number_input` |
| **Min/Max** | -0.20 / 0.0 |
| **Défaut** | `-0.08` (-8%) |
| **CLI** | `--target-down-threshold` |

**Rôle** : Seuil de rendement futur en-dessous duquel un trade est étiqueté comme « short ». Aligné sur le take-profit short (-8%).

**Impact** : Symétrique du seuil UP mais avec une magnitude plus faible (-8% vs +12%), car les marchés baissiers sont historiquement plus rapides (drawdowns plus violents que les rallies). Un short à -8% capture bien les corrections sans être trop rare.

### 10e. Seuil de décision

| Propriété | Valeur |
|---|---|
| **Label** | `Seuil de décision` |
| **Type** | `number_input` |
| **Min/Max** | 0.0 / 1.0 |
| **Défaut** | `0.55` |
| **CLI** | `--decision-threshold` |

**Rôle** : En mode binaire, probabilité minimale pour déclencher un ordre d'entrée. En mode ternaire, ce paramètre n'est pas utilisé tel quel : la décision se fait par `argmax` sur les 3 classes. Le seuil peut être réoptimisé automatiquement si `--optimize-thresholds` est activé.

### 10f. Méthode de calibration

| Propriété | Valeur |
|---|---|
| **Label** | `Méthode de calibration` |
| **Type** | `selectbox` |
| **Options** | `none`, `platt` |
| **Défaut** | `platt` |
| **CLI** | `--calibration-method` |

**Rôle** : Applique une calibration des probabilités après entraînement.

- **none** : pas de calibration, les probabilités brutes du modèle sont utilisées.
- **platt** : calibration Platt (régression logistique sur les logits). Rend les probabilités plus fiables (une proba de 0.7 correspond vraiment à ~70% de chance).

**Impact** : La calibration Platt est automatiquement désactivée en mode ternaire (`num_classes=3`) car elle est conçue pour le cas binaire uniquement.

---

## 11. Walk-forward

### 11a. Activer walk-forward

| Propriété | Valeur |
|---|---|
| **Label** | `Activer walk-forward` |
| **Type** | `checkbox` |
| **Défaut** | coché |
| **CLI** | `--walkforward` / `--no-walkforward` |

**Rôle** : Active une validation walk-forward avant l'entraînement final. Le walk-forward divise l'historique en splits temporels glissants (entraînement → validation → test), puis réentraîne sur chaque split, simulant des conditions réelles de trading out-of-sample.

**Impact** : Multiplie le temps d'entraînement par `(max_splits + 1)`. Très utile en production pour évaluer la robustesse temporelle du modèle. À désactiver pour du debug rapide.

### 11b. wf min train

| Propriété | Valeur |
|---|---|
| **Label** | `wf min train` |
| **Type** | `number_input` |
| **Défaut** | `504` |
| **CLI** | `--wf-min-train-size` |

**Rôle** : Taille minimale de la fenêtre d'entraînement walk-forward, en jours de trading. 504 jours ≈ 2 ans de trading.

### 11c. wf val / wf test

| Propriété | Valeur |
|---|---|
| **Label** | `wf val`, `wf test` |
| **Type** | `number_input` |
| **Défaut** | `126` chacun |
| **CLI** | `--wf-val-size`, `--wf-test-size` |

**Rôle** : Taille des fenêtres de validation et de test walk-forward, en jours. 126 jours ≈ 6 mois.

### 11d. wf step

| Propriété | Valeur |
|---|---|
| **Label** | `wf step` |
| **Type** | `number_input` |
| **Défaut** | `126` |
| **CLI** | `--wf-step-size` |

**Rôle** : Pas de glissement entre deux splits walk-forward successifs. 126 jours = les splits avancent de 6 mois à chaque itération.

### 11e. wf max splits

| Propriété | Valeur |
|---|---|
| **Label** | `wf max splits` |
| **Type** | `number_input` |
| **Min/Max** | 1 / 20 |
| **Défaut** | `3` |
| **CLI** | `--wf-max-splits` |

**Rôle** : Nombre maximum de splits walk-forward. 3 splits × (504 train + 126 val + 126 test) = couvre ~4 ans d'historique glissant.

---

## 12. Hyperparams & seuils d'optimisation (section expandable)

### 12a. ML — max workers

| Propriété | Valeur |
|---|---|
| **Label** | `ML — max workers` |
| **Type** | `number_input` |
| **Min/Max** | 1 / 32 |
| **Défaut** | `4` |
| **CLI** | `--max-workers` |

**Rôle** : Nombre de processus parallèles pour l'entraînement des symboles. Avec GPU, ce paramètre est forcé à 1 (contrainte CUDA). Avec CPU, 4 workers entraînent 4 symboles simultanément.

**Impact** : Sur CPU, le speedup est quasi-linéaire jusqu'à `cpu_count`. Au-delà, le gain marginal diminue.

### 12b. ML — max epochs (LSTM)

| Propriété | Valeur |
|---|---|
| **Label** | `ML — max epochs (LSTM)` |
| **Type** | `number_input` |
| **Min/Max** | 5 / 500 |
| **Défaut** | `50` |
| **CLI** | `--max-epochs` |

**Rôle** : Nombre maximum d'époques d'entraînement du LSTM par symbole. L'entraînement peut s'arrêter plus tôt grâce à l'early stopping (patience configurable).

**Impact** : 50 époques est un bon compromis qualité/vitesse pour du swing trading. Pour du debug rapide, 5-10 époques suffisent. Pour une optimisation finale, 100-200 époques peuvent améliorer la convergence.

### 12c. ML — feature set

| Propriété | Valeur |
|---|---|
| **Label** | `ML — feature set` |
| **Type** | `selectbox` |
| **Options** | `v1`, `expert` |
| **Défaut** | `v1` |
| **CLI** | `--feature-set` |

**Rôle** : Sélectionne l'ensemble de features utilisées pour l'entraînement.

- **v1** : features standard (~35 colonnes) : rendements, volatilités, RSI, ATR, volumes, moyennes mobiles.
- **expert** : features avancées (~60 colonnes) : ajoute des indicateurs de régime de marché, des ratios de dispersion, des features de momentum multi-timeframe.

**Impact** : `expert` donne de meilleurs résultats mais augmente le risque d'overfitting sur les petits historiques. `v1` est plus robuste et plus rapide.

### 12d. ML — taux d'action min

| Propriété | Valeur |
|---|---|
| **Label** | `ML — taux d'action min` |
| **Type** | `number_input` |
| **Min/Max** | 0.0 / 1.0 |
| **Défaut** | `0.03` (3%) |
| **CLI** | `--min-action-rate` |

**Rôle** : Pourcentage minimum de prédictions positives (actions) qu'un seuil de décision doit produire pour être valide. Empêche de sélectionner un seuil trop restrictif qui ne générerait presque jamais de trades.

### 12e. ML — taux d'action max

| Propriété | Valeur |
|---|---|
| **Label** | `ML — taux d'action max` |
| **Type** | `number_input` |
| **Min/Max** | 0.0 / 1.0 |
| **Défaut** | `0.20` (20%) |
| **CLI** | `--max-action-rate` |

**Rôle** : Pourcentage maximum de prédictions positives acceptable. Empêche de sélectionner un seuil trop permissif qui générerait trop de trades de faible qualité.

### 12f. ML — précision min (long)

| Propriété | Valeur |
|---|---|
| **Label** | `ML — précision min (long)` |
| **Type** | `number_input` |
| **Min/Max** | 0.0 / 1.0 |
| **Défaut** | `0.55` (55%) |
| **CLI** | `--min-precision-long` |

**Rôle** : Précision minimale exigée pour les signaux long. 55% est un seuil exigeant qui garantit plus de gains que de pertes en moyenne.

### 12g. ML — niveau de log

| Propriété | Valeur |
|---|---|
| **Label** | `ML — niveau de log` |
| **Type** | `selectbox` |
| **Options** | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| **Défaut** | `INFO` |
| **CLI** | `--log-level` |

**Rôle** : Verbosité des logs du backend Model Factory. `DEBUG` est utile pour diagnostiquer un problème, mais génère beaucoup de volume.

### 12h. ML — mode debug train

| Propriété | Valeur |
|---|---|
| **Label** | `ML — mode debug train` |
| **Type** | `checkbox` |
| **Défaut** | décoché |
| **CLI** | `--debug-train` |

**Rôle** : Active des logs plus détaillés et force un ordonnancement déterministe (seed fixe, 1 worker). Utile pour reproduire un bug.

### 12i. ML — heartbeat interval (s)

| Propriété | Valeur |
|---|---|
| **Label** | `ML — heartbeat interval (s)` |
| **Type** | `number_input` |
| **Défaut** | `60` |
| **CLI** | `--heartbeat-interval-seconds` |

**Rôle** : Intervalle d'émission des heartbeats structurés consommés par l'IHM pour afficher la progression en temps réel.

### 12j. ML — watchdog timeout (s)

| Propriété | Valeur |
|---|---|
| **Label** | `ML — watchdog timeout (s)` |
| **Type** | `number_input` |
| **Défaut** | `0` (surveillance seule) |
| **CLI** | `--watchdog-timeout-seconds` |

**Rôle** : Si > 0, le job est considéré comme bloqué si aucun heartbeat n'est reçu pendant ce délai. `0` = pas de timeout.

---

## 13. Hyperparams avancés — Architecture LSTM

### 13a. LSTM — sequence length

| Propriété | Valeur |
|---|---|
| **Label** | `LSTM — sequence length` |
| **Type** | `number_input` |
| **Min/Max** | 5 / 400 |
| **Défaut** | `60` |
| **CLI** | `--sequence-length` |

**Rôle** : Longueur de la fenêtre glissante LSTM, en jours de trading. 60 jours ≈ 3 mois de contexte temporel.

**Impact** : Une séquence plus longue (120-200) donne plus de contexte mais augmente le risque d'overfitting et le temps d'entraînement. 60 est un bon compromis pour le swing 5 jours.

### 13b. LSTM — batch size

| Propriété | Valeur |
|---|---|
| **Label** | `LSTM — batch size` |
| **Type** | `number_input` |
| **Min/Max** | 4 / 4096 |
| **Défaut** | `64` |
| **CLI** | `--batch-size` |

**Rôle** : Taille des mini-batchs pour l'entraînement LSTM.

**Impact** : Sur GPU (RTX 5060 Ti 16 Go), monter à `256` ou `512` améliore significativement l'utilisation GPU. Sur CPU, 64 est raisonnable. Un batch trop petit = GPU sous-utilisé. Un batch trop grand = mémoire GPU saturée.

### 13c. LSTM — hidden size

| Propriété | Valeur |
|---|---|
| **Label** | `LSTM — hidden size` |
| **Type** | `number_input` |
| **Min/Max** | 8 / 1024 |
| **Défaut** | `128` |
| **CLI** | `--hidden-size` |

**Rôle** : Dimension de l'état caché du LSTM. 128 neurones dans la couche récurrente.

**Impact** : Un hidden size plus grand (256-512) donne un modèle plus expressif mais plus lent et plus sujet à l'overfitting. 128 est bien adapté pour ~35-60 features sur 60 jours de séquence.

---

## 14. Hyperparams avancés — Divers

### 14a. Répertoire d'artefacts ML

| Propriété | Valeur |
|---|---|
| **Label** | `Répertoire d'artefacts ML` |
| **Type** | `text_input` |
| **Défaut** | `artifacts/models` |
| **CLI** | `--artifacts-dir` |

**Rôle** : Dossier racine où sont stockés les artefacts par symbole : `config.json`, checkpoints PyTorch, modèles LightGBM/CatBoost sérialisés. Partagé entre `ml_train` et `ml_predict`.

### 14b. Symbole benchmark

| Propriété | Valeur |
|---|---|
| **Label** | `Symbole benchmark` |
| **Type** | `text_input` |
| **Défaut** | `SPY` |
| **CLI** | `--benchmark-symbol` |

**Rôle** : Symbole utilisé pour calculer les features relatives au marché (rendement relatif, beta implicite, corrélation). SPY est le benchmark naturel pour les actions US.

### 14c. Champion par défaut

| Propriété | Valeur |
|---|---|
| **Label** | `Champion par défaut` |
| **Type** | `selectbox` |
| **Options** | `lstm_attention`, `lightgbm`, `catboost`, `global_model` |
| **Défaut** | `lstm_attention` |
| **CLI** | `--default-champion` |

**Rôle** : Modèle servi quand la sélection champion est désactivée ou quand aucun challenger n'est disponible/éligible.

**Impact** : `lstm_attention` est le meilleur modèle par défaut car il exploite la structure temporelle des données. Les modèles tabulaires sont des challengers utiles mais le LSTM avec attention reste le plus performant pour la prédiction de séries temporelles.

### 14d. Cross-sectional — taille mini univers/date

| Propriété | Valeur |
|---|---|
| **Label** | `Cross-sectional — taille mini univers/date` |
| **Type** | `number_input` |
| **Min/Max** | 2 / 500 |
| **Défaut** | `20` |
| **CLI** | `--cross-sectional-min-universe` |

**Rôle** : Nombre minimum de symboles actifs requis à une date donnée pour calculer les features cross-sectionnelles. Si l'univers du jour est plus petit, les features cross-sectionnelles sont désactivées pour cette date.

### 14e. Calibration — min samples

| Propriété | Valeur |
|---|---|
| **Label** | `Calibration — min samples` |
| **Type** | `number_input` |
| **Défaut** | `64` |
| **CLI** | `--calibration-min-samples` |

**Rôle** : Nombre minimum d'échantillons dans l'ensemble de validation pour ajuster le calibrateur Platt. En dessous, la calibration est désactivée.

### 14f. Calibration — max iter

| Propriété | Valeur |
|---|---|
| **Label** | `Calibration — max iter` |
| **Type** | `number_input` |
| **Défaut** | `100` |
| **CLI** | `--calibration-max-iter` |

**Rôle** : Nombre maximum d'itérations pour la régression logistique du calibrateur Platt.

---

## 15. LightGBM (challenger local)

### 15a. LightGBM — max depth

| Propriété | Valeur |
|---|---|
| **Label** | `LightGBM — max depth` |
| **Type** | `number_input` |
| **Défaut** | `4` |
| **CLI** | `--lgbm-max-depth` |

**Rôle** : Profondeur maximale des arbres LightGBM. 4 est volontairement limité pour éviter l'overfitting sur les petits datasets par symbole.

### 15b. LightGBM — n estimators

| Propriété | Valeur |
|---|---|
| **Label** | `LightGBM — n estimators` |
| **Type** | `number_input` |
| **Défaut** | `200` |
| **CLI** | `--lgbm-n-estimators` |

**Rôle** : Nombre d'arbres (itérations de boosting). 200 est un bon compromis pour des datasets de ~500-2000 lignes par symbole.

### 15c. LightGBM — learning rate

| Propriété | Valeur |
|---|---|
| **Label** | `LightGBM — learning rate` |
| **Type** | `number_input` |
| **Défaut** | `0.05` |
| **CLI** | `--lgbm-learning-rate` |

**Rôle** : Taux d'apprentissage du gradient boosting. 0.05 est relativement élevé, adapté aux datasets financiers bruités où un apprentissage trop lent peut manquer les patterns.

---

## 16. CatBoost (challenger local)

### 16a. CatBoost — depth

| Propriété | Valeur |
|---|---|
| **Label** | `CatBoost — depth` |
| **Type** | `number_input` |
| **Défaut** | `6` |
| **CLI** | `--catboost-depth` |

**Rôle** : Profondeur des arbres CatBoost. Légèrement plus profond que LightGBM car CatBoost a un meilleur mécanisme anti-overfitting intégré (ordered boosting).

### 16b. CatBoost — iterations

| Propriété | Valeur |
|---|---|
| **Label** | `CatBoost — iterations` |
| **Type** | `number_input` |
| **Défaut** | `300` |
| **CLI** | `--catboost-iterations` |

**Rôle** : Nombre d'itérations CatBoost. 300 car CatBoost converge généralement plus lentement que LightGBM mais vers de meilleures solutions.

### 16c. CatBoost — learning rate

| Propriété | Valeur |
|---|---|
| **Label** | `CatBoost — learning rate` |
| **Type** | `number_input` |
| **Défaut** | `0.03` |
| **CLI** | `--catboost-learning-rate` |

**Rôle** : Taux d'apprentissage CatBoost. Plus faible que LightGBM (0.03 vs 0.05) car CatBoost utilise plus d'itérations.

---

## 17. Grilles candidate (optimisation)

### 17a. candidate-horizons (jours)

| Propriété | Valeur |
|---|---|
| **Label** | `candidate-horizons (jours)` |
| **Type** | `multiselect` |
| **Défaut** | `[3, 5, 7, 10]` |
| **CLI** | `--candidate-horizons` |

**Rôle** : Liste des horizons testés quand `--optimize-target` est activé. Le backend entraîne et évalue un modèle pour chaque horizon, puis sélectionne le meilleur.

### 17b. candidate-up-thresholds

| Propriété | Valeur |
|---|---|
| **Label** | `candidate-up-thresholds` |
| **Type** | `multiselect` |
| **Défaut** | `[0.015, 0.02, 0.03]` |
| **CLI** | `--candidate-up-thresholds` |

**Rôle** : Liste des seuils UP testés par `--optimize-target`. 1.5%, 2%, 3% de rendement futur pour étiqueter un trade long.

### 17c. candidate-down-thresholds

| Propriété | Valeur |
|---|---|
| **Label** | `candidate-down-thresholds` |
| **Type** | `multiselect` |
| **Défaut** | `[-0.01, -0.015]` |
| **CLI** | `--candidate-down-thresholds` |

**Rôle** : Liste des seuils DOWN testés par `--optimize-target`. -1%, -1.5% pour étiqueter un trade short.

### 17d. candidate-decision-thresholds

| Propriété | Valeur |
|---|---|
| **Label** | `candidate-decision-thresholds` |
| **Type** | `multiselect` |
| **Défaut** | `[0.55, 0.60, 0.65]` |
| **CLI** | `--candidate-decision-thresholds` |

**Rôle** : Liste des seuils de décision testés par `--optimize-thresholds`. Le backend évalue chaque seuil sur la validation et sélectionne celui qui maximise le business score.

### 17e. min-trades-fraction (optimize-target)

| Propriété | Valeur |
|---|---|
| **Label** | `min-trades-fraction (optimize-target)` |
| **Type** | `number_input` |
| **Défaut** | `0.15` (15%) |
| **CLI** | `--min-trades-fraction` |

**Rôle** : Fraction minimale de jours avec un trade (long ou short) qu'une combinaison de paramètres doit produire pour être valide. 15% évite les cibles trop sélectives qui ne généreraient pas assez de signaux.

---

## Récapitulatif des valeurs par défaut clés

| Paramètre | Défaut | Justification |
|---|---|---|
| Target mode | `ternary` | Permet long/flat/short en une seule passe |
| Forecast horizon | `5` jours | Horizon swing typique (1 semaine) |
| Target UP | `+12%` | Aligné take-profit long |
| Target DOWN | `-8%` | Aligné take-profit short |
| Decision threshold | `0.55` | Équilibre précision/rappel |
| Sequence length | `60` jours | ~3 mois de contexte |
| Batch size | `64` | À monter à 256 sur GPU |
| Hidden size | `128` | Bon compromis capacité/vitesse |
| Max epochs | `50` | Convergence LSTM standard |
| Max workers | `4` | Parallélisme CPU raisonnable |
| Walk-forward | ON | Validation temporelle robuste |
| WF splits | `3` | Couvre ~4 ans d'historique |
| Accelerator | `auto` | GPU si dispo, sinon CPU |
| ML mode | `rebuild-missing` | Évite de réentraîner l'existant |
| Feature set | `v1` | Robuste, rapide |
| LightGBM depth | `4` | Anti-overfitting |
| CatBoost depth | `6` | Profondeur modérée |


---

## Rollback du champion ML — Procédure (Sprint S12)

### Contexte

Le système `modelFactory` sélectionne automatiquement un **champion ML** par symbole
(LSTM+Attention, LightGBM, CatBoost ou modèle global) via la métrique `selection_score`.
En cas de dégradation des performances du champion (drift détecté, overfitting, erreur
silencieuse), une procédure de rollback permet de revenir au champion précédent ou au
modèle par défaut (`lstm_attention`).

### Quand déclencher un rollback ?

- **Drift monitor** : le `modelFactory` émet un avertissement dans les `run_summary`
  si le champion actuel sous-performe le champion précédent de plus de 10 % sur la
  métrique de sélection (précision, F1, ou business_score).
- **Dégradation live** : si le taux d'action (`action_rate`) chute en dessous de
  `ml_min_action_rate` (défaut 3 %) ou dépasse `ml_max_action_rate` (défaut 20 %).
- **Erreur d'inférence** : si le champion échoue à produire des prédictions pour
  plus de 5 % des symboles de l'univers (`ml_min_coverage_ratio`).

### Procédure de rollback pas à pas

#### Étape 1 — Identifier le champion problématique

```bash
# Lister les champions actuels par symbole
python -m modelFactory.cli list-champions --format json > champions_$(date +%Y%m%d).json

# Vérifier le drift
python -m modelFactory.cli drift-check --window 20
```

#### Étape 2 — Désactiver le champion défaillant

Dans l'IHM, page **Pipeline → Paramètres Model Factory** :
1. Décocher **Select champion** (`ml_select_champion = False`)
2. Sélectionner **Default champion** = `lstm_attention` (modèle de secours)
3. Lancer un **ML Predict** manuel pour vérifier que l'inférence fonctionne

#### Étape 3 — Rollback en ligne de commande

```bash
# Forcer le rollback vers le champion précédent pour un symbole
python -m modelFactory.cli rollback-champion --symbol AAPL

# Rollback global (tous les symboles)
python -m modelFactory.cli rollback-champion --all --reason "drift_detected"

# Rollback avec réentraînement du champion précédent
python -m modelFactory.cli rollback-champion --all --retrain
```

#### Étape 4 — Vérifier le rollback

```bash
# Vérifier que les prédictions sont revenues à la normale
python -m modelFactory.cli list-champions --format table | grep -v "lstm_attention"

# Si aucune sortie, tous les symboles utilisent le fallback lstm_attention
```

#### Étape 5 — Investiguer la cause racine

1. Consulter les logs ML : `artifacts/models/*/training_log.txt`
2. Vérifier les métriques dans `model_metrics` (table SQL)
3. Comparer les features driftées avec `ml_regime_ablation.py`
4. Si overfitting : réduire `ml_max_epochs` ou augmenter `ml_wf_min_train_size`
5. Si données corrompues : relancer l'ingestion (`step 1`) puis réentraîner

### Rollback automatique (drift monitor)

Le `modelFactory` peut être configuré pour un rollback automatique :

```yaml
# config.yaml
model_factory:
  auto_rollback:
    enabled: true
    max_consecutive_failures: 3
    fallback_champion: "lstm_attention"
    notify_on_rollback: true
```

Quand activé, si le champion échoue 3 jours consécutifs (inférence KO ou drift > seuil),
le système bascule automatiquement sur `fallback_champion` et envoie une notification
email à l'opérateur.

### Restauration après rollback

Une fois le problème corrigé (réentraînement, correction des données) :

```bash
# Réactiver la sélection automatique du champion
python -m modelFactory.cli select-champion --all
```

Le système réévalue tous les backends et sélectionne le meilleur champion pour chaque
symbole. L'ancien champion problématique n'est pas exclu définitivement : il sera
réévalué lors du prochain cycle de sélection.

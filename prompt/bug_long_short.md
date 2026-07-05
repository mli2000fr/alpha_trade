# Audit de cohérence : Backfill → Prédictions → Calibrations

> **Date** : 2026-07-05
> **Contexte** : Vérification de la chaîne complète après verrouillage de la config ML (horizon=10j, batch=32, hidden=256, f1_macro wf=0.258 sur 7584 symboles).

---

## 1. BACKFILL PIT (`stock_scores_history`)

### Ce qui est stocké par jour

```
rank_and_select()        → ~60 longs  (selection_size=60, par final_score décroissant)
rank_and_select_short()  → ~60 shorts (short_selection_size=60, par short_score décroissant,
                                        exclus les symboles déjà dans les 60 longs)
                         ↓
                  concaténés → ~120 candidats/jour, tous is_candidate=1
```

| Direction | Nb | Score utilisé | Exclus si déjà long ? | Colonne dans l'historique |
|---|---|---|---|---|
| Long | 60 | `final_score` ↓ | — | `final_score`, `final_score_sentiment`, `final_score_walk_forward` |
| Short | 60 | `short_score` ↓ | Oui | `short_score`, `short_score_walk_forward` |

✅ **Cohérent** : les deux directions sont capturées PIT, avec leurs scores respectifs.

---

## 2. ML PREDICT

- Lit `stock_scores_history` (ou `stock_scores` en live) pour savoir quels symboles prédire
- Produit `model_predictions` : `predicted_proba` (long) + `proba_short` (short, via softmax ternaire classe 0)
- En runtime standard, **les prédictions portent par défaut sur les candidats** (`symbol_source="candidates"`) : on ne prédit donc pas tout l’univers entraîné, mais l’univers candidat courant
- En backfill historique PIT, le code peut même reconstruire un scope **date par date** pour ne prédire que les symboles effectivement candidats à cette date
- **Les prédictions ne limitent pas le top-N.** Le top-N est décidé par les scores candidats puis par la calibration ; la prédiction ne fait qu'enrichir ces candidats après sélection. La jointure candidat↔prédiction se fait ensuite (`merge_asof` dans `load_dataset()`). Un candidat sans prédiction est soit écarté de la calibration (`.dropna()`), soit traité en mode « quant only » en live.

✅ **Cohérent** : les prédictions ML sont disponibles pour les deux directions sur l’univers candidat traité. Le modèle ternaire produit 3 probas (short/flat/long) → `proba_short` et `predicted_proba` (long) sont tous deux utilisables. La prédiction est un **enrichissement** des candidats, pas un filtre d'entrée dans le top-N.

---

## 3. CALIBRATION CONVICTION (quant/ML)

**Fichier** : `backtesting/weights_calibration.py` → `calibrate_conviction_kelly()`

### Ce qu'elle fait
- Lit `stock_scores_history WHERE is_candidate=1`
- Extrait `COALESCE(final_score_walk_forward, final_score_sentiment, final_score)` → score long uniquement
- Extrait `predicted_proba` depuis `model_predictions` → proba long uniquement
- Calcule `conviction = w_score × quant_score + w_prediction × proba_ml` via `fuse()` (formule **long**)
- Trie par conviction décroissant, prend `head(top_n)` → **top-20 longs**
- Évalue via `_weighted_daily_strategy_returns()` : moyenne pondérée des retours forward, **sans stops, sans corrélation, sans circuit breaker**

### Ce qu'elle NE fait PAS
- ❌ N'utilise pas `short_score`
- ❌ N'utilise pas `proba_short`
- ❌ N'utilise pas `fuse_short()` (formule conviction short)
- ❌ Pas de stops, pas de trailing, pas de corrélation filter, pas de circuit breaker
- ❌ Pas de distinction long/short dans le portefeuille simulé

### Verdict
| Aspect | Statut |
|---|---|
| Direction | � **Long + Short** — corrigé Sprint 2 |
| Moteur d'évaluation | 🟡 **Simplifié** — top-N pondéré, pas de risk management (→ Sprint 3) |
| Score utilisé | ✅ Correct pour les deux directions |
| Shorts | ✅ Présents — calibrés via `fuse_short()` + `proba_short` (Sprint 2) |

---

## 4. CALIBRATION KELLY (sizing)

**Fichier** : même fonction `calibrate_conviction_kelly()` avec `scope='all'`

### Ce qu'elle fait
- Même logique que la calibration conviction, mais ajoute un grid search sur :
  - `kelly_fraction_multiplier` ∈ {0.10, 0.25, 0.50}
  - `assumed_payoff_ratio` ∈ {1.0, 1.5, 2.0}
  - `min_effective_probability` ∈ {0.50, 0.52, 0.55}
- Évalue avec la même méthode simplifiée (top-N pondéré)

### Problèmes

| # | Problème | Détail |
|---|---|---|
| 1 | **Long-only** | Mêmes limitations que la calibration conviction — les shorts sont absents |
| 2 | **Moteur simplifié** | Les paramètres Kelly sont optimisés sur un portefeuille sans stops ni corrélation. Le vrai `KellySizer` opère dans un contexte avec stops, trailing, corrélation filter → les paramètres optimaux dans le modèle simplifié ne sont pas nécessairement optimaux dans le vrai moteur |
| 3 | **Payoff ratio unique** | Un seul `assumed_payoff_ratio` pour tous les trades, alors que les longs et les shorts ont des distributions de rendement différentes |
| 4 | **Probabilité effective** | La formule `p_eff = α × proba_ml + (1−α) × win_rate` est la même pour longs et shorts, mais les shorts utilisent `proba_short` (classe 0 du softmax) qui a une calibration différente de `predicted_proba` (classe 2) |

### Verdict
� **Corrigé Sprint 3.** Kelly peut désormais être calibré dans `BacktestEngine` avec `--backtest-kelly`. Les paramètres sont distincts par direction (`assumed_payoff_ratio_long` ≠ `short`). Le moteur simplifié reste le défaut rapide ; le backtest engine est disponible pour les validations de précision.

---

## 5. VALIDATION WALK-FORWARD (sentiment)

**Fichier** : `backtesting/sentiment_calibration.py` → `walk_forward_backtest()`

### Ce qu'elle fait
- Lit `stock_scores_history` complet (tous les candidats, long+short)
- Grid search sur `sentiment_weight` × `macro_weight`
- Par fold : évalue les scénarios via IC + spread (top-N vs univers pour les longs, bottom-N vs univers pour les shorts)
- Validation finale OOS : **vrai `BacktestEngine`** avec stops, Kelly sizing, corrélation filter, circuit breaker
- Supporte `direction="short"` (P2 2026-06-25) → bottom-N par `composite_score`

### Ce qu'elle NE fait PAS
- ❌ Ne recalibre pas les paramètres Kelly — elle utilise ceux du `RiskConfig` en vigueur
- ❌ Ne recalibre pas les poids de conviction (`score_weight` / `prediction_weight`) — elle utilise ceux du `RiskConfig`

### Verdict
| Aspect | Statut |
|---|---|
| Direction | 🟢 **Long + Short** — les deux directions sont évaluées |
| Moteur d'évaluation | 🟢 **BacktestEngine complet** — stops, sizing, corrélation, circuit breaker |
| Kelly | 🟡 Utilise les params du `RiskConfig`, ne les recalibre pas |
| Conviction | 🟡 Utilise les params du `RiskConfig`, ne les recalibre pas |

---

## 6. TABLEAU DE COHÉRENCE GLOBAL

| Étape | Direction | Moteur | Kelly calibré ? | Conviction calibrée ? |
|---|---|---|---|---|
| **Backfill** | 🟢 Long + Short | N/A (stockage) | N/A | N/A |
| **ML Predict** | 🟢 Long + Short (probas ternaires) | N/A (inférence) | N/A | N/A |
| **④ Conviction** | � Long + Short | 🟡 Simplifié (top-N pondéré) | ❌ | ✅ Oui (Sprint 2) |
| **⑤ Kelly** | � Long + Short (Sprint 3) | 🟢 BacktestEngine (opt-in `--backtest-kelly`) | ✅ Oui (Sprint 3) | ❌ |
| **⑥ Walk-Forward** | 🟢 Long + Short | 🟢 BacktestEngine complet | ❌ (utilise RiskConfig) | ❌ (utilise RiskConfig) |

---

## 7. INCOHÉRENCES IDENTIFIÉES

### A. Direction : Long-only vs Long+Short

✅ Résolu Sprint 2 (conviction) + Sprint 3 (Kelly). Les deux calibrations sont maintenant bi-directionnelles. Le moteur d'évaluation Kelly peut utiliser `BacktestEngine` (opt-in).

### B. Moteur : Simplifié vs Complet

Les calibrations ④ et ⑤ utilisent `_weighted_daily_strategy_returns()` par défaut (rapide). Sprint 3 ajoute `--backtest-kelly` qui évalue les paramètres Kelly dans `BacktestEngine` complet (stops, corrélation, circuit breaker, slippage). Le moteur simplifié reste acceptable pour la calibration conviction ; pour le sizing, le backtest engine est recommandé.

### C. Chaîne de paramètres cassée

```
④ Conviction → produit score_weight, prediction_weight
⑤ Kelly      → produit kelly_fraction_multiplier, payoff_ratio, min_probability
⑥ WF         → consomme ces params (via RiskConfig) mais ne les recalibre pas
```

Si ④ et ⑤ produisent des paramètres sous-optimaux (car long-only + simplifié), ⑥ les valide OOS avec un moteur différent → les résultats OOS peuvent être **pires** que si on avait utilisé des paramètres par défaut conservateurs.

### D. Payoff ratio unique pour deux directions

Le Kelly calibration utilise un seul `assumed_payoff_ratio` pour tous les trades, mais :
- Longs : upside théoriquement illimité, downside limité à -100%
- Shorts : upside limité à +100%, downside théoriquement illimité
- Les distributions de rendement sont asymétriques → un payoff ratio unique est une approximation grossière

### E. Désalignement des quotas entre l'amont et l'aval

Le backfill fabrique un univers PIT d'environ **60 longs + 60 shorts**. Depuis Sprint 2, la calibration conviction ④ exploite les deux jambes. En pratique :
- les 60 shorts sont bien reconstruits et stockés,
- les prédictions short existent,
- ✅ la calibration conviction les utilise désormais (Sprint 2).

**Restent à aligner** : Kelly (⑤) et walk-forward (⑥).

---

## 8. AVIS SUR LA GRAVITÉ DES INCOHÉRENCES

### Mon avis

Toutes les incohérences n'ont pas le même poids :

1. **La calibration Kelly est maintenant disponible dans BacktestEngine (Sprint 3).**
   Le `--backtest-kelly` permet d'évaluer les paramètres Kelly dans le vrai moteur avec stops, corrélation, circuit breaker et slippage. Le moteur simplifié reste le défaut pour les runs rapides. Les params sont distincts par direction.

2. **La calibration Conviction est maintenant bi-directionnelle (Sprint 2).**
   Elle couvre long et short avec des pipelines séparés via `fuse()` / `fuse_short()`. Le moteur d'évaluation reste simplifié (→ Sprint 3 pour le passage à `BacktestEngine`).

3. **Le Walk-Forward est aujourd'hui la référence la plus crédible.**
   C'est le seul maillon qui se rapproche du comportement réel du moteur. En cas de conflit entre une calibration simplifiée et le walk-forward / backtest complet, c'est le moteur complet qui doit arbitrer.

4. **Le problème principal n'est pas `100 longs / 20 shorts` pris isolément (résolu : 60/60 est maintenant le standard).**
   Le vrai problème est que la chaîne aval n'est pas construite pour exploiter proprement cette asymétrie. Aujourd'hui, on produit un univers mixte, mais on ne le calibre pas comme un univers mixte.

5. **Si la cible devient une calibration long+short rigoureuse, la bonne référence n'est plus `100/20` mais une architecture symétrique explicite.**
   Dans ce cadre, la cible recommandée est :
   - **univers candidats PIT / backfill : `60 longs + 60 shorts`**
   - **top de calibration / validation : `20 longs + 20 shorts`**

---

## 9. COHÉRENCE DU RATIO — `60 LONGS / 60 SHORTS`

### Verdict

`60 longs / 60 shorts` est le **nouveau standard par défaut** depuis Sprint 1. Ce ratio est cohérent avec l'objectif de calibration long+short rigoureuse car il rétablit une symétrie de couverture entre les deux jambes tout en conservant un volume total de `~120` candidats/jour.

### Pourquoi ce ratio est cohérent

- Symétrie méthodologique entre long et short pour la constitution du dataset PIT.
- Volume total inchangé par rapport à l'ancien `100/20`, donc sans surcoût opérationnel.
- Évite de surpondérer structurellement le côté long dans la calibration.
- Reste pragmatique : plus réaliste qu'un saut à `100/100`.

### Ce qu'il reste à aligner

- ✅ Univers PIT : `60/60` fait.
- ✅ Calibration conviction : long+short fait (Sprint 2).
- ❌ Calibration Kelly : moteur simplifié par défaut, BacktestEngine disponible (Sprint 3).
- ❌ Walk-forward : pas encore orchestrateur bi-directionnel (→ Sprint 4).

### Conclusion pratique

`60/60` n'est plus une cible future : c'est **le mode de fonctionnement actuel**. La priorité est maintenant d'aligner l'aval (calibration conviction/Kelly/walk-forward) sur cette symétrie.

---

## 10. PLAN D'ACTION RECOMMANDÉ

> **Dépendances entre sprints** : Sprint 2 dépend de Sprint 1. Sprint 4 (intégration) dépend de Sprint 1+2+3 terminés et validés séparément.

### Sprint 0 — Baseline + métriques directionnelles ✅ FAIT (2026-07-05)

**Objectif** : poser les métriques de portefeuille directionnelles et figer les garde-fous Kelly.

**✅ Implémenté**
- Kelly déjà aux valeurs conservatrices dans `risk_management/config.py` : `kelly_fraction_multiplier=0.25`, `assumed_payoff_ratio=1.5`, `min_effective_probability=0.52`, `max_kelly_fraction=0.25`.
- Ajout de `pnl_net`, `gross_exposure_avg_pct`, `net_exposure_avg_pct`, `turnover_pct` dans `BacktestReport` (`backtesting/report.py`). Exposition et turnover marqués `0.0` en attente des données position-level (Sprint 3).
- Pydantic schema (`report_schema_pydantic.py`) mis à jour avec les nouveaux champs.

**Fichiers modifiés**
- `backtesting/report.py` — ajout `pnl_net`, `gross_exposure_avg_pct`, `net_exposure_avg_pct`, `turnover_pct`
- `backtesting/report_schema_pydantic.py` — ajout des champs directionnels

**Critère de sortie**
- ✅ Les rapports de backtest exposent des métriques lisibles par jambe. Kelly est sous garde-fous.

### Sprint 1 — Univers PIT symétrique `60L / 60S` ✅ FAIT (2026-07-05)

**Objectif** : remplacer l'asymétrie `100/20` par un univers candidat symétrique `60/60` comme nouveau standard.

**✅ Implémenté**
- `selection_size` passé de `100` à `60`, `short_selection_size` de `20` à `60` dans `AlphaScannerConfig` (`selector/config.py`).
- Retrait du paramètre `calibration_mode` : le mode symétrique est désormais **le mode par défaut**, sans flag.
- Le backfill produit `60L + 60S` par jour, avec exclusion des doublons conservée via `rank_and_select_short`.
- `--selection-size` du CLI `backfill-scores-history` mis à jour avec le défaut `60`.

**Fichiers modifiés**
- `selector/config.py` — `selection_size=60`, `short_selection_size=60`
- `backtesting/backfill_scores_history.py` — simplification (retrait du paramètre `calibration_mode`)
- `backtesting/cli/_impl.py` — `--selection-size` défaut `60`, retrait `--calibration-mode`

**Critère de sortie**
- ✅ L'univers PIT est symétrique par défaut. Prêt pour les sprints de calibration bi-directionnelle.

### Sprint 2 — Loader bi-directionnel + Conviction `20L / 20S` ✅ FAIT (2026-07-05)

**Objectif** : sortir de la calibration long-only. Cette étape inclut le refactoring du loader de données, prérequis indispensable avant toute calibration bi-directionnelle.

**✅ Implémenté**

**a) Refactoring du loader**
- `load_dataset()` charge désormais `short_score` (ou `short_score_walk_forward`) et `selector_signal_mode` depuis `stock_scores_history`, ainsi que `proba_short` depuis `model_predictions`.
- Le dataset retourné contient `quant_score_short`, `proba_short` et `selector_signal_mode` en plus des colonnes long existantes.
- Fallback automatique si les colonnes short sont absentes (comportement long-only conservé).

**b) Calibration conviction bi-directionnelle**
- Nouvelle fonction `calibrate_conviction_kelly_short()` — miroir de la version long, utilisant `fuse_short()` et inversant les rendements forward (`-forward_return`).
- `walk_forward_backtest()` sépare le dataset en jambes long/short via `selector_signal_mode`, exécute les deux calibrations, puis combine les rendements quotidiens (moyenne long+short).
- Les poids sont consolidés avec préfixes `long_*` / `short_*` dans les artefacts.
- Le nom du scénario reflète les deux jambes : `L:0.70/0.30_S:0.65/0.35`.

**Fichiers modifiés**
- `backtesting/weights_calibration.py` — loader bi-directionnel, `calibrate_conviction_kelly_short()`, consolidation long+short dans `walk_forward_backtest()`, import de `fuse_short`
- `core/conviction.py` — déjà prêt (`fuse_short` existant)

**Validation**
- La calibration conviction fonctionne en mode `20L + 20S`.
- Les artefacts contiennent `long_score_weight`, `short_score_weight`, etc.
- Les shorts sont un objet calibré, plus seulement des lignes ignorées.
- Fallback long-only si les colonnes short sont absentes (rétrocompatibilité).

**Critère de sortie**
- ✅ Le loader alimente les deux directions ; la calibration conviction bi-directionnelle tourne de bout en bout.

### Sprint 3 — Kelly directionnel dans `BacktestEngine` ✅ FAIT (2026-07-05)

**Objectif** : remplacer le moteur simplifié de calibration Kelly par le vrai moteur d'exécution, avec des paramètres distincts par direction.

**✅ Implémenté**

**a) Infrastructure BacktestEngine pour Kelly**
- Nouvelle méthode `_build_backtest_signals()` : convertit le dataset de calibration (scores + conviction) en signaux d'entrée compatibles `BacktestEngine` (top-N par jour, par direction).
- Nouvelle méthode `evaluate_kelly_in_backtest()` : pour un jeu de paramètres Kelly donné, charge l'OHLCV, génère les signaux, exécute `BacktestEngine.run()` avec un `RiskConfig` dédié, et retourne Sharpe / return / drawdown.
- Nouvelle méthode `calibrate_kelly_via_backtest()` : grid search sur les paramètres Kelly (27 combinaisons : 3 fraction × 3 payoff × 3 proba) évalué via `BacktestEngine`, retourne les meilleurs params par direction.

**b) Intégration dans le flux de calibration**
- Paramètre `use_backtest_kelly: bool = False` ajouté à `walk_forward_backtest()`.
- Quand activé, après la calibration conviction (moteur simplifié), les Kelly params sont raffinés via `BacktestEngine` pour les deux jambes.
- Flag CLI `--backtest-kelly` sur `calibrate-conviction-weights`.
- Seuil minimum de 60 jours de données pour activer le backtest (évite les runs trop courts).
- Les Kelly params raffinés écrasent ceux du moteur simplifié dans `best_weights`.

**c) Paramètres distincts long/short**
- Les deux calibrations (long et short) sont indépendantes : `assumed_payoff_ratio_long` peut différer de `assumed_payoff_ratio_short`.
- Les poids consolidés utilisent les préfixes `long_*` / `short_*` (déjà en place depuis Sprint 2).

**⚠️ Coût computationnel**
- Chaque `BacktestEngine.run()` prend quelques secondes à quelques minutes selon la période.
- Une calibration Kelly complète = 27 backtests × 2 directions = 54 runs.
- Usage recommandé : `--backtest-kelly` sur des périodes de validation courtes (3-6 mois), pas sur des historiques complets.
- Le `--backtest-kelly` est désactivé par défaut pour les runs quotidiens.

**Fichiers modifiés**
- `backtesting/weights_calibration.py` — `_build_backtest_signals()`, `evaluate_kelly_in_backtest()`, `calibrate_kelly_via_backtest()`, paramètre `use_backtest_kelly`
- `backtesting/cli/_impl.py` — flag `--backtest-kelly`

**Validation**
- `--backtest-kelly` exécute la calibration Kelly dans `BacktestEngine` avec stops, corrélation, circuit breaker, slippage.
- Les Kelly params peuvent différer entre long et short.
- Sans `--backtest-kelly`, le comportement existant est inchangé.

**Critère de sortie**
- ✅ Kelly peut être calibré dans le même moteur que l'exécution cible. Les params sont directionnels.

### Sprint 4 — Walk-forward orchestrateur central (sprint d'intégration)

**Objectif** : faire du walk-forward la couche unique de calibration et de validation OOS. Ce sprint compose les sprints 1, 2 et 3 — **il ne peut démarrer qu'après leur validation individuelle**.

**⚠️ Dépendance explicite** : Sprint 4 nécessite que Sprint 1 (univers `60/60`), Sprint 2 (conviction `20/20`) et Sprint 3 (Kelly directionnel) soient fonctionnels et testés indépendamment.

**À implémenter**
- Sur chaque fold train : sélectionner ou calibrer `60/60`, conviction `20/20`, Kelly directionnel.
- Sur chaque fold test : exécuter la validation OOS dans le même `BacktestEngine`.
- Comparer les variantes sur métriques portefeuille consolidées (pas uniquement sur moyenne de retours forward).
- Produire un rapport par fold + résumé global avec train vs OOS par jambe.
- Exposer clairement quel scénario est promu et pourquoi.

**Fichiers probables**
- `backtesting/sentiment_calibration.py`
- `backtesting/walk_forward.py`
- `backtesting/cli/_impl.py`

**Validation**
- Un run walk-forward compare plusieurs variantes long+short.
- Le meilleur scénario est sélectionné sur métriques portefeuille.
- Train vs OOS est lisible par jambe.

**Critère de sortie**
- Le walk-forward orchestre la calibration long+short de bout en bout et produit un verdict OOS fondé sur le vrai moteur.

### Sprint 5 — Architecture proche du market-neutral

**Objectif** : rendre l'architecture compatible avec une logique future de neutralité nette ou quasi-neutralité, sans l'imposer prématurément.

> **Note** : les métriques directionnelles de base (gross/net exposure, PnL par jambe) sont déjà dans Sprint 0. Ce sprint ne traite que les **contraintes de neutralité** et les tests de grilles symétriques.

**À implémenter**
- Ajouter une contrainte optionnelle de neutralité nette (corridor cible, ex: `net_exposure ∈ [-0.10, +0.10]`).
- Ajouter le suivi de corrélation inter-jambes.
- Permettre de tester plusieurs grilles symétriques : `60/60`, `80/80`, `100/100`.
- Vérifier que le sizing et les caps ne détruisent pas la neutralité visée.

**Fichiers probables**
- `risk_management/portfolio_builder.py`

**Validation**
- Une grille de variantes symétriques peut être testée et comparée.
- Une asymétrie `100/20` n'est conservée que si elle surperforme la base symétrique `60/60` sur métriques portefeuille.

**Critère de sortie**
- L'architecture supporte proprement un book net long ou quasi market-neutral sans rupture méthodologique.

### Sprint 6 — Finition IHM, CLI, artefacts et documentation

**Objectif** : rendre la chaîne cible exploitable sans ambiguïté.

**À implémenter**
- CLI/IHM : exposer `--long-candidates`, `--short-candidates`, `--top-n-long`, `--top-n-short`.
- Distinguer explicitement mode `baseline` et mode `target` dans les flags et les artefacts.
- Mettre à jour les pages IHM et les exports.
- Documenter les prérequis de données et l'ordre d'exécution des sprints.

**Fichiers probables**
- `backtesting/cli/_impl.py`
- `ihm/pages/backtesting/__init__.py`
- `ihm/services/backtesting_runner.py`
- `doc/synthese_long_short.md`
- `prompt/bug_long_short.md`

**Validation**
- Un opérateur peut lancer chaque sprint sans deviner des paramètres cachés.
- Les artefacts utilisent un vocabulaire cohérent (`60/60`, `20/20`, `baseline`, `target`).

**Critère de sortie**
- Une autre IA peut implémenter ou exécuter chaque sprint indépendamment.


---

## 11. RÉSUMÉ EXÉCUTIF

| Composant | Statut | Action |
|---|---|---|
| Backfill (60L + 60S) | ✅ Cohérent pour la génération PIT | Standard par défaut |
| ML Predict (probas ternaires) | ✅ Cohérent | — |
| Conviction (long-only, simplifié) | � Cohérent long+short (Sprint 2) | Moteur simplifié → Sprint 3 |
| Kelly (long-only, simplifié) | � BacktestEngine disponible (Sprint 3) | Activer `--backtest-kelly` pour validation |
| Walk-Forward (long+short, complet) | 🟢 Brique centrale | En faire l'orchestrateur de calibration OOS |
| Backtest complet | 🟢 Référence finale | Arbitrer toutes les variantes au niveau portefeuille |

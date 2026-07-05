# Audit de cohérence : Backfill → Prédictions → Calibrations

> **Date** : 2026-07-05
> **Contexte** : Vérification de la chaîne complète après verrouillage de la config ML (horizon=10j, batch=32, hidden=256, f1_macro wf=0.258 sur 7584 symboles).

---

## 1. BACKFILL PIT (`stock_scores_history`)

### Ce qui est stocké par jour

```
rank_and_select()        → ~100 longs  (selection_size=100, par final_score décroissant)
rank_and_select_short()  →  ~20 shorts (short_selection_size=20, par short_score décroissant,
                                         exclus les symboles déjà dans les 100 longs)
                         ↓
                  concaténés → ~120 candidats/jour, tous is_candidate=1
```

| Direction | Nb | Score utilisé | Exclus si déjà long ? | Colonne dans l'historique |
|---|---|---|---|---|
| Long | 100 | `final_score` ↓ | — | `final_score`, `final_score_sentiment`, `final_score_walk_forward` |
| Short | 20 | `short_score` ↓ | Oui | `short_score`, `short_score_walk_forward` |

✅ **Cohérent** : les deux directions sont capturées PIT, avec leurs scores respectifs.

---

## 2. ML PREDICT

- Lit `stock_scores_history` (ou `stock_scores` en live) pour savoir quels symboles prédire
- Produit `model_predictions` : `predicted_proba` (long) + `proba_short` (short, via softmax ternaire classe 0)
- Les prédictions couvrent **tous** les symboles entraînés, pas seulement les candidats du jour

✅ **Cohérent** : les prédictions ML sont disponibles pour les deux directions. Le modèle ternaire produit 3 probas (short/flat/long) → `proba_short` et `predicted_proba` (long) sont tous deux utilisables.

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
| Direction | 🔴 **Long-only** — les shorts sont ignorés |
| Moteur d'évaluation | 🟡 **Simplifié** — top-N pondéré, pas de risk management |
| Score utilisé | ✅ Correct pour les longs (`final_score` + `predicted_proba`) |
| Shorts | ❌ Absents — les ~20 shorts/jour du backfill sont chargés (is_candidate=1) mais leur `final_score` bas les exclut naturellement du top-20 |

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
🔴 **Non optimal pour une stratégie long+short.** Les paramètres Kelly calibrés sur un portefeuille long-only simplifié ne sont pas transposables tels quels au vrai moteur long+short avec stops.

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
| **④ Conviction** | 🔴 Long-only | 🟡 Simplifié (top-N pondéré) | ❌ | ✅ Oui |
| **⑤ Kelly** | 🔴 Long-only | 🟡 Simplifié (top-N pondéré) | ✅ Oui | ❌ |
| **⑥ Walk-Forward** | 🟢 Long + Short | 🟢 BacktestEngine complet | ❌ (utilise RiskConfig) | ❌ (utilise RiskConfig) |

---

## 7. INCOHÉRENCES IDENTIFIÉES

### A. Direction : Long-only vs Long+Short

Les calibrations ④ et ⑤ assument un portefeuille **long-only** (top-N par conviction décroissante). La stratégie réelle et le Walk-Forward ⑥ sont **long+short**. Les paramètres optimaux pour un book long-only ne sont pas les mêmes que pour un book long+short — les shorts ont des distributions de rendement asymétriques (upside capé, downside théoriquement illimité), des win rates différents, et une corrélation différente avec le marché.

### B. Moteur : Simplifié vs Complet

Les calibrations ④ et ⑤ utilisent `_weighted_daily_strategy_returns()` : une moyenne pondérée des retours forward, **sans stops, sans trailing, sans corrélation filter, sans circuit breaker, sans slippage**. Le Walk-Forward ⑥ et le vrai backtest utilisent le `BacktestEngine` complet. Les paramètres optimaux dans le modèle simplifié peuvent être dangereux dans le vrai moteur (ex: un Kelly fraction trop élevé qui serait contré par les stops dans la réalité).

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

Le backfill fabrique un univers PIT d'environ **100 longs + 20 shorts**, mais les calibrations ④ et ⑤ ne consomment ensuite qu'un **top-20 long-only**. En pratique :
- les 20 shorts sont bien reconstruits et stockés,
- les prédictions short existent,
- mais la calibration actuelle ne transforme jamais ce stock short en signal calibré exploité.

Autrement dit, l'amont est déjà **bi-directionnel**, alors que l'aval de calibration reste **mono-directionnel**. Ce n'est pas un bug de données ; c'est un désalignement de design.

---

## 8. AVIS SUR LA GRAVITÉ DES INCOHÉRENCES

### Mon avis

Toutes les incohérences n'ont pas le même poids :

1. **La calibration Kelly est la vraie incohérence bloquante.**
   Elle est à la fois long-only **et** évaluée avec un moteur simplifié, alors que son rôle est de piloter le sizing réel. C'est la combinaison la plus risquée, car elle peut pousser des paramètres trop agressifs ou simplement non transférables au vrai moteur.

2. **La calibration Conviction est imparfaite, mais exploitable comme calibration partielle long-side.**
   Elle n'est pas cohérente avec une stratégie long+short complète, mais elle peut encore donner une information utile sur le compromis `final_score` / `predicted_proba` pour la poche long. Il faut simplement la documenter comme telle, et non comme une calibration globale du portefeuille.

3. **Le Walk-Forward est aujourd'hui la référence la plus crédible.**
   C'est le seul maillon qui se rapproche du comportement réel du moteur. En cas de conflit entre une calibration simplifiée et le walk-forward / backtest complet, c'est le moteur complet qui doit arbitrer.

4. **Le problème principal n'est pas `100 longs / 20 shorts` pris isolément.**
   Le vrai problème est que la chaîne aval n'est pas construite pour exploiter proprement cette asymétrie. Aujourd'hui, on produit un univers mixte, mais on ne le calibre pas comme un univers mixte.

---

## 9. COHÉRENCE DU RATIO `100 LONGS / 20 SHORTS`

### Verdict

`100 longs / 20 shorts` est **cohérent comme choix de génération de candidats**, mais **pas suffisant comme preuve de cohérence de la chaîne complète**.

### Pourquoi ce ratio peut être cohérent

- Le portefeuille semble conçu comme **net long** avec une poche short opportuniste, pas comme un book market-neutral 50/50.
- Les shorts sont généralement plus rares, plus fragiles microstructurellement, et plus coûteux en risque opérationnel ; un quota plus faible est donc défendable.
- Le code confirme que ce ratio est **volontairement paramétré** via `selection_size=100` et `short_selection_size=20`, pas subi par hasard.

### Pourquoi ce ratio devient incohérent dans l'architecture actuelle

- Si l'amont retient 20 shorts mais que l'aval calibre uniquement les longs, la poche short n'est pas réellement gouvernée par une calibration dédiée.
- Si l'objectif implicite est une stratégie long+short pleinement calibrée, alors le ratio seul ne suffit pas : il faut aussi des règles aval cohérentes (`top_n_long`, `top_n_short`, conviction short, Kelly short, validation conjointe).
- Le ratio `100/20` est donc **cohérent pour la découverte de candidats**, mais **incomplet pour la calibration**.

### Conclusion pratique

Je considère que `100 longs / 20 shorts` est **acceptable aujourd'hui** si l'intention métier est :
- un moteur principalement long,
- avec une poche short secondaire,
- et une validation finale confiée au backtest/walk-forward complet.

Je le considère **non suffisant** si l'intention est :
- une calibration rigoureuse du portefeuille long+short,
- une symétrie méthodologique entre les deux directions,
- ou une future logique proche du market-neutral.

---

## 10. PLAN D'ACTION RECOMMANDÉ

### Phase 1 — Court terme (cette semaine)

1. **Ne pas exécuter la calibration Kelly (⑤)** en l'état. Utiliser des paramètres Kelly conservateurs par défaut :
   - `kelly_fraction_multiplier = 0.25`
   - `assumed_payoff_ratio = 1.5`
   - `min_effective_probability = 0.52`
   - Ces valeurs sont déjà les défauts dans `RiskConfig` et sont protégées par `max_kelly_fraction=0.25`.

2. **Exécuter la calibration Conviction (④) avec `--scope conviction`** (décocher "Inclure Kelly"). Interpréter le résultat comme une **calibration prioritairement long-side**, utile comme point de départ pour `score_weight` / `prediction_weight`, mais pas comme une vérité calibrée sur toute la poche short.

3. **Exécuter le Walk-Forward (⑥)** avec les paramètres par défaut ou avec la conviction calibrée, pour valider la robustesse OOS de l'ensemble dans le vrai moteur.

4. **Lancer un backtest complet** (`backtesting run`) avec les paramètres calibrés (conviction) + défauts (Kelly) pour établir une baseline de performance.

5. **Conserver provisoirement `100 longs / 20 shorts`** tant qu'aucune analyse empirique ne montre que la poche short est sous-alimentée ou sur-diluée. Le ratio n'est pas la priorité à corriger avant la calibration Kelly.

### Phase 2 — Moyen terme (P3)

6. **Ajouter une calibration conviction short** dans `weights_calibration.py` :
   - Nouvelle fonction `calibrate_conviction_short()` utilisant `short_score` + `proba_short` + `fuse_short()`
   - Tri par conviction short décroissant, top-N shorts
   - Évaluer avec les retours forward (inversés pour les shorts : `-forward_return`)

7. **Intégrer la calibration Kelly dans le Walk-Forward** :
   - Ajouter un grid search Kelly dans `walk_forward_backtest()` ou une fonction dédiée
   - Utiliser le vrai `BacktestEngine` (avec stops, corrélation, etc.) pour évaluer les paramètres Kelly
   - Produire des paramètres Kelly distincts pour longs et shorts

8. **Ou, alternative plus simple** : remplacer la calibration Kelly par une calibration dans le backtest complet :
   - Lancer `backtesting run` avec différents paramètres Kelly
   - Sélectionner les meilleurs paramètres sur la période d'entraînement
   - Valider OOS sur la période de test

9. **Si besoin, tester empiriquement le ratio `100/20`** :
   - comparer `100/20` vs `100/30` vs `80/20`,
   - mesurer fill rate short, turnover, contribution PnL short, drawdown, et stabilité OOS,
   - ne changer le ratio que sur base de ces métriques, pas par symétrie théorique.

### Phase 3 — Documentation

10. **Mettre à jour `synthese_long_short.md` §8** pour documenter ces limitations
11. **Ajouter un cadre d'audit** dans `prompt/bug_long_short.md` pour tracer les résolutions

---

## 11. RÉSUMÉ EXÉCUTIF

| Composant | Statut | Action |
|---|---|---|
| Backfill (100L + 20S) | ✅ Cohérent pour la génération PIT | Conserver provisoirement |
| ML Predict (probas ternaires) | ✅ Cohérent | — |
| Conviction (long-only, simplifié) | 🟡 Utilisable comme calibration long-side partielle | Lancer avec --scope conviction |
| Kelly (long-only, simplifié) | 🔴 Non fiable | **Ne pas lancer.** Utiliser les défauts. |
| Walk-Forward (long+short, complet) | ✅ Cohérent | Lancer pour validation OOS |
| Backtest complet | ✅ Cohérent | Lancer avec conviction calibrée + Kelly défauts |

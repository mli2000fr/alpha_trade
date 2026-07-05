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

5. **Si la cible devient une calibration long+short rigoureuse, la bonne référence n'est plus `100/20` mais une architecture symétrique explicite.**
   Dans ce cadre, la cible recommandée est :
   - **univers candidats PIT / backfill : `60 longs + 60 shorts`**
   - **top de calibration / validation : `20 longs + 20 shorts`**

---

## 9. COHÉRENCE DU RATIO `100 LONGS / 20 SHORTS`

### Verdict

`100 longs / 20 shorts` est **cohérent comme configuration runtime transitoire**, mais **pas suffisant comme cible de calibration** si l'objectif est une méthodologie long+short rigoureuse.

### Pourquoi ce ratio peut être cohérent

- Le portefeuille semble conçu comme **net long** avec une poche short opportuniste, pas comme un book market-neutral 50/50.
- Les shorts sont généralement plus rares, plus fragiles microstructurellement, et plus coûteux en risque opérationnel ; un quota plus faible est donc défendable.
- Le code confirme que ce ratio est **volontairement paramétré** via `selection_size=100` et `short_selection_size=20`, pas subi par hasard.

### Pourquoi ce ratio devient incohérent dans l'architecture actuelle

- Si l'amont retient 20 shorts mais que l'aval calibre uniquement les longs, la poche short n'est pas réellement gouvernée par une calibration dédiée.
- Si l'objectif implicite est une stratégie long+short pleinement calibrée, alors le ratio seul ne suffit pas : il faut aussi des règles aval cohérentes (`top_n_long`, `top_n_short`, conviction short, Kelly short, validation conjointe).
- Le ratio `100/20` est donc **cohérent pour la découverte de candidats**, mais **incomplet pour la calibration**.

### Ratio cible recommandé pour l'objectif long+short rigoureux

Pour l'objectif visé, je recommande comme **standard cible** :

- **Backfill / univers candidats** : **`60 longs + 60 shorts`**
- **Calibration / validation** : **`top 20 longs + top 20 shorts`**

Ce choix est cohérent parce que :

- il rétablit une symétrie méthodologique entre les deux directions ;
- il garde un volume total de candidats proche de l'existant (`120/jour`) ;
- il évite de surpondérer structurellement le côté long dans le dataset de calibration ;
- il reste plus pragmatique qu'un saut immédiat vers `100/100`.

### Conclusion pratique

Je considère que `100 longs / 20 shorts` est **acceptable seulement comme état transitoire** si l'objectif immédiat est d'exploiter un moteur net long déjà opérationnel.

Je le considère **insuffisant comme cible d'architecture** si l'intention est :
- une calibration rigoureuse du portefeuille long+short,
- une symétrie méthodologique entre les deux directions,
- ou une future logique proche du market-neutral.

Dans cette intention cible, le bon réflexe n'est plus de "conserver 100/20 par prudence", mais de **viser directement `60/60` pour l'univers candidats et `20/20` pour la calibration**, puis de revalider empiriquement autour de cette base.

---

## 10. PLAN D'ACTION RECOMMANDÉ

### Sprint 0 — Cadrage et baseline mesurable

**Objectif** : figer la baseline actuelle (`100L/20S`, conviction long-only, Kelly simplifié) comme point de comparaison, sans la traiter comme cible produit.

**À implémenter**
- Documenter dans le code et/ou les artefacts de run que la calibration actuelle ④/⑤ est une **baseline technique historique**.
- Geler provisoirement Kelly sur les valeurs conservatrices actuelles :
  - `kelly_fraction_multiplier = 0.25`
  - `assumed_payoff_ratio = 1.5`
  - `min_effective_probability = 0.52`
- Produire un run de référence portefeuille avec le vrai moteur (`walk-forward` + `backtesting run`).
- Exporter au minimum les métriques suivantes : PnL long, PnL short, hit rate long, hit rate short, gross exposure, net exposure, drawdown, turnover.

**Fichiers / zones probables**
- `backtesting/weights_calibration.py`
- `backtesting/cli/_impl.py`
- `ihm/pages/backtesting/__init__.py`
- `artifacts/conviction_calibration/`
- `artifacts/sentiment_walk_forward/`

**Validation attendue**
- Un run baseline est exécutable depuis CLI et IHM.
- Les artefacts distinguent clairement baseline actuelle vs cible future.
- Le rapport de sortie permet une lecture séparée des jambes long et short.

**Critère de sortie**
- On dispose d'une baseline portefeuille stable et comparable pour tous les sprints suivants.

### Sprint 1 — Univers symétrique de candidats `60L / 60S`

**Objectif** : remplacer, pour la calibration cible, l'asymétrie structurelle `100/20` par un univers candidat symétrique `60/60` tout en gardant le volume total proche de `120` lignes/jour.

**À implémenter**
- Ajouter une configuration de calibration cible distincte du runtime courant :
  - `selection_size_calibration_target = 60`
  - `short_selection_size_calibration_target = 60`
- Permettre au backfill PIT ou à un mode de backfill dédié de produire cet univers symétrique pour la calibration.
- Garantir l'exclusion des doublons long/short comme aujourd'hui.
- Tracer dans l'historique ou les artefacts quel mode a été utilisé : `runtime_100_20` vs `calibration_60_60`.

**Fichiers / zones probables**
- `selector/config.py`
- `selector/ranking.py`
- `backtesting/backfill_scores_history.py`
- éventuels presets / config YAML

**Validation attendue**
- Sur une plage de dates test, le backfill calibration produit environ `60L + 60S` par jour.
- Aucun symbole n'est à la fois long et short le même jour.
- Les colonnes `is_candidate`, `candidate_rank`, `selector_signal_mode` restent cohérentes.

**Critère de sortie**
- L'univers PIT de calibration symétrique est disponible et vérifiable en base ou dans les artefacts.

### Sprint 2 — Calibration conviction bi-directionnelle `20L / 20S`

**Objectif** : sortir de la calibration long-only et calibrer explicitement les deux jambes avec la même méthodologie.

**À implémenter**
- Séparer les deux pipelines de conviction :
  - `conviction_long = fuse(final_score_*, predicted_proba)`
  - `conviction_short = fuse_short(short_score_*, proba_short)`
- Définir une cible de sélection symétrique :
  - `top_n_long = 20`
  - `top_n_short = 20`
- Produire des scores, métriques et artefacts distincts par jambe.
- Ajouter une consolidation portefeuille qui combine les deux jambes pour l'évaluation finale.

**Fichiers / zones probables**
- `backtesting/weights_calibration.py`
- `core/conviction.py`
- `risk_management/cli.py`
- `ihm/pages/backtesting/__init__.py`

**Validation attendue**
- La commande de calibration conviction peut tourner en mode long+short explicite.
- Les artefacts contiennent au minimum : meilleurs poids long, meilleurs poids short, métriques par jambe, métrique portefeuille consolidée.
- Les shorts ne sont plus seulement “chargés puis ignorés”.

**Critère de sortie**
- Une calibration conviction `20L + 20S` fonctionne de bout en bout et produit des résultats auditables.

### Sprint 3 — Kelly directionnel dans le vrai moteur

**Objectif** : supprimer la dépendance au moteur simplifié pour le sizing et calibrer Kelly dans le même moteur que celui utilisé pour la validation portefeuille.

**À implémenter**
- Ne plus utiliser `_weighted_daily_strategy_returns()` comme référence cible pour Kelly.
- Introduire une boucle de calibration Kelly fondée sur `BacktestEngine`.
- Autoriser des paramètres distincts au minimum sur :
  - `assumed_payoff_ratio_long`
  - `assumed_payoff_ratio_short`
  - éventuellement `min_effective_probability_long` / `short`
  - éventuellement `kelly_fraction_multiplier_long` / `short`
- Exporter des métriques de sizing par jambe et consolidées au niveau portefeuille.

**Fichiers / zones probables**
- `backtesting/weights_calibration.py`
- `backtesting/sentiment_calibration.py`
- `backtesting/simulator.py`
- `risk_management/kelly.py`

**Validation attendue**
- La calibration Kelly produit des paramètres directionnels distincts.
- Les résultats diffèrent réellement entre long et short lorsque les distributions le justifient.
- Les métriques sont évaluées avec stops, corrélation, circuit breaker et slippage actifs.

**Critère de sortie**
- Kelly n'est plus calibré dans un moteur conceptuellement différent du moteur cible d'exécution.

### Sprint 4 — Walk-forward orchestrateur central

**Objectif** : faire du walk-forward la couche d'orchestration unique qui sélectionne, calibre et valide l'ensemble de la chaîne long+short.

**À implémenter**
- Sur chaque fold train :
  - calibrer ou sélectionner `60/60` si plusieurs univers sont testés,
  - calibrer conviction `20/20`,
  - calibrer Kelly directionnel,
  - éventuellement calibrer les poids sentiment/macro si encore utilisés.
- Sur chaque fold test :
  - exécuter la validation OOS dans le même moteur,
  - comparer les variantes sur métriques portefeuille, pas uniquement sur moyenne de retours forward.
- Produire un rapport consolidé par fold et un résumé global.

**Fichiers / zones probables**
- `backtesting/sentiment_calibration.py`
- `backtesting/walk_forward.py`
- `backtesting/cli/_impl.py`
- `ihm/services/backtesting_runner.py`

**Validation attendue**
- Un run walk-forward peut comparer plusieurs variantes de calibration long+short.
- Le meilleur scénario est choisi sur base portefeuille globale.
- Les sorties exposent clairement train vs OOS par jambe et au niveau consolidé.

**Critère de sortie**
- Le walk-forward devient la source de vérité pour promouvoir une configuration long+short.

### Sprint 5 — Architecture proche du market-neutral

**Objectif** : rendre l'architecture compatible avec une logique future de neutralité nette ou quasi-neutralité, sans l'imposer prématurément.

**À implémenter**
- Ajouter des métriques et contraintes explicites :
  - `gross_exposure`
  - `net_exposure`
  - contribution PnL long / short
  - corrélation inter-jambes
- Permettre de tester plusieurs grilles symétriques : `60/60`, `80/80`, `100/100`.
- Ajouter, si besoin, un corridor cible de neutralité nette.
- Vérifier que le sizing et les caps ne détruisent pas la neutralité visée.

**Fichiers / zones probables**
- `risk_management/portfolio_builder.py`
- `backtesting/report.py`
- `backtesting/report_schema.py`
- `backtesting/analytics.py`

**Validation attendue**
- Les rapports de backtest exposent la neutralité nette et la contribution par jambe.
- Les variantes symétriques peuvent être comparées proprement.
- Une asymétrie type `100/20` n'est conservée que si elle surperforme clairement la base symétrique.

**Critère de sortie**
- L'architecture supporte proprement un book net long ou quasi market-neutral sans rupture méthodologique.

### Sprint 6 — Finition IHM, CLI, artefacts et documentation

**Objectif** : rendre la nouvelle chaîne exploitable par un opérateur ou une autre IA sans ambiguïté.

**À implémenter**
- Ajouter dans CLI/IHM des options explicites pour :
  - univers candidats `long_candidates` / `short_candidates`
  - `top_n_long` / `top_n_short`
  - Kelly directionnel
  - mode baseline vs mode calibration cible
- Mettre à jour les pages IHM et les exports d'artefacts.
- Documenter la procédure de run par sprint et les prérequis de données.

**Fichiers / zones probables**
- `backtesting/cli/_impl.py`
- `ihm/pages/backtesting/__init__.py`
- `ihm/services/backtesting_runner.py`
- `doc/synthese_long_short.md`
- `prompt/bug_long_short.md`

**Validation attendue**
- Un utilisateur peut lancer chaque étape sans deviner des paramètres cachés.
- Les artefacts et rapports utilisent un vocabulaire cohérent (`60/60`, `20/20`, baseline, cible).
- La documentation permet à une autre IA de reprendre chaque sprint indépendamment.

**Critère de sortie**
- La chaîne complète est industrialisable et documentée de façon non ambiguë.
1. On exécute des **backtests complets** (moteur `BacktestEngine` normal : stops, sizing, corrélation, etc.) avec différentes combinaisons de poids — les décisions **ne sont pas basées sur le sentiment seul** mais sur le score fusionné `w_quant×score + w_sentiment×sentiment_norm + w_macro×macro_norm`
2. On évalue les performances OOS (Out-Of-Sample) par folds glissants
3. On sélectionne les meilleurs poids → sauvegardés dans `latest_best_weights.json`
4. Ces poids peuvent ensuite être appliqués **en LIVE** (via `SentimentBoostConfig`) **et en BACKTEST** (via la colonne `final_score_walk_forward` dans `stock_scores_history`, consommée par la cascade `COALESCE` de `data_loader.py`)

---

## 11. RÉSUMÉ EXÉCUTIF

| Composant | Statut | Action |
|---|---|---|
| Backfill (100L + 20S) | 🟡 Acceptable comme état transitoire | Cible recommandée : migrer vers `60L + 60S` |
| ML Predict (probas ternaires) | ✅ Cohérent | — |
| Conviction (long-only, simplifié) | 🔴 Insuffisant pour la cible long+short | Remplacer par calibration `20L + 20S` |
| Kelly (long-only, simplifié) | 🔴 Non fiable | Sortir du moteur simplifié, recalibrer dans BacktestEngine |
| Walk-Forward (long+short, complet) | 🟢 Brique centrale | En faire l'orchestrateur de calibration OOS |
| Backtest complet | 🟢 Référence finale | Arbitrer toutes les variantes au niveau portefeuille |

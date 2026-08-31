# Contrôle de couverture ML — documentation complète

> Dernière mise à jour : 2026-08-27.
> Sujet : mécanique du gate de couverture, sémantique « couverture ≠ qualité », flux global rank only, synchronisation `global_rank_history` / `model_predictions`, et les 2 points (déclencheur historique explicite + complément live quotidien global-only).

---

## 1. Contexte : les tables et le flux « global rank only »

Deux tables distinctes, remplies par deux étapes distinctes :

| Étape | Table écrite | Rôle |
|---|---|---|
| `predict_global_rank_history()` (`modelFactory/predictor.py`) | **`global_rank_history`** | Rangs : `(symbol, date, global_rank_{H}, batch_id)` — source de vérité |
| `synthesize()` (`modelFactory/synthesize_global_rank_predictions.py`) | **`model_predictions`** | Couche per-symbol dérivée : `proba_long = rank`, `proba_short = 1-rank`, `run_id = {batch}_globalrank_synth` (+ filtre DIP live) |

- **Aucune synchronisation automatique en base** : les deux tables ne sont alignées que par le **processus** (lancer la synthèse après la prédiction).
- La synthèse est **idempotente** (`ON DUPLICATE KEY UPDATE` sur la clé unique `(run_id, symbol, prediction_date)`) → la relancer **écrase** les mêmes lignes, zéro doublon, « au pire il écrase ».
- La `model_predictions` synthétisée est une **projection 1:1 de `global_rank_history`** → sa couverture ≡ couverture de `global_rank_history`.

### Ordre requis (flux nominal)
```
1. predict (remplit global_rank_history + model_predictions via synthèse)
2. backtest (lit les DEUX tables — ne synthétise jamais)
```

---

## 2. Mécanique du gate de couverture

Chaîne : `_impl.py:_enforce_ml_coverage_gate` → `backtesting/fidelity.py:evaluate_ml_coverage_gate` → `backtesting/resilience.py:prepare_predictions_for_ml_mode`.

```
coverage_ratio = (expected_symbol_dates − missing_prediction_keys) / expected_symbol_dates
allowed = coverage_ratio >= --min-ml-coverage-ratio
```

- **`expected_symbol_dates`** = paires `(symbol, date)` de l'**univers d'entraînement du batch** (`_load_batch_training_universe_scope`, mode pipeline), indépendant du batch.
- **`missing_prediction_keys`** = paires présentes dans `expected` mais **absentes de `model_predictions`** filtré par `--ml-batch-id` (`load_predictions` → `JOIN model_training_run` → `AND batch_id = :batch_id`).
- **Le gate est strictement filtré par batch** : jamais « tous batchs confondus » (tant que ML actif, `--ml-batch-id` est obligatoire — `_impl.py:5568`).

### Comportement binaire
```python
if gate.get("enabled") and not gate.get("allowed"):
    _safe_print("❌ Couverture ML insuffisante ...")
    sys.exit(1)      # ← bloque TOUT le run
```
- **Sous le seuil** → le run entier s'arrête (`sys.exit(1)`). Rien ne tourne.
- **Au-dessus** (ou `--min-ml-coverage-ratio 0`) → le run continue intégralement.

### `--cascade-batch-id` / `--ml-batch-id`
- **`--ml-batch-id`** pilote `load_predictions` (ligne ~3170) **et donc le gate de couverture**. Obligatoire quand `--ml-mode != off` (`_impl.py:5568` → `parser.error(...)`).
- **`--cascade-batch-id`** pilote `apply_cascade_to_predictions` (ligne ~3463). Fallback config `batch_diagnostics.backtest_batch_id` (`= model-factory-20260811223551-ef2cd0`), sinon erreur dure si `cascade.enabled`.

---

## 3. Sémantique : « couverture insuffisante » ≠ « modèle mauvais »

Le message de couverture insuffisante est un verdict sur la **disponibilité** (il manque des rangs), **jamais** sur la **qualité** des prédictions.

Pour un batch global only, le gate mesure la présence dans `model_predictions` = présence dans `global_rank_history`. Un trou signifie : **pour X % des (symbol, date) attendus, aucun rang n'a été produit**.

### Pourquoi les trous ?
`predict_global_rank_history` calcule des features **par symbole** (momentum_250, z-scores 252, cross-sectionnelles, relative_strength vs SPY, lookback 500 j calendaires). Un symbole est **exclu du classement du jour** si :
- historique de barres insuffisant (nouvelles cotations, début de période) ;
- features NaN → `rank = NULL` → non persisté → pas de ligne `model_predictions`.

### Chiffres constatés (batch B25 `model-factory-20260811223551-ef2cd0`)

| Période | Couverture `global_rank_history` | Gate à 0.85 |
|---|---|---|
| 2023-2025 | ~99 % (dense) | ✅ passe |
| 2022 | ~77 % (plafond structurel) | ❌ bloque |

Le plafond 2022 ne s'améliore **pas** en réentraînant : il est fixé par l'historique de prix disponible. Réponses possibles :
- `--min-ml-coverage-ratio 0` (ou 0.75) sur les runs 2022 (assumé) ;
- limiter la fenêtre backtest à 2023+ pour garder le gate strict.

---

## 4. Conséquences quand on « laisse passer »

Une fois le gate passé (ou contourné), les (symbol, date) manquants sont simplement **absents de `preds_df`** :

1. **Ils ne sont pas candidats** : dans `cascade_select`, `pred = per_symbol_preds.get(symbol); if pred is None: continue` → ce symbole est sauté **ce jour-là uniquement**.
2. **Les autres candidats ne sont pas bloqués** : ils sont traités normalement.
3. **Conséquence de capacité** : sur les dates creuses, moins de candidats que `max_positions` → positions vides (capital non déployé). Pas d'erreur, juste sous-exposition.
4. **Arrêt dur résiduel** (non lié à la couverture partielle) : `_impl.py:~3480` → `if _cas_passed == 0 and _cas_before > 0: sys.exit(1)`. Ne se déclenche que si la cascade produit **0 candidat alors qu'il y avait des prédictions** (mauvaise config `top_pct`/`min_prob`). Une couverture à 77 % ne le déclenche pas.

---

## 5. Global rank only : les prédictions per-symbol sont-elles nécessaires ?

**Oui, mécaniquement** — au-delà du gate de couverture, en backtest **et** en live.

### Backtest (`apply_cascade_to_predictions` → `cascade_select`)
1. **Présence obligatoire** : `pred = per_symbol_preds.get(symbol); if pred is None: continue` — un symbole sans ligne per-symbol est exclu même top 10 %.
2. **Veto `min_prob`** : `is_top and pred.long_prob > _min_prob` (0.55 classification / 0.10 régression).
3. **Score de classement** : `score = rank × proba_long`, puis `replay_signals` re-trie par `selection_score = proba_long` (slots limités).

### Live (pipeline)
- La sélection phase 2 est **ML-first** : exige des probas ternaires (`proba_long/proba_flat/proba_short` non nulles + `run_id`) dans `model_predictions`, sinon ligne rejetée.
- C'est la raison d'être de la **synthèse** : satisfaire ce contrat sans modèle per-symbol réel.
- Le filtre DIP live est appliqué **à la persistance** (dans `synthesize` via `_build_dip_long_set`), pas dans un `cascade_select` live (jamais appelé par le live).

### Nuance « informationnellement redondante »
En mode synthèse, `proba_long = rank` (monotone) :
- le veto `min_prob` ne bloque rien (top ⇒ proba > 0.90 > seuil) ;
- `score = rank²` monotone ⇒ l'ordre de sélection = ordre du rang seul.

⇒ La proba synthétisée n'ajoute **aucune information per-symbol**, mais les lignes `model_predictions` (avec run_id + probas) sont **mécaniquement requises**.

---

## 6. Synchronisation `global_rank_history` / `model_predictions` : le piège

- `predict_global_rank_history` → **`global_rank_history` uniquement**.
- `synthesize` → **`model_predictions` uniquement**.
- Si tu fais la prédiction **sans** relancer la synthèse → `model_predictions` reste périmée/vide → le gate mesure des trous → « couverture insuffisante » (qui n'est pas un trou de rangs mais une **synthèse non relancée**).

### Pipeline predict (historique, `--training-end-date`)
- `_process_date` : `predict_global_rank_history(day)` ; puis `if _per_sector or not _has_ps_models: return (_ds, 0)` (per-symbol skippé).
- Après la boucle : **filet de sécurité** (`cli.py:~1210`) :
  - `_per_sector` → `synthesize()` explicite ;
  - sinon si `_dates_with_data == 0` **et** rangs présents → **fallback `synthesize()`** (log : `predict 0 per-symbol rows MAIS rangs globaux présents → fallback synthèse`).
- Pour un batch global-only **propre**, `predict_symbol` retourne `None` pour chaque symbole (`if not config_path.exists(): return None`) → `_dates_with_data` reste 0 → **la synthèse tourne à chaque run** (déjà systématique en pratique).

### Backtest
Le backtest **ne synthétise jamais** : il lit `model_predictions` (`load_predictions`) et `global_rank_history` (`cascade_select`). Ordre obligatoire : **prédire avant de backtester**, et vérifier le log `fallback synthèse`.

---

## 7. Point 1 — Déclencheur historique explicite (NON appliqué, optionnel)

Condition actuelle (`cli.py:~1205`) : `if _dates_with_data == 0:` (fallback synthèse).

**Conclusion** : pour un batch global-only propre, c'est **déjà systématique** (`_dates_with_data == 0` toujours vrai). Une modification proposée mais **non requise** :
```python
# avant : if _dates_with_data == 0:
if _dates_with_data == 0 or not _has_ps_models:
```
- Utile uniquement comme **défense en profondeur** contre des artefacts **pollués** (champions per-symbol résiduels dans `artifacts/models/{batch}`) qui feraient produire des lignes au per-symbol par erreur.
- ⚠️ **Ne jamais rendre la synthèse inconditionnelle** : pour un batch AVEC modèles per-symbol, le `run_id` synth (`_globalrank_synth`) coexisterait avec les vraies lignes → risque de doublons multi-run dans `load_predictions` (ordre non déterministe dans `_pred_dict[symbol]`).

**Décision** : non appliqué (flux sain = pas nécessaire).

---

## 8. Point 2 — Complément live quotidien global-only (APPLIQUÉ ✅)

### Le trou identifié
Dans le chemin **live quotidien** (`--mode predict` **sans** `--training-end-date`, `cli.py:~1245`), la branche non-per_sector pour un batch global-only faisait :
```python
else:
    if not _has_ps_models:
        # Batch global-only : pas de per-symbol à prédire.
        preds = pd.DataFrame(...)   # ← VIDE : ni rangs ni synthèse
    else:
        preds = predict_batch(...)
```
→ ni `predict_global_rank_history` ni `synthesize` n'étaient appelés → `global_rank_history` **et** `model_predictions` non rafraîchis ce jour-là → gate de couverture KO en live.

### Correction appliquée (`modelFactory/cli.py`)
La branche global-only live reproduit désormais le comportement per_sector :
1. **Breadth guard** : `enforce_min_universe_breadth(_breadth, trade_date=_live_day, batch_id=_batch_id)` ;
2. `predict_global_rank_history(_day_str, _day_str, _batch_id, ...)` → rangs du jour ;
3. `synthesize(_batch_id, best_h=..., dip_config=_load_live_dip_config())` → `model_predictions` ;
4. `persisted_incrementally = True` (évite le double-insert en aval) ;
5. `preds = _load_synth_frame_for_range(engine, _batch_id, [_live_day])`.

Scoped strictement à `not _has_ps_models` (jamais pour les batchs avec modèles per-symbol).

### Logs de validation (après un predict live global-only)
```
predict global-only live ranks 2026-... : {...}
predict global-only live synthèse batch=model-factory-... : {'status': 'completed', ...}
```

---

## 9. Synthèse des décisions

| Point | Nécessaire ? | Statut |
|---|---|---|
| Gate par `--ml-batch-id` (jamais multi-batch) | Oui (déjà en place, `--ml-batch-id` obligatoire) | ✅ existant |
| `--min-ml-coverage-ratio 0` pour 2022 | Selon fenêtre | Décision opérateur |
| Branche rank-only dans `cascade_select` | Non (flux synthèse canonique) | ❌ non implémenté |
| Point 1 : déclencheur historique explicite `or not _has_ps_models` | Non (déjà systématique) | ❌ non appliqué (optionnel) |
| Point 2 : complément live quotidien global-only | **Oui** (live global-only) | ✅ **appliqué** |

---

## 10. Références clés

- `modelFactory/cli.py` : dispatch `predict`, filet de sécurité historique (~1205), complément live quotidien global-only (~1245+).
- `modelFactory/predictor.py` : `predict_global_rank_history`, `cascade_select` (2728), `apply_cascade_to_predictions` (3133), `predict_batch` (3461), `predict_symbol` (config absente → `None`).
- `modelFactory/synthesize_global_rank_predictions.py` : `synthesize` (INSERT idempotent), `_build_dip_long_set`.
- `backtesting/fidelity.py` : `evaluate_ml_coverage_gate` (2802).
- `backtesting/resilience.py` : `prepare_predictions_for_ml_mode` (374), `_expected_symbol_dates` (43).
- `backtesting/cli/_impl.py` : `_enforce_ml_coverage_gate` (2570), `load_predictions` (3170), résolution `_cascade_batch_id` (3306-3325), `apply_cascade_to_predictions` (3462), arrêt dur `_cas_passed == 0` (~3480), validation `--ml-batch-id` (5568).
- `backtesting/data_loader.py` : `load_predictions` (filtre batch via `JOIN model_training_run`).
- `backtesting/signal_replay.py` : `selection_score = proba_long`, tri/rank par proba (161-185).

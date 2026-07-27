# 🔀 Architecture Cascade — Plan d'Action

> **Date** : 2026-07-27
> **Objectif** : Architecture en cascade : Global Ranking filtre l'univers → Per-Symbol valide les trades. Le stacking (injection global_rank comme feature) reste optionnel via checkbox IHM.
> **Statut** : À implémenter

---

## 🧠 Principe

```
[ENTRAÎNEMENT]
1. Global Ranking Model → entraîné sur ~2000 symboles → global_rank_3, global_rank_5
2. Per-Symbol Models → stacking OPTIONNEL (checkbox IHM, défaut OFF)

[BACKTEST / LIVE]
1. Global Model prédit les rangs du jour (live) ou de l'historique (backtest)
2. Filtre TOP N% et BOTTOM N% selon global_rank_3 ET global_rank_5
3. Per-Symbol prédit la probabilité LONG/SHORT pour les candidats
4. Trade si : prob > seuil + dans les top/bottom N% 
```

---

## 📋 Points détaillés

### Point 1 — Stacking optionnel (checkbox IHM)

| Fichier | Action |
|---------|--------|
| `ihm/pages/_execution_center/__init__.py` | Checkbox "📥 Stacking (injecter global_rank dans per-symbol)" sous Paramètres d'exécution, défaut `False` |
| `ihm/services/pipeline_ml_defaults.py` | `DEFAULT_ML_ENABLE_GLOBAL_STACKING = False` |
| `modelFactory/trainer.py` | Quand `False`, les per-symbol sont entraînés SANS `global_rank_*` |
| `modelFactory/orchestrator.py` | Log de fin : `stacking_enabled=True/False` |
| `modelFactory/report.py` | Rapport .md : ligne `- **Stacking Global Rank** : Oui/Non` |
| `ihm/pages/ml_diagnostics.py` | Affichage du statut stacking dans le détail batch |

**Table DB** : ajouter colonne `stacking_enabled TINYINT(1) DEFAULT 0` dans `model_training_batch` (migration 0058).

---

### Point 2 — Univers élargi

Le Global Ranking peut tourner sur plus de 2000 symboles (tradable universe). Le paramètre `global_ranking_max_symbols` dans l'IHM (défaut 500) permet de limiter. Pour la cascade, on utilisera tous les symboles disponibles pour le ranking, puis le per-symbol filtrera.

---

### Point 3 — Règles de décision en cascade

Un trade est exécuté si **toutes** ces conditions sont remplies :

1. ✅ **Per-Symbol** prédit `LONG` avec probabilité > `cascade_min_prob` (défaut 0.55)
   — ou `SHORT` avec probabilité > `cascade_min_prob`
2. ✅ Le symbole est dans le **top N%** de `global_rank_3` ET dans le **top N%** de `global_rank_5` (pour LONG)
   — ou **bottom N%** des deux (pour SHORT)
3. ✅ Tri par score combiné multiplicatif :
   $$\text{score\_final} = \left( \frac{\text{global\_rank\_3} + \text{global\_rank\_5}}{2} \right) \times \text{prob\_per\_symbol}$$
   > Pourquoi multiplicatif : si le rang global est médiocre (0.30), le score s'effondre même avec une proba locale élevée → protection contre les trades à contre-courant du marché. Si les deux sont forts (0.90 × 0.70 = 0.63), le trade est prioritaire. L'additif (w1×rank + w2×prob) peut être trompé par un seul score élevé.
4. ✅ Limite de positions : gérée par le module risque (`risk_max_positions`), pas par la cascade

**Logique** :
```python
def cascade_select(date, global_ranks, per_symbol_preds, top_pct, min_prob):
    candidates = []
    for symbol, rank3, rank5 in global_ranks:
        # Condition 2 : dans les extrêmes des DEUX horizons
        is_top = rank3 > (1 - top_pct) and rank5 > (1 - top_pct)
        is_bottom = rank3 < top_pct and rank5 < top_pct
        if not (is_top or is_bottom):
            continue
        # Condition 1 : prob per-symbol
        pred = per_symbol_preds.get(symbol)
        if pred is None:
            continue
        if is_top and pred.long_prob > min_prob:
            score = (rank3 + rank5) / 2.0 * pred.long_prob  # multiplicatif
            candidates.append(('LONG', symbol, score))
        elif is_bottom and pred.short_prob > min_prob:
            score = ((1 - rank3) + (1 - rank5)) / 2.0 * pred.short_prob
            candidates.append(('SHORT', symbol, score))
    # Condition 4 : tri par score décroissant (limite gérée par risk_max_positions)
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates
```

---

### Point 4 — Paramétrage config.yaml

```yaml
cascade:
  top_pct: 0.20          # top/bottom 20% pour le filtre global
  min_prob: 0.55         # probabilité minimale per-symbol
```

Utilisé par le backtest ET le live pipeline.

---

### Point 5 — Prédiction Global + Per-Symbol dans ML Predict

**Workflow dans le bloc 10. ML Predict :**

1. L'utilisateur sélectionne une période de dates (ex: 2026-01-01 → 2026-06-30)
2. **Étape Global** : `predict_global_rank()` est appelé pour chaque date de la période. Les rangs prédits sont insérés/upsertés dans la table `global_rank_history` (écrase si déjà existant pour cette date+batch).
3. **Étape Per-Symbol** : les per-symbol sont prédits normalement (comme aujourd'hui).
4. **Backtest/Live** : la cascade lit `global_rank_history` (via le `batch_id` configuré) et le cache per-symbol pour filtrer.

| Fichier | Action |
|---------|--------|
| `modelFactory/predictor.py` | Nouvelle fonction `predict_global_rank_history(start_date, end_date, batch_id)` : pour chaque date, prédit les rangs et upsert dans `global_rank_history` |
| `ihm/pages/_execution_center/__init__.py` | Bloc 10 : avant de lancer les per-symbol, exécuter `predict_global_rank_history` si la cascade est activée |
| `config.yaml` | `batch_diagnostics.live_batch_id` / `backtest_batch_id` déterminent quel batch utiliser |

**Sources de données pour la cascade :**

| Source | Contenu | Utilisation |
|--------|---------|-------------|
| `_global_rank_cache.parquet` | Rangs d'entraînement (2018→2025) | Gardé tel quel, référence |
| `global_rank_history` (DB) | Rangs prédits (toute période) | Source unique pour backtest/live |
| Per-symbol `config.json` | Modèles par symbole | Prédiction locale |

> **Règle** : la table `global_rank_history` est la source de vérité pour la cascade. Le parquet reste un sous-produit du training. La table est peuplée/écrasée à chaque "Prédire l'univers sélectionné".

---

### Point 6 — Cohérence features + Table global_rank_history

**Table DB** — source unique des rangs pour backtest/live :
```sql
CREATE TABLE IF NOT EXISTS alpha_trade.global_rank_history (
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    global_rank_3 DOUBLE DEFAULT NULL,
    global_rank_5 DOUBLE DEFAULT NULL,
    global_rank_10 DOUBLE DEFAULT NULL,
    batch_id VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, batch_id),
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Peuplement :** uniquement lors du clic "Prédire l'univers sélectionné" dans le bloc 10. ML Predict. Si des rangs existent déjà pour (symbol, date, batch_id), ils sont écrasés (upsert).

| Composant | Vérification |
|-----------|-------------|
| **Global Model** | ✅ Déjà OK — `_global_ranking_features.json` sauvegarde les `feature_columns` + `horizon_features` + `include_*` flags. `predict_global_rank()` les utilise. |
| **Per-Symbol** | ✅ Déjà OK — `config.json` par symbole sauvegarde le `feature_fingerprint` + `feature_contract`. Le `predictor.py` vérifie la cohérence avant prédiction. |
| **Rangs historiques** | 🟡 À faire — `predict_global_rank_history()` lit le modèle global, prédit pour chaque date de la période, upsert dans `global_rank_history`. |
| **Cohérence batch** | `live_batch_id` / `backtest_batch_id` dans `config.yaml` détermine quel batch de modèles (global + per-symbol) utiliser. |

### Point 7 — Consultation des rangs historiques dans Diagnostic ML ✅

Dans `ihm/pages/ml_diagnostics.py`, une nouvelle section **🌐 Ranks Globaux Historiques** est ajoutée au détail de chaque batch. Elle permet de :
- Voir la plage de dates couvertes par `global_rank_history` pour le batch sélectionné
- Sélectionner une date précise et afficher les **Top N%** et **Bottom N%** des symboles selon `rank_avg_35 = (rank_3 + rank_5) / 2`
- Ajuster le seuil Top/Bottom % via un slider (5%–50%)
- Télécharger les rangs complets en CSV
- Visualiser les stats : nb symboles, médiane, taux de remplissage H3/H5

---

## 📋 Résumé des étapes

| # | Étape | Fichiers | Effort |
|:--:|-------|----------|:--:|
| 1 | Stacking optionnel (checkbox + DB + logs) | IHM, defaults, trainer, orchestrator, report, ml_diagnostics, DB | 1h |
| 2 | Paramètres cascade dans config.yaml | `config.yaml` | 15 min |
| 3 | Logique cascade dans predictor | `modelFactory/predictor.py` | 2h |
| 4 | Intégration backtest | `backtesting/` | 1h30 |
| 5 | Prédiction Global + Per-Symbol dans ML Predict | `ihm/`, `predictor.py` | 1h |
| 6 | Table global_rank_history + cohérence features | DB, `predictor.py` | 30 min |
| 7 | Consultation rangs historiques dans Diagnostic ML | `ihm/pages/ml_diagnostics.py` | ✅ Fait |

---

## ⚠️ Risques

1. **Top 20% trop restrictif** → trop peu de trades. Commencer à 25% et ajuster.
2. **Double condition H3+H5** → peut être trop stricte. Possibilité de passer en OU (top H3 OU top H5).
3. **Per-symbol F1 faible** → si F1 < 0.30, la cascade ne filtre rien de plus. Nécessite per-symbol de qualité.
4. **Latence** → interroger 200+ modèles per-symbol par jour. Doit être < 2s avec cache.


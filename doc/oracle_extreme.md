# Oracle Extreme — Gate d'univers LONG (composant officiel E6→E13)

**Statut :** composant intégré au code (config + `cascade_select` + tests ✅ 54/54),
**non câblé au pipeline live** (voir [§8 État du câblage](#8-etat-du-cablage-et-to-do)).

**Référence recherche :** `doc/synthese_e6_e13_2026-08-20.md` (branche E6→E13 **FERMÉE**).
**Baseline research gelée :** Oracle O0 → Extreme TOP20 → LONG-only → PROD lifecycle → **m24** → equal-weight 1/24.

---

## 1. Rôle

L'Oracle Extreme transforme la probabilité de **mouvement extrême** (`proba_extreme`,
Oracle O0) en un **gate d'univers LONG**, indépendant du ranking B25 (`global_rank_20`).

- **Ce n'est pas un ranker directionnel.** Il ne prédit pas la hausse/baisse.
- **C'est un filtre d'univers** : garde les top `pool_pct` (défaut 20 %) du jour par
  potentiel de mouvement extrême, puis on ne joue que **LONG** dans cet univers.
- **L'edge est empirique** (E8→E13) : le *top 20 % de `proba_extreme`* forme un univers
  porteur pour le LONG ; le classement interne des titres est secondaire.

> ⚠️ **SÉMANTIQUE (à ne jamais oublier)** : `proba_extreme` **≠ P(LONG)**. C'est le
> potentiel de **MOUVEMENT EXTRÊME** cross-sectionnel. L'orientation LONG est un choix
> empirique validé par la recherche, pas une propriété de la proba.

---

## 2. Architecture

```
modelFactory/oracle/
├── extreme_gate.py          # compute_extreme_gate() + build_oracle_rank_map()  (NOUVEAU)
├── train.py                 # entraînement Oracle Extreme + ablations O0/O1/O2 (S3)
├── walk_forward.py          # WF causal strict (oracle_available_date < test_start) + persist_oos()
├── dataset.py               # build_dataset() — features PIT + targets Oracle
├── build_labels.py          # build_labels() — labels Oracle H20 (global_oracle_labels)
├── config.py                # OracleConfig — horizon H20, top_pct 0.10, raw_target=True
└── combine.py               # second signal B25+Oracle (désactivé par défaut)

modelFactory/
├── predictor.py             # cascade_select(rank_mode="extreme_gate", oracle_rank_map=…)
│                            #   + load_extreme_gate_config() + apply_cascade_to_predictions()
└── orchestrator.py          # train_oracle_extreme() — pipeline O0 (labels→dataset→WF→OOS)

config.yaml                  # section `extreme_gate:` (enabled / pool_pct / long_only / min_prob)
```

### Dépendances data

| Donnée | Source |
|---|---|
| `proba_extreme` | Parquet OOS du walk-forward Oracle : `artifacts/models/oracle/oracle-wf-<run_id>/oos_predictions.parquet` |
| Pool features + `proba_extreme` + `atr_pct_20` | Recherche : `scripts/e6_b2_ev_long_backtest.load_pool()` (merge_pools) |
| OHLCV | `artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet` |

---

## 3. Mécanique (PIT, aucun lookahead)

```
Oracle O0 → proba_extreme (calculé à D avec les données ≤ D)
   → percentile cross-sectionnel DU JOUR : rank(pct=True) dans la journée
   → extreme_pct ≥ 1 − pool_pct  ⇔  extreme_gate = True  (défaut : top 20 %)
   → candidates LONG (side="buy") → sizing equal-weight 1/m → lifecycle PROD
```

- Le gate est **cross-sectionnel par jour** : on classe les candidats du jour *entre eux*.
- **Aucune information future** : ni seuil global, ni rang de J+1.
- `pool_pct ≤ 0` garde tout ; `pool_pct ≥ 1` garde le percentile max.

---

## 4. Config `config.yaml`

```yaml
extreme_gate:
  enabled: false          # ⚠️ INFORMATIF — voir §8 (le vrai interrupteur est rank_mode)
  pool_pct: 0.20          # univers : top 20 % du jour par proba_extreme
  long_only: true         # ⚠️ INFORMATIF — la branche est LONG-only en dur dans le code
  min_prob: null          # per-symbol min ; null = défaut cascade min_prob_regression
```

| Paramètre | Défaut | Consommé par | Effet |
|---|---|---|---|
| `enabled` | `false` | **Aucun code** (lu mais non utilisé comme interrupteur) | Voir §8 |
| `pool_pct` | `0.20` | `cascade_select` (L2675-2676) et `compute_extreme_gate` | Taille de l'univers |
| `long_only` | `true` | **Aucun code** (hardcodé `is_bottom = False`) | LONG-only garanti |
| `min_prob` | `null` | `cascade_select` (L2689-2691) | Seuil per-symbol ; `null` → `min_prob_regression` (0.10) |

> **Bloc voisin `cascade:`** (inchangé) : `top_pct: 0.10`, `min_prob_classification: 0.55`,
> `min_prob_regression: 0.10`, `short_momentum_filter: none`, `short_momentum_max_pct: null`.

---

## 5. Flux dans `cascade_select` (`rank_mode="extreme_gate"`)

```mermaid
flowchart TD
    A["Oracle O0<br/>oracle_rank_map {date: {symbol: proba_extreme}}"] --> B["percentile cross-sectionnel du jour<br/>pd.Series(values).rank(pct=True)"]
    B --> C{"rank ≥ 1 − pool_pct ?"}
    C -- oui (top 20 %) --> D{"per_symbol_preds[symbol] ?<br/>pred.long_prob > min_prob ?"}
    C -- non --> X["is_bottom = False<br/>AUCUN SHORT possible"]
    D -- oui --> E["LONG — score = rank × long_prob"]
    D -- non --> X2["Rejeté (flat)"]
    E --> F["Tri par score décroissant → candidates (side, symbol, score)"]
```

| Étape | Modèle concerné | Comportement |
|---|---|---|
| **Global B25** (`global_rank_20`) | ❌ **PAS utilisé** | `load_global_ranks_from_db()` n'est **pas** appelé — le rang vient de l'`oracle_rank_map` seul |
| **Per-symbol** | ✅ **Oui** | Exigé pour chaque symbole retenu ; filtre `long_prob > min_prob` |
| **Per-sector** | ❌ **Non** | `cascade_select` n'a pas de dimension sectorielle ; sortie = `(side, symbol, score)` |
| **SHORT** | 🚫 **Jamais** | `is_bottom = False` hardcodé (predictor.py L2800) |

Code clé :

```python
# predictor.py L2799-2801 — la branche extreme_gate
if _mode_extreme_gate:
    is_top = rank is not None and rank >= (1.0 - _extreme_gate_pct)
    is_bottom = False  # LONG-only
```

---

## 6. Fonctions du module `modelFactory/oracle/extreme_gate.py`

### `compute_extreme_gate(df, pool_pct=0.20, proba_col="proba_extreme", date_col="date")`

Ajoute au DataFrame :
- `extreme_pct` : percentile cross-sectionnel de `proba_extreme` **dans le jour**
  (1.0 = plus haut du jour). PIT.
- `extreme_gate` : booléen `extreme_pct >= 1 - pool_pct`.

```python
from modelFactory.oracle.extreme_gate import compute_extreme_gate
df = compute_extreme_gate(df, pool_pct=0.20)   # colonnes date, symbol, proba_extreme
```

### `build_oracle_rank_map(df, proba_col="proba_extreme", date_col="date")`

Construit `{date: {symbol: proba_extreme}}` à passer à
`cascade_select(rank_mode="extreme_gate", oracle_rank_map=...)`.

```python
from modelFactory.oracle.extreme_gate import build_oracle_rank_map
rank_map = build_oracle_rank_map(oos_df)   # oos_df = parquet OOS Oracle
```

---

## 7. Utilisation en PRODUCTION (pipeline)

### Entraînement de l'Oracle O0

- **Flag :** `modelFactory/config.py` → `enable_oracle_model: bool = False` (défaut) ;
  IHM → `ihm/services/pipeline_ml_defaults.py` → `DEFAULT_ML_ENABLE_ORACLE_MODEL = False`.
- **Déclenchement :** `modelFactory/orchestrator.py` → `train_oracle_extreme()` (L467) —
  pipeline : labels H20 → dataset → walk-forward causal O0 → `persist_oos()` sous
  `artifacts/models/oracle/oracle-wf-<run_id>/`.
- **Anti-leakage :** `oracle_available_date < test_start` (T2), folds expansifs
  (`modelFactory/oracle/walk_forward.py`).

### Appel à l'inférence (sélection)

```python
from modelFactory.predictor import apply_cascade_to_predictions, load_extreme_gate_config

preds_df = apply_cascade_to_predictions(
    preds_df, batch_id, engine=engine,
    rank_mode="extreme_gate",
    oracle_rank_map=build_oracle_rank_map(oos_df),  # {date: {symbol: proba_extreme}}
    extreme_gate_pct=None,   # None → pool_pct de la config (0.20)
)
```

- Les symboles retenus gardent `predicted_side` ; les autres passent `flat` (exclus du backtest).
- **Sizing :** m24 = `max_positions=24`, equal-weight `1/24` (budget de risque total constant).

### Checklist production candidate

1. `extreme_gate.enabled: true` (pour la trace — ne pilote pas le code, cf. §8).
2. Câbler `rank_mode="extreme_gate"` + `oracle_rank_map` au call-site live
   `backtesting/cli/_impl.py` (à faire — §8).
3. Activer l'entraînement Oracle O0 (`enable_oracle_model = True`).
4. `max_positions = 24`.
5. Lifecycle PROD figé (stop 2.5×ATR / TP min(3×ATR,7%) / trailing 2.5×ATR / time_stop OFF / gap 3% / 16bps).

---

## 8. État du câblage et TO-DO

### ⚠️ Point critique : `enabled: true` ne suffit PAS

- `load_extreme_gate_config()` (predictor.py L2043) **lit** `enabled`, `pool_pct`,
  `long_only`, `min_prob` — mais **aucun code ne consomme `enabled`** comme interrupteur.
- Le vrai interrupteur est le **paramètre** `rank_mode="extreme_gate"` passé à
  `cascade_select()` / `apply_cascade_to_predictions()` (L2677).
- `long_only` est **aussi informatif** : la branche est LONG-only en dur (`is_bottom=False`).

### Câblage live NON FAIT

Dans `backtesting/cli/_impl.py` (L3112-3131) :
- l'`oracle_rank_map` n'est chargé que pour `oracle / oracle_filter / oracle_rerank / oracle_pool`
  (S6.1) — **pas** pour `"extreme_gate"` ;
- `extreme_gate_pct` n'est pas transmis.

→ Passer `rank_mode="extreme_gate"` au CLI aujourd'hui → `oracle_rank_map=None` → warning
"no oracle ranks" → `return []` (aucun trade).

### TO-DO pour rendre le composant réellement activable

| # | Action | Fichier |
|---|---|---|
| 1 | Charger l'`oracle_rank_map` aussi pour `rank_mode == "extreme_gate"` (parquet OOS Oracle) | `backtesting/cli/_impl.py` |
| 2 | Passer `extreme_gate_pct` à `apply_cascade_to_predictions` | `backtesting/cli/_impl.py` |
| 3 | *(Optionnel)* consommer `enabled`/`long_only` de la config pour piloter le mode | `predictor.py` / call-site |

---

## 9. Utilisation en BACKTEST

### Chemin recherche (scripts E6→E13) — le plus simple

Les scripts réutilisent `build_signals()` + `make_engine()` de
`scripts/e11_extreme_long_payoff_diag.py` :

```python
from scripts.e11_extreme_long_payoff_diag import build_signals, load_pool, load_pivots

pool = load_pool()                                  # features + proba_extreme + atr_pct_20
pivots = load_pivots()                              # open/close/high/low/volume
sig = build_signals(pool, 0.80, 1.01, seed=7)       # Extreme TOP20 (percentile ≥ 0.80)
res = make_engine(m=24).run(open_df=pivots["open"], close=pivots["close"],
                            high=pivots["high"], low=pivots["low"],
                            signals_df=sig, volume=pivots["volume"])
```

- `build_signals(pool, lo=0.80, hi=1.01, seed)` : filtre `_pe_pct >= 0.80` (top 20 %) par
  `proba_extreme`, rang aléatoire intra-date (seed) pour isoler l'edge du gate vs le ranking,
  `score = proba_extreme`, `side="buy"` (**LONG-only**).
- `make_engine(m)` (variante PROD, `scripts/e13_capacity_diversification.py`) :
  `atr_risk_stop_multiple=2.5`, `initial_stop_atr_multiple=2.5`, `tp_atr_multiple=3.0`,
  `tp_max_pct=0.07`, `trailing=None`, `time_stop_enabled=False`,
  `microstructure(max_entry_gap_pct=0.03, intrabar_priority="conservative")`, 16bps.
- ⚠️ `make_engine()` d'**E11** est le **E-LIFECYCLE** (stop 3.5×ATR, TP 13%, trailing 7%,
  time_stop ON) — **référence historique uniquement**. Toute expérience part du **PROD lifecycle + m24**.

### Chemin pipeline (backtest CLI)

Même mécanisme qu'en production mais avec `apply_cascade_to_predictions(...)` sur les
prédictions du batch — sujet au même **câblage manquant** (§8) : il faut charger
l'`oracle_rank_map` depuis le parquet OOS avant l'appel.

---

## 10. Résultats de référence (recherche, 50 seeds — E13-B)

| Métrique | m24 (baseline) |
|---|---|
| Return médian | **61.6 %** |
| P10 / P25 / P90 | 41.1 % / 46.8 % / 88.3 % |
| Pire seed | **+23.5 %** (100 % seeds positifs) |
| PF | 1.13 |
| Sharpe | 0.45 |
| DD | −22.6 % |
| Dispersion P90−P10 | 47 (vs 113 en m8, −59 %) |

**Message central :** m24 n'améliore **pas** le signal prédictif — il améliore sa
**monétisation** (réduction du risque d'échantillonnage). L'edge est dans l'appartenance à
l'univers Extreme, pas dans le ranking.

---

## 11. Garde-fous / NO-GO (ne pas réintroduire)

- **Pas de `global_rank_20` comme source de l'edge** (le rang interne ne porte pas la valeur).
- **Pas de Y3 directionnel** en production (filtre destructeur, E7).
- **Pas de Platt / EV_LONG** (pur re-ranking, E6-B4).
- **Pas de filtre NO-TRADE / TRUE_BAD** (non séparable, E12-1A).
- **Pas de modification TP/SL/trailing** (stop initial inerte, trailing négatif, E12-2B/C).
- **Pas de SHORT** (chantier séparé ; E8 : −86.8 %).
- **Risque résiduel 2026H1** : semestre faible (16-28 % seeds positifs) sous toutes les
  configs testées — risque officiel, **non à optimiser maintenant**.

---

## 12. Liens

- Synthèse de clôture : `doc/synthese_e6_e13_2026-08-20.md`
- Spec Oracle : `doc/ml_oracle.md` / `doc/ml_oracle_sprint.md`
- Module gate : `modelFactory/oracle/extreme_gate.py`
- Branch `cascade_select` : `modelFactory/predictor.py` (~L2670-2801, L2880-2995)
- Entraînement O0 : `modelFactory/orchestrator.py` (`train_oracle_extreme`, L467)
- Tests : `tests/test_cascade_ml.py` (54/54 ✅ — dont 3 nouveaux tests extreme_gate)
- Scripts recherche : `scripts/e11_extreme_long_payoff_diag.py`, `scripts/e13_capacity_diversification.py`, `scripts/e13b_baseline_confirmation.py`

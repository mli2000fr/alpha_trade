# Oracle Extreme — Gate d'univers LONG (composant officiel E6→E13)

**Statut :** composant intégré au code (config + `cascade_select` + tests ✅ 54/54),
**câblé au backtest CLI** (`--cascade-rank-mode extreme_gate` + variantes E17/E18),
**non câblé au pipeline live** (voir [§8 État du câblage](#8-etat-du-cablage-et-to-do)).

**Référence recherche :** `doc/synthese_e6_e13_2026-08-20.md` (branche E6→E13 **FERMÉE**).
**Baseline research gelée :** Oracle O0 → Extreme TOP20 → LONG-only → PROD lifecycle → **m24** → equal-weight 1/24.
**Résultats production CLI (E16-D/E17/E18) :** voir [§13 Résultats CLI corrigés + E19](#13-correction-2026-08-20--bug-atrpct20--resultats-cli-finaux--e19).
**⚠️ 2026-08-20 :** les +146 % historiques étaient faussés par un bug `atr_pct_20`
(TP 12 %/SL 7 % au lieu de config prod) — **valeurs corrigées en §13** (EXT A = +113,1 %, B25 long-only = +175,7 %).

> **⚠️ NATURE DU « PER-SYMBOL » (audit DB 2026-08-20)** : le batch B25 est **per_sector**
> (mode d'entraînement), **sans modèle per-symbol**. Le `long_prob` / `proba_long` consommé
> par le flux **n'est PAS un vrai modèle per-symbol** : c'est le **rang global H10 synthétisé**
> (`proba_long = global_rank_10`, corr = 1,0 — `synthesize_global_rank_predictions`). Ni le
> per-symbol ni le per-sector n'alimentent réellement le signal : tout est **rank-driven**
> (rang global B25). Les 11 modèles per-sector sont entraînés mais **inutilisés** par la cascade.

---

## 📚 Documents liés

- [`doc/mode_cascade.md`](mode_cascade.md) — les **7 modes de cascade** (`ml`, `oracle`,
  `oracle_filter`, `oracle_pool`, `oracle_rerank`, `extreme_gate`, `random`) et comment
  combiner Global Rank × Oracle Extreme (dont la clarification « pourquoi B25 »).
- [`doc/calibration_oracle_exterme.md`](calibration_oracle_exterme.md) — calibration de
  `proba_extreme` (`none` | `rank` | `isotonic`) et la différence entre les méthodes.

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
├── walk_forward.py          # WF causal strict (oracle_available_date < test_start) + persist_oos() → table
├── predictions_store.py     # table oracle_extreme_predictions : write/load (table-only)
├── predict_history.py       # prédiction standard sans retrain (champions) → table
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
| `proba_extreme` | **Table `oracle_extreme_predictions`** (stockage table-uniquement) — écrite par `persist_oos` (walk-forward) ET la prédiction standard (`predict_oracle_extreme_history`) ; lue au backtest via `--oracle-batch-id` (filtre batch strict) |
| Pool features + `proba_extreme` + `atr_pct_20` | Recherche : `scripts/e6_b2_ev_long_backtest.load_pool()` (merge_pools) |
| OHLCV | `artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet` |

> 📦 **Stockage (2026-08-28) — table-uniquement** : les prédictions `proba_extreme`
> sont stockées dans `oracle_extreme_predictions` (PK `(prediction_date, symbol, batch_id)`,
> **sans `run_id`** → toute ré-écriture d'un même couple écrase, pas de doublons entre runs).
> Le walk-forward (`persist_oos`) et la prédiction standard alimentent la même table.
> Le parquet `artifacts/models/oracle/oracle-wf-<run_id>/oos_predictions.parquet` n'est **plus
> écrit ni lu** ; `--oracle-oos-path` (parquet legacy) reste un fallback, `--oracle-batch-id`
> (table) est la voie recommandée.

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
    C -- oui (top 20 %) --> D{"per_symbol_preds[symbol] ?<br/>pred.long_prob (rang global B25 H10) > min_prob ?"}
    C -- non --> X["is_bottom = False<br/>AUCUN SHORT possible"]
    D -- oui --> E["LONG — score = rank × long_prob"]
    D -- non --> X2["Rejeté (flat)"]
    E --> F["Tri par score décroissant → candidates (side, symbol, score)"]
```

| Étape | Modèle concerné | Comportement |
|---|---|---|
| **Global B25** (`global_rank_20`) | ❌ **PAS utilisé** | `load_global_ranks_from_db()` n'est **pas** appelé — le rang vient de l'`oracle_rank_map` seul |
| **`long_prob` B25** (⚠️ = **rang global H10** synthétisé, PAS un modèle per-symbol) | ✅ **Oui** | Exigé pour chaque symbole retenu ; filtre `long_prob > min_prob` |
| **Per-sector** | ❌ **Non** | `cascade_select` n'a pas de dimension sectorielle ; sortie = `(side, symbol, score)` |
| **SHORT** | 🚫 **Jamais** | `is_bottom = False` hardcodé (predictor.py L2800) |

Code clé :

```python
# predictor.py L2799-2801 — la branche extreme_gate
if _mode_extreme_gate:
    is_top = rank is not None and rank >= (1.0 - _extreme_gate_pct)
    is_bottom = False  # LONG-only
```

### 5.1 — Flux PRODUCTION complet (`python -m backtesting run --cascade-rank-mode extreme_gate ...`)

Le run CLI (E16-D, preset `capital_2001_5000`) enchaîne **deux filtres successifs** + la pile production :

```mermaid
flowchart TD
    A["Oracle O0 (walk-forward OOS)<br/>proba_extreme par (date, symbol)"] --> B["oracle_rank_map<br/>{date: {symbol: proba_extreme}}"]
    B --> C["percentile cross-sectionnel DU JOUR<br/>rank(pct) de proba_extreme"]
    C --> D{"GATE : rank >= 1 − pool_pct ?<br/>(top 20% du jour)"}
    D -- non --> X["Rejeté (flat)"]
    D -- oui --> E{"long_prob B25 = rang global H10 :<br/>long_prob > min_prob ?<br/>(0.55 en classification)"}
    E -- non --> X
    E -- oui --> F["LONG — score = rank × long_prob<br/>(LONG-only, is_bottom=False)"]
    F --> G["Pile production :<br/>preset capital_2001_5000 / equity 4000$<br/>risk / sizing / exécution / coûts canoniques"]
    G --> H["Portefeuille final + report.json"]
```

- **Le gate** (Étape 1) : filtre Oracle sur `proba_extreme` (mouvement extrême, **pas** P(LONG)), percentile intra-jour, top `pool_pct` — LONG-only.
- **Le `long_prob` B25** (Étape 2) : ⚠️ **= rang global H10 synthétisé** (`proba_long = global_rank_10`), **pas un vrai modèle per-symbol** ; filtre `long_prob > min_prob` — confirmation directionnelle.
- **La pile production** : le preset capital (petit compte), le sizing, le risque, l'exécution next-open, les coûts canoniques.

> ⚠️ Interprétation : le résultat CLI = **gate + long_prob (rang global B25 H10) + pile production**, pas le gate seul. Le gate seul (recherche, E16-C) donnait ~23 % en médiane — la différence vient du filtre `long_prob` (= rang global B25) et du pipeline.
>
> ⚠️ **2026-08-20 — RÉSULTATS CLI PRÉ-FIX INVALIDÉS** : les +146 % (E16-D/E17) étaient **falsifiés par un bug de câblage `atr_pct_20`** (TP tombé à 12 % fixe / SL 7 % fixe au lieu de TP prod `min(3×ATR,7%)` / stop 2,5×ATR). **Valeurs CORRIGÉES (config prod) : EXT A = +113,1 %**, B25 long-only = +175,7 % — cf. §13.

### 5.2 — Variantes du rôle per-symbol (E17, flag `--extreme-gate-per-symbol`)

Le `long_prob` B25 intervient à **2 endroits** dans le flux (⚠️ **`long_prob` = rang global H10 synthétisé**, pas un vrai modèle per-symbol) :

1. **VETO** (sélection) : `long_prob > min_prob` (0.55) — rejette un candidat du top 20 %.
2. **RANG** (priorité) : `replay_signals` classe par `proba_long` (= long_prob) → c'est **lui** qui décide qui entre dans `max_positions` (pas `cascade_score`, inutilisé en aval).

Trois variantes câblées (`--extreme-gate-per-symbol`) :

| Variante | VETO `long_prob > min_prob` | RANG / priorité |
|---|---|---|
| **A `filter`** (actuel) | ✅ oui (0.55) | `long_prob` (= rang global B25 H10, via `proba_long`) |
| **B `no_filter`** | ❌ non | `long_prob` (= rang global B25 H10) |
| **C `bypass`** (Oracle pur) | ❌ non | **percentile Oracle O0** — `proba_long` est écrasé par le score `rank` |

**Câblage de C (`bypass`)** — ne pas juste changer le score en amont :

- `cascade_select` : `score = rank` (percentile O0), `long_prob` ignoré (ni veto ni score).
- `apply_cascade_to_predictions` : `proba_long = score (percentile O0)`, `proba_short = 0`, `predicted_side = "long"` — indispensable car `replay_signals` classe par `proba_long`. Sans cet écrasement, le `long_prob` (rang global B25) continuerait de classer.

```python
# predictor.py — branche extreme_gate (E17)
if _mode_extreme_gate:
    if _eg_ps_mode == "bypass":                       # C : Oracle pur
        candidates.append(("LONG", symbol, rank))
    else:
        _eg_pred = per_symbol_preds.get(symbol)
        if _eg_pred is None:
            continue
        if _eg_ps_mode == "no_filter" or _eg_pred.long_prob > _min_prob:  # B / A
            candidates.append(("LONG", symbol, rank * _eg_pred.long_prob))
    continue
```

```python
# apply_cascade_to_predictions — bypass : proba_long = percentile O0
if _eg_ps_bypass:
    _oscore = _score_map.get(_sym)
    result.loc[_pm, "proba_long"] = float(_oscore) if _oscore is not None else 0.0
    result.loc[_pm, "proba_short"] = 0.0
    result.loc[_pm, "predicted_side"] = "long"
    continue
```

Utilisation CLI :

```bash
--cascade-rank-mode extreme_gate \
--oracle-batch-id <batch_oracle> \   # table oracle_extreme_predictions (remplace --oracle-oos-path)
--extreme-gate-pct 0.20 \
--extreme-gate-per-symbol filter   # | no_filter | bypass
```

### 5.3 — Branche SHORT optionnelle (E18, flag `--extreme-gate-shorts`)

Le gate Extreme est **LONG-only par défaut**. Le flag `--extreme-gate-shorts` (défaut OFF)
active une branche SHORT symétrique dans le gate top20 :

```
LONG  = gate ∩ long_prob > min_prob            (0.55)
SHORT = gate restants ∩ short_prob > min_prob  (≈ long_prob < 0.45)
REST  = NO TRADE
```

> ⚠️ **NO-GO mesuré (E18-A + E18-B)** : le `long_prob` B25 (= rang global H10) est une
> classification **binaire pure** (`short_prob ≡ 1 − long_prob`, corr = −1.000000, `proba_flat` = 0 constant). La queue
> basse de `long_prob` est **aussi haussière que le reste du pool** (P(ret<0) H20 ≈ 47 % vs
> 47.6 % global ; MAE short −10.4 % > MFE short +8.6 %). En backtest réel (config corrigée,
> cf. §13) : **EXT short-only = −57.4 %** (Sharpe −1.43, PF 0.675) et **EXT L+S fait chuter
> le run de +113,1 % à +97,0 %**.
> → **SHORT reste FERMÉ**, le flag est câblé mais **ne doit pas être activé**.

Code :

```python
# predictor.py — branche extreme_gate (E18)
if _eg_ps_mode == "no_filter" or _eg_pred.long_prob > _min_prob:
    candidates.append(("LONG", symbol, rank * _eg_pred.long_prob))
elif _eg_shorts and _eg_pred.short_prob > _min_prob:
    candidates.append(("SHORT", symbol, rank * _eg_pred.short_prob))
```

```python
# apply_cascade_to_predictions — forçage du côté (E17 fix + E18)
_side = _side_map.get(_sym, "LONG")
if _side == "SHORT":
    result.loc[_pm, "proba_short"] = _cp.short_prob
    result.loc[_pm, "proba_long"] = 0.0
    result.loc[_pm, "predicted_side"] = "short"
else:
    result.loc[_pm, "proba_short"] = 0.0
    result.loc[_pm, "predicted_side"] = "long"
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
rank_map = build_oracle_rank_map(oos_df)   # oos_df = load_oracle_predictions(engine, batch_id=…) (table)
```

---

## 7. Utilisation en PRODUCTION (pipeline)

### Entraînement de l'Oracle O0

- **Flag :** `modelFactory/config.py` → `enable_oracle_model: bool = False` (défaut) ;
  IHM → `ihm/services/pipeline_ml_defaults.py` → `DEFAULT_ML_ENABLE_ORACLE_MODEL = False`.
- **Déclenchement :** `modelFactory/orchestrator.py` → `train_oracle_extreme()` (L467) —
  pipeline : labels H20 → dataset → walk-forward causal O0 → `persist_oos()` →
  **table `oracle_extreme_predictions`** (stockage table-uniquement, plus de parquet).
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

### ✅ Câblage BACKTEST CLI — FAIT (E16-D, E17, E18)

Depuis E16-D, le CLI `python -m backtesting run` câble complètement le gate Extreme :

```bash
python -m backtesting run ... \
  --cascade-rank-mode extreme_gate \
  --oracle-batch-id <batch_oracle> \   # table oracle_extreme_predictions (filtre batch strict)
  --extreme-gate-pct 0.20 \
  [--extreme-gate-per-symbol filter|no_filter|bypass] \
  [--extreme-gate-shorts]                    # E18 : branche SHORT optionnelle (NO-GO)
```

- `backtesting/cli/_impl.py` : `oracle_rank_map` chargé pour `"extreme_gate"` (+ oracle_modes),
  `extreme_gate_pct` / `extreme_gate_per_symbol` / `extreme_gate_shorts` transmis à
  `apply_cascade_to_predictions`.
- `modelFactory/predictor.py` : variantes per-symbol (A/B/C, §5.2) + shorts optionnels (§5.3).

### ❌ Câblage LIVE — NON FAIT

Le pipeline de production live (`ihm/services/pipeline_runner.py`, `risk_management/`,
`execution_engine/`) **n'appelle pas** `cascade_select` / `apply_cascade_to_predictions`.
Le gate Extreme (LONG et SHORT) est aujourd'hui un composant **backtest/recherche uniquement**.

### TO-DO pour rendre le composant réellement activable en live

| # | Action | Fichier |
|---|---|---|
| 1 | Brancher `rank_mode="extreme_gate"` + `oracle_rank_map` au call-site live (à partir de la table `oracle_extreme_predictions`) | `ihm/services/pipeline_runner.py` |
| 2 | Rendre `enabled`/`long_only` de la config réellement consommés (interrupteur) | `predictor.py` / call-site |

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
l'`oracle_rank_map` depuis la table `oracle_extreme_predictions` (via `load_oracle_predictions`)
avant l'appel.

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

---

## 13. CORRECTION 2026-08-20 — bug `atr_pct_20` + résultats CLI finaux + E19

### 13.1 Le bug (invalidait les résultats CLI E16-D/E17/E18)

Symptôme : le profil des trades était **anormal** — TP sortis à **+12 % fixe** et
« trailing » perdants à **−7 % fixe**, au lieu de TP prod `min(3×ATR, 7 %)` et
stop/trailing `2,5×ATR`.

**Cause racine (tracé complet du pipeline) :**

- `atr_pct_20` est **rempli à 100 %** dans `stock_scores_history` (source PIT).
- Mais dans `replay_signals`, le merge se faisait sur `(symbol, trade_date)` **exact** ;
  les snapshots ne couvrant que ~17 % des dates de trading, **83 % des signaux avaient
  `atr_pct_20 = NaN`**.
- Sans `atr_pct_20`, le simulateur retombait sur les **défauts CLI** :
  - TP = `profit_taker_pct` = **12 %** (`--tp` défaut) au lieu de `min(3×ATR, 7 %)`
  - `risk_per_share` = None → **pas de stop initial ATR**, trailing = `--ts` = **7 % fixe**
- Les flags `--atr-risk-stop-multiple 2.5 --tp-atr-multiple 3.0 --tp-max-pct 0.07`
  étaient donc **totalement ignorés**. Le bug affectait **tous les runs CLI** de la
  session (pas les runs recherche, qui chargent `atr_pct_20` depuis les path labels).

**Impact sur les chiffres** (TP 12 %/SL 7 % gonflait les gains en régime haussier) :

| Run | AVANT fix (bug TP12/SL7) | APRÈS fix (config prod) |
|---|---|---|
| B25 long-only | +218,3 % | **+175,7 %** |
| EXT A | +146,1 % | **+113,1 %** |

### 13.2 Le fix (2 points, sans toucher modèle/gate/m24/lifecycle/coûts)

1. `backtesting/signal_replay.py` — **merge asof** de `atr_pct_20` : dernier snapshot
   disponible ≤ date du signal (PIT) au lieu du merge exact.
2. `backtesting/cli/_impl.py` — **fallback OHLCV** : pour les signaux encore sans
   `atr_pct_20` (symboles sans snapshot), calcul `ATR20/close` depuis les barres du
   backtest. Couverture mesurée : **100 % (EXT A) / 98,2 % (B25)**.

Vérif SL : le stop initial 2,5×ATR est redevenu **actif** (67 trades sur 402 EXT A, vs 1
avant) et le trailing est **variable** (2,5×ATR). Les DD −28 à −37 % restants sont réels
(volatilité SMCI/RHI/SMMT + levier ~1,5× + exécution au gap).

### 13.3 Résultats CLI finaux (config prod corrigée, preset 2001_5000 @ 4000 $, 2025-01-02 → 2026-05-29)

| Run | Ret % | Sharpe | DD % | PF | Trades | L/S |
|---|---|---|---|---|---|---|
| **B25 long-only** 🏆 | **+175,7** | **1,66** | **−28,2** | 1,330 | 396 | 396/0 |
| **EXT A (long, long_prob)** | +113,1 | 1,24 | −37,3 | 1,253 | 402 | 402/0 |
| EXT long+short | +97,0 | 1,31 | −33,3 | 1,215 | 407 | 348/59 |
| EXT C (bypass / Oracle pur) | +63,4 | 0,92 | −33,4 | 1,164 | 440 | 440/0 |
| B25 long+short | +39,1 | 0,98 | −17,1 | 1,110 | 362 | 165/197 |
| B25 short-only | −31,5 | −0,67 | −51,7 | 0,822 | 329 | 0/329 |
| EXT short-only | −57,4 | −1,43 | −60,4 | 0,675 | 412 | 0/412 |

**Verdicts :**
- 🏆 **B25 long-only +175,7 %** (meilleur retour, Sharpe 1,66, DD le plus faible).
- **Le `long_prob` apporte une vraie valeur** (⚠️ = rang global B25 H10, pas un vrai per-symbol) :
  EXT A (+113,1 %) vs EXT C/Oracle pur (+63,4 %) → **+50 pp** apportés par le ranking `long_prob`, en config prod.
- **SHORT = NO-GO confirmé** : B25 short-only −31,5 %, EXT short-only −57,4 %.
- **Long-only > L+S** : B25 (+176 vs +39) et EXT (+113 vs +97).

### 13.4 E19 — valeur conditionnelle du `long_prob` = rang global B25 (protocole complet)

Moteur recherche PROD-contract (même gate/m24/lifecycle/coûts/`atr_pct_20` que B2),
**aucun seuil tuné**.

| Point | Résultat |
|---|---|
| **1-2.** Placebo 100 permutations intra-date de `long_prob` | REAL = **65,0 %** → percentile **100 %** (max placebo 52,7 %) → **GO FORT** |
| **3.** SELECTED vs REJECTED (date identique) | SELECTED H20 **2,3 %** vs REJECTED **1,4 %** |
| **4.** Gradient par quintile | Q1=1,7 % → Q5=**2,3 %**, MFE/MAE 1,11→1,18, TRUE_BAD 35,5 %→29,9 % |
| **5.** Stabilité semestrielle | spread SEL−REJ : 2025H1 +0,9 · 2025H2 **+3,7** · 2026H1 −0,1 |
| **6.** VETO 0,55 vs RANKING (`e19_i_veto_vs_ranking.py`) | **veto = NEUTRE** (full 65,0 % = no_veto 65,0 %) · **ranking = +23,2 pp** (65,0 % vs veto_only 41,8 %) |

**Verdict E19 : H1 CONFIRMÉ** — le `long_prob` (= rang global B25 H10, **pas un vrai
per-symbol**) porte une **information conditionnelle réelle**, portée par le **ranking**
(pas le veto 0,55). Le +113 % / +176 % ne vient pas de la variance de sélection du pool
Extreme — c'est la **valeur du rang global B25 dans l'univers Oracle**.

**Question TP 12 % vs TP ATR** (2025-2026, marché haussier) : TP fixe 12 % surperforme
(+33 à +43 pp, meilleur Sharpe) — mais c'est un comportement de régime haussier ; le TP
ATR reste plus robuste en régime baissier/latéral. À re-tester sur 2022-2024 avant décision.


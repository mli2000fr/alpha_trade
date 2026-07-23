# 🔍 Filtre ML — Diagnostics batch pour live & backtest

> **Créé le** : 2026-07-23  
> **Module** : `modelFactory/batch_diagnostics.py`  
> **Table** : `alpha_trade.model_batch_diagnostics`  
> **Migration** : `alembic/versions/0054_add_model_batch_diagnostics.py`

---

## 🎯 Objectif

À la fin de chaque campagne d'entraînement (`modelFactory --mode train`), on snapshot les diagnostics Walk-Forward dans une table dédiée. Ces données sont consommées par le **live** et le **backtest** pour filtrer les symboles peu prédictibles ou directionnellement biaisés.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   run_training_batch()                       │
│                   (orchestrator.py)                          │
│                         │                                    │
│                         ▼                                    │
│              persist_batch_diagnostics()                     │
│              (batch_diagnostics.py)                          │
│                         │                                    │
│                         ▼                                    │
│    ┌─────────────────────────────────────────────┐           │
│    │  alpha_trade.model_batch_diagnostics         │           │
│    │  (1 ligne par symbole × rank_type)          │           │
│    └─────────────────────────────────────────────┘           │
│                         │                                    │
│                         ▼                                    │
│    ┌─────────────────────────────────────────────┐           │
│    │  get_batch_filters() → BatchFilters          │           │
│    │  → .prefer        (top N)                   │           │
│    │  → .exclude_long  (bottom + weak_long)      │           │
│    │  → .exclude_short (bottom + zero_short      │           │
│    │                    + weak_short)             │           │
│    └─────────────────────────────────────────────┘           │
│                         │                                    │
│                         ▼                                    │
│    ┌─────────────────────────────────────────────┐           │
│    │  Live / Backtest : croisement avec les      │           │
│    │  sélections du jour (screener)              │           │
│    └─────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Table `model_batch_diagnostics`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGINT PK | Auto-incrément |
| `batch_id` | VARCHAR(64) | Identifiant du batch |
| `batch_started_at` | DATETIME | Dénormalisé pour requêtes sans JOIN |
| `symbol` | VARCHAR(20) | Ticker |
| `f1_macro_wf` | DOUBLE | F1 macro Walk-Forward |
| `f1_long_wf` | DOUBLE | F1 classe long WF |
| `f1_short_wf` | DOUBLE | F1 classe short WF |
| `f1_flat_wf` | DOUBLE | F1 classe flat WF |
| `rank_type` | VARCHAR(20) | `top` / `bottom` / `zero_short` / `weak_long` / `weak_short` |
| `rank_position` | INT | 1..N pour top/bottom, NULL sinon |
| `threshold_used` | DOUBLE | Seuil pour weak_long / weak_short |
| `created_at` | DATETIME | Date de création |

### Index
- `idx_batch_diag_batch_rank` (batch_id, rank_type) — requêtes principales
- `idx_batch_diag_symbol` (symbol) — lookup par symbole
- `idx_batch_diag_started` (batch_started_at) — dernier batch

---

## 🏷️ Catégories `rank_type`

| Catégorie | Condition | Signification |
|-----------|-----------|---------------|
| `top` | Parmi les N meilleurs f1_macro_wf | **Privilégier** si présent dans les sélections du jour |
| `bottom` | Parmi les N pires f1_macro_wf | **Exclure** long et short |
| `zero_short` | f1_short_wf = 0 | Modèle incapable de shorter |
| `weak_long` | 0 < f1_long_wf < seuil (défaut 0.15) | Long inefficace |
| `weak_short` | 0 < f1_short_wf < seuil (défaut 0.15) | Short inefficace |

### Règles de filtrage

```python
EXCLUDE_LONG  = {'bottom', 'weak_long'}
EXCLUDE_SHORT = {'bottom', 'zero_short', 'weak_short'}
PREFER        = {'top'}
```

---

## ⚙️ Configuration (`config.yaml`)

```yaml
batch_diagnostics:
  top_n: 10                         # Nb symboles stockés dans le top
  bottom_n: 10                      # Nb symboles stockés dans le bottom
  weak_long_threshold: 0.15         # Seuil f1_long pour weak_long
  weak_short_threshold: 0.15        # Seuil f1_short pour weak_short
  prefer_top_n: 10                  # Nb de top effectivement boostés (≤ top_n)
  prefer_sizing_multiplier: 1.2     # Multiplicateur de sizing pour les prefer
```

- `top_n` / `bottom_n` : combien de symboles on persiste dans la table.
- `prefer_top_n` : parmi les `top_n` stockés, combien on booste réellement
  en live/backtest (permet de stocker plus qu'on ne booste, pour analyses).
- `prefer_sizing_multiplier` : facteur multiplicatif appliqué au sizing
  (target_shares / target_notional en live, proba_long/proba_short en backtest).

---

## 🔌 API

### Persistence (appelée automatiquement en fin de batch)

```python
from modelFactory.batch_diagnostics import persist_batch_diagnostics

# Appelé dans orchestrator.py à la fin de run_training_batch()
count = persist_batch_diagnostics(engine, batch_id)
# → rows insérées dans model_batch_diagnostics
```

### Lecture (consommé par le live/backtest)

```python
from modelFactory.batch_diagnostics import get_batch_filters, BatchFilters

# batch_id=None → dernier batch complété
# prefer_top_n lu depuis config.yaml (10) — déjà appliqué dans filters.prefer
filters: BatchFilters = get_batch_filters(engine, batch_id=None)

# filters.prefer        → frozenset[str]  # top N (déjà filtré par prefer_top_n)
# filters.exclude_long  → frozenset[str]  # bottom + weak_long
# filters.exclude_short → frozenset[str]  # bottom + zero_short + weak_short
# filters.batch_id      → str
# filters.batch_started_at → datetime | None
# filters.all_diagnostics → pd.DataFrame  # toutes les lignes du batch (debug)
```

Si `batch_id=None`, utilise automatiquement le **dernier batch** (par `batch_started_at DESC`).

### Filtrage d'un DataFrame de prédictions (backtest)

```python
from modelFactory.batch_diagnostics import filter_predictions

# Exclut les lignes où predicted_side = "long" et symbole ∈ exclude_long
#                         ou predicted_side = "short" et symbole ∈ exclude_short
preds_df = filter_predictions(preds_df, filters)

# Optionnel : booster la colonne sizing_mult pour les prefer
# preds_df = filter_predictions(preds_df, filters, boost_prefer_sizing=True)
```

---

## 🔄 Workflow ML-First

### Live (`execution_engine/executor.py`)

Intégré dans `execute_run()`, après le chargement des targets :

```
1. Chargement des targets (screener → ML → sizing → targets)
2. FILTRE BATCH (non-bloquant, try/except) :
   ├─ get_batch_filters(engine) → dernier batch
   ├─ Exclusion : si side ∈ {sell, short} ET symbole ∈ exclude_short → skip
   │              si side ∈ {buy, long}   ET symbole ∈ exclude_long  → skip
   ├─ Boost prefer : target_shares   *= prefer_sizing_multiplier
   │                 target_notional *= prefer_sizing_multiplier
   │                 pour les symboles dans prefer (top prefer_top_n)
   └─ Si plus aucune target après filtrage → ABORTED
3. RISK MANAGEMENT → Sizing, concentration, stops
4. EXECUTION → Submit orders Alpaca
```

Code réel (simplifié) :

```python
from modelFactory.batch_diagnostics import get_batch_filters

_bt_filters = get_batch_filters(engine)  # dernier batch, prefer_top_n lu du config

# ── Exclusion ──
for _t in targets:
    _sym = str(_t.symbol).strip().upper()
    _side = str(getattr(_t, "side", "buy") or "buy").strip().lower()
    if _side in ("sell", "short") and _sym in _bt_filters.exclude_short:
        continue  # exclu
    if _side in ("buy", "long") and _sym in _bt_filters.exclude_long:
        continue  # exclu
    _filtered_targets.append(_t)

# ── Boost sizing prefer ──
for _t in targets:
    if _t.symbol in _bt_filters.prefer:
        _t = replace(_t,
            target_shares=_t.target_shares * prefer_sizing_multiplier,
            target_notional=_t.target_notional * prefer_sizing_multiplier)
```

### Backtest (`backtesting/cli/_impl.py`)

Intégré dans `_run_backtest()`, après chargement de `preds_df` :

```
1. Chargement preds_df (ML predictions PIT-safe)
2. FILTRE BATCH (non-bloquant, try/except) :
   ├─ get_batch_filters(engine) → dernier batch
   ├─ Étape 1 — Exclusion : filter_predictions(preds_df, filters)
   │   Retire les lignes où predicted_side = "long"  ET symbole ∈ exclude_long
   │                 ou predicted_side = "short" ET symbole ∈ exclude_short
   └─ Étape 2 — Boost prefer : proba_long  *= prefer_sizing_multiplier (clip ≤ 1.0)
                                proba_short *= prefer_sizing_multiplier (clip ≤ 1.0)
                                → cascade vers selection_score → sizing
3. RISK (PIT)
4. EXECUTION (simulée)
```

Code réel (simplifié) :

```python
from modelFactory.batch_diagnostics import get_batch_filters, filter_predictions

_bt_filters = get_batch_filters(engine)

# Étape 1 : exclusion
preds_df = filter_predictions(preds_df, _bt_filters)

# Étape 2 : boost prefer (Option B — sizing boost, parité avec le live)
_prefer_mask = preds_df["symbol"].str.upper().isin(_bt_filters.prefer)
for _col in ("proba_long", "proba_short"):
    preds_df.loc[_prefer_mask, _col] = (
        preds_df.loc[_prefer_mask, _col] * prefer_sizing_multiplier
    ).clip(upper=1.0)
```

### Parité live ↔ backtest

Les deux pipelines utilisent la **même logique** (Option B = sizing boost) :

| Aspect | Live | Backtest |
|--------|------|----------|
| Exclusion long | `side ∈ {buy,long} ∧ sym ∈ exclude_long` | `predicted_side="long" ∧ sym ∈ exclude_long` |
| Exclusion short | `side ∈ {sell,short} ∧ sym ∈ exclude_short` | `predicted_side="short" ∧ sym ∈ exclude_short` |
| Boost prefer | `target_shares` × multiplier | `proba_long/proba_short` × multiplier (clip 1.0) |
| Multiplier | `prefer_sizing_multiplier` (1.2) | `prefer_sizing_multiplier` (1.2) |
| Prefer set | top N `prefer_top_n` (10) | top N `prefer_top_n` (10) |
| Non-bloquant | ✅ try/except | ✅ try/except |

---

## 📝 Exemple concret

Pour le batch `model-factory-20260723041048-1db3e0` (+VIX, 198 symboles) :

| Catégorie | Nb symboles | Exemples |
|-----------|:---:|------|
| `top` | 10 | ESTA (0.408), SANM (0.397), MOG.A (0.394), DRH (0.390), GTX (0.384) |
| `bottom` | 10 | ANET (0.190), PRG (0.195), HSBC (0.204), INDV (0.208), IIPR (0.213) |
| `zero_short` | 8 | BMO, CFG, INTC, JBHT, SSD, TREX, VOYA, WWD |
| `weak_long` | variable | Tous les symboles avec f1_long_wf < 0.15 |
| `weak_short` | variable | Tous les symboles avec 0 < f1_short_wf < 0.15 |

---

## ⚠️ Précautions

1. **Look-ahead bias** : Ne consommer le batch N qu'à partir de J+1 de `training_end_date`.
2. **Promotion explicite** : Utiliser `model_serving_batch` pour promouvoir un batch en production (ne pas prendre automatiquement le dernier).
3. **Dégradation** : Monitorer l'`avg(f1_macro_wf)` par batch. Si le dernier batch a une moyenne anormalement basse, ne pas l'utiliser.
4. **Univers changeant** : Un symbole exclu peut ne plus être tradable → ignorer silencieusement.

---

## 🧪 Test manuel

```powershell
# 1. Appliquer la migration
alembic upgrade head

# 2. Lancer un batch (la persistence est automatique)
python -m modelFactory --mode train --feature-set expert --enable-cross-sectional --comment test_diagnostics

# 3. Vérifier les données
python -c "
from database.connection import get_sqlalchemy_engine
from modelFactory.batch_diagnostics import get_batch_filters
engine = get_sqlalchemy_engine()
f = get_batch_filters(engine)
print(f'Batch: {f.batch_id}')
print(f'Prefer ({len(f.prefer)}): {sorted(f.prefer)[:10]}...')
print(f'Exclude long ({len(f.exclude_long)}): {sorted(f.exclude_long)[:10]}...')
print(f'Exclude short ({len(f.exclude_short)}): {sorted(f.exclude_short)[:10]}...')
"
```

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
  live_batch_id: ""                 # Batch à utiliser en live (vide = dernier batch)
  backtest_batch_id: ""             # Batch à utiliser en backtest (vide = dernier batch)
```

- `top_n` / `bottom_n` : combien de symboles on persiste dans la table.
- `prefer_top_n` : parmi les `top_n` stockés, combien on booste réellement
  en live/backtest (permet de stocker plus qu'on ne booste, pour analyses).
- `prefer_sizing_multiplier` : facteur multiplicatif appliqué au sizing
  (live → `approved_shares`/`target_notional`, backtest → `proba_long`/`proba_short`).
- `live_batch_id` : batch de diagnostics à utiliser pour le live (étape 11 Risk).
  Laisser vide pour utiliser automatiquement le dernier batch complété.
  Renseigner un `batch_id` explicite (ex: le batch promu via `model_serving_batch`)
  pour figer les filtres et éviter de changer de batch entre deux runs.
- `backtest_batch_id` : batch de diagnostics à utiliser pour le backtest.
  Laisser vide pour utiliser le dernier batch (⚠️ attention au look-ahead :
  si le dernier batch est postérieur à la période backtestée, les diagnostics
  utilisent de l'information future). Pour un backtest PIT-safe, renseigner
  un `batch_id` dont la `training_end_date` est antérieure à la date simulée.

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

### Live — Risk Management (`risk_management/cli.py`)

Intégré dans l'étape 11 (Risk) en deux temps :

```
1. MLRankedCandidate → boost_candidate_scores()  ← BOOST SCORE AVANT sizing
   └─ p_side *= prefer_sizing_multiplier (clip 1.0) pour les prefer
      → le PortfolioBuilder intègre naturellement ce boost dans le sizing,
        les contraintes et les target_weight → cohérence parfaite
2. PortfolioBuilder.build_from_ml_candidates() → entries
3. apply_batch_diagnostics_to_entries()  ← EXCLUSION uniquement
   ├─ Exclusion long/short
   └─ Plus de boost ici (déjà fait en étape 1)
4. persist_portfolio_targets() → DB
```

Code réel (simplifié) :

```python
from risk_management.batch_diagnostics import (
    boost_candidate_scores,
    apply_batch_diagnostics_to_entries,
)

# AVANT le builder : boost score prefer
boost_candidate_scores(candidates, repo.engine)

# Builder normal (intègre le score boosté)
entries = builder.build_from_ml_candidates(candidates, prices, ...)

# APRÈS le builder : exclusion uniquement
entries, excluded, batch_id = apply_batch_diagnostics_to_entries(entries, repo.engine)
```

### Backtest (`backtesting/cli/_impl.py`)

Intégré dans `_run_backtest()`, après chargement de `preds_df` :

```
1. Chargement preds_df (ML predictions PIT-safe)
2. FILTRE BATCH (non-bloquant, try/except) :
   ├─ get_batch_filters(engine) → batch configuré
   ├─ Étape 1 — Exclusion : filter_predictions(preds_df, filters)
   └─ Étape 2 — Boost prefer side-aware (Option C) :
        proba_long *= prefer_sizing_multiplier UNIQUEMENT si predicted_side="long"
        proba_short *= prefer_sizing_multiplier UNIQUEMENT si predicted_side="short"
        (clip ≤ 1.0, flat = pas de boost)
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

# Étape 2 : boost prefer side-aware (Option C)
_prefer_set = _bt_filters.prefer
# Boost proba_long uniquement pour les prefer prédits long
_mask_long = preds_df["symbol"].str.upper().isin(_prefer_set) & (preds_df["predicted_side"] == "long")
preds_df.loc[_mask_long, "proba_long"] = (preds_df.loc[_mask_long, "proba_long"] * multiplier).clip(upper=1.0)
# Boost proba_short uniquement pour les prefer prédits short
_mask_short = preds_df["symbol"].str.upper().isin(_prefer_set) & (preds_df["predicted_side"] == "short")
preds_df.loc[_mask_short, "proba_short"] = (preds_df.loc[_mask_short, "proba_short"] * multiplier).clip(upper=1.0)
```

### Parité live ↔ backtest

Les deux pipelines utilisent désormais la **même logique** (Option C = boost de score en amont du sizing) :

| Aspect | Live (Risk étape 11) | Backtest |
|--------|----------------------|----------|
| Exclusion long | `side ∈ {buy,long} ∧ sym ∈ exclude_long` | `predicted_side="long" ∧ sym ∈ exclude_long` |
| Exclusion short | `side ∈ {sell,short} ∧ sym ∈ exclude_short` | `predicted_side="short" ∧ sym ∈ exclude_short` |
| Boost prefer | `p_side` × multiplier (AVANT sizing) | `proba_long` × multiplier si side=long, `proba_short` × multiplier si side=short (AVANT sizing) |
| Side-awareness | ✅ side respecté | ✅ side respecté (long→proba_long, short→proba_short) |
| Multiplier | `prefer_sizing_multiplier` (1.2) | `prefer_sizing_multiplier` (1.2) |
| Prefer set | top N `prefer_top_n` (10) | top N `prefer_top_n` (10) |
| Clip | p_side ≤ 1.0 | proba ≤ 1.0 |
| Non-bloquant | ✅ try/except | ✅ try/except |
| Module | `risk_management/batch_diagnostics.py` | `backtesting/cli/_impl.py` (inline) |

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

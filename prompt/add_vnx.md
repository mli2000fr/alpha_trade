# Plan d'Action Détaillé — Intégration VXN, VIX3M, MOVE, RVX dans Alpha Trade

**Date :** 2026-06-25
**Statut :** ✅ **IMPLÉMENTÉ** — Toutes les étapes 1-8 sont terminées
**Module principal :** `service/market/` (macro providers + regime manager)
**Modules impactés :** `modelFactory/`, `ihm/`, `database/`

> **Résumé d'exécution :** 30 tests unitaires, 16 fichiers modifiés, 3 fichiers créés.
> Détail dans `/memories/session/progress_final.md`.

---

## 🎯 Objectifs

1. **Ajouter 4 nouveaux indicateurs macro** : VXN (Nasdaq vol), VIX3M (term structure), MOVE (bond vol), RVX (Small Caps vol)
2. **Ajouter le ratio VIX/VIX3M** comme signal de contango/backwardation
3. **Alimenter `stock_macro_indicators_daily`** avec ces nouvelles colonnes
4. **Permettre à l'opérateur IHM de cocher/décocher** ces indicateurs pour l'entraînement ML
5. **Injecter les features macro dans le pipeline ML** (`modelFactory/dataset.py`)

---

## 🏗️ Architecture existante — `stock_macro_indicators_daily`, source unique Live + Backtest

La table `stock_macro_indicators_daily` est **LA source unique de vérité** pour tous les indicateurs macro. Elle alimente à la fois le pipeline LIVE et le moteur de BACKTEST, garantissant **zéro divergence** entre les deux modes.

```
┌──────────────────────────────────────────────────────────────────────┐
│                   stock_macro_indicators_daily                        │
│  PK: trade_date | vix | vix9d | ten_y | mode | risk_multiplier...   │
│  (bientôt: +vxn | +vix3m | +move | +rvx)                            │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
         🔴 LIVE                        🔵 BACKTEST
              │                             │
    build_default_macro_              build_default_macro_
    provider(yaml_cfg)                provider(yaml_cfg,
              │                       execution_context="backtest")
              ▼                             │
    TableFirstMacroProvider                  ▼
              │                    TableFirstMacroProvider
    ┌─────────┴─────────┐                    │
    │ DB hit ?           │          ┌─────────┴─────────┐
    │  oui → retour      │          │ DB hit ?           │
    │  non → fallback    │          │  oui → retour      │
    └─────────┬──────────┘          │  non → fallback    │
              │                     └─────────┬──────────┘
              ▼                               ▼
    fetch_eod() EODHD                fetch_eod() EODHD
    (1 call / symbole)              (1 call / symbole)
              │                               │
              ▼                               ▼
    persist_macro_indicator         persist_macro_indicator
    _daily() → écrit DB            _daily() → écrit DB
```

### Flux détaillé par mode

| Étape | 🔴 LIVE | 🔵 BACKTEST |
|-------|---------|-------------|
| **Construction provider** | `build_default_macro_provider(yaml_cfg)` → `TableFirstMacroProvider` avec `strict_before=False` | `build_default_macro_provider(yaml_cfg, execution_context="backtest")` → `TableFirstMacroProvider` avec `strict_before=True` (J-1 strict) |
| **Lecture VIX/VXN/...** | `get_vix_close(trade_date)` → lit `stock_macro_indicators_daily` WHERE `trade_date <= :date` → si absent, fallback EODHD → écrit DB | `get_vix_close(trade_date)` → lit `stock_macro_indicators_daily` WHERE `trade_date < :date` (strict) → si absent, fallback EODHD → écrit DB |
| **Régime** | `build_snapshot()` → `execution_context="live"` → `MarketRegimeSnapshot` → consommé par `risk_management/portfolio_builder.py` | `build_snapshot()` → `execution_context="backtest"` → `MarketRegimeSnapshot` → consommé par `backtesting/risk_bridge.py` |
| **Appels EODHD** | 1er jour : 1 call/symbole. Jours suivants : 0 call (cache DB) | Backfill initial : ~1250 calls/symbole. Re-runs : 0 call (tout en DB) |
| **Fichiers clés** | `service/market/regime_manager.py`, `risk_management/portfolio_builder.py`, `risk_management/cli.py` | `backtesting/cli/_impl.py:_run_backtest()`, `backtesting/risk_bridge.py`, `backtesting/weights_calibration.py` |

### Pourquoi c'est important pour ce plan

1. **Ajouter VXN/VIX3M/MOVE/RVX dans `stock_macro_indicators_daily`** = les rendre disponibles **instantanément** en live ET en backtest, sans duplication de code
2. **Backfill une fois** = toutes les dates historiques ont leurs valeurs → le backtest les lit directement, 0 appel EODHD
3. **PIT-safe par design** : le `strict_before=True` en backtest garantit que la valeur du VIX du jour J n'est connue qu'à J-1 (pas de look-ahead bias)
4. **Le `TableFirstMacroProvider`** est le point unique où ajouter les nouvelles colonnes — une fois fait, tous les consommateurs (live, backtest, IHM) en bénéficient

---

## 📋 Étape 1 — Protocol `MacroDataProvider` + tous les providers

### 1.1 `service/market/macro_signals.py`

Ajouter 4 méthodes au `Protocol` `MacroDataProvider` :

```python
class MacroDataProvider(Protocol):
    # ... existant ...
    def get_vxn_close(self, trade_date: date) -> float | None: ...
    def get_vix3m_close(self, trade_date: date) -> float | None: ...
    def get_move_close(self, trade_date: date) -> float | None: ...
    def get_rvx_close(self, trade_date: date) -> float | None: ...
```

Ajouter une fonction `evaluate_vxn()` (miroir de `evaluate_vix()`) :

```python
def evaluate_vxn(
    provider: MacroDataProvider | None,
    trade_date: date,
    *,
    high_threshold: float,
) -> tuple[float | None, bool, dict[str, str]]:
    """Retourne (vxn_value, is_high, data_quality)."""
```

Ajouter une fonction `evaluate_vix_term_structure()` pour le ratio contango/backwardation :

```python
@dataclass(frozen=True, slots=True)
class VixTermStructure:
    vix_value: float | None = None
    vix3m_value: float | None = None
    ratio: float | None = None       # VIX / VIX3M
    backwardation: bool = False       # ratio > 1
    data_quality: dict[str, str] = field(default_factory=dict)

def evaluate_vix_term_structure(
    provider: MacroDataProvider | None,
    trade_date: date,
    *,
    backwardation_threshold: float = 1.0,
) -> VixTermStructure: ...
```

### 1.2 `service/market/macro_providers.py`

#### a) `_DEFAULT_EODHD_SYMBOLS` — ajouter les 4 clés

```python
_DEFAULT_EODHD_SYMBOLS = {
    "vix": "VIX.INDX",
    "vix_short": "VIX9D.INDX",
    "vxn": "VXN.INDX",         # ← nouveau
    "vix3m": "VIX3M.INDX",     # ← nouveau
    "move": "MOVE.INDX",       # ← nouveau (à vérifier côté EODHD)
    "rvx": "RVX.INDX",         # ← nouveau
    "us10y": "US10Y.INDX",
}
```

#### b) `_signal_key_for_method()` — étendre

```python
def _signal_key_for_method(method: str) -> str | None:
    if method == "get_vix_close":        return "vix"
    if method == "get_vix_short_term_close": return "vix_short"
    if method == "get_vxn_close":        return "vxn"
    if method == "get_vix3m_close":      return "vix3m"
    if method == "get_move_close":       return "move"
    if method == "get_rvx_close":        return "rvx"
    if method == "get_us10y_history":    return "yield_10y"
    return None
```

#### c) `EodhdMacroProvider` — ajouter les 4 méthodes getter

Ajouter à la classe (même pattern que `get_vix_close`):

```python
def get_vxn_close(self, trade_date: date) -> float | None:
    bars = self._fetch("vxn", trade_date, _CLOSE_LOOKBACK_DAYS)
    value = _last_close(bars, trade_date)
    if value is not None:
        self._last_source_by_signal["vxn"] = self.source_name
    else:
        self._last_source_by_signal.pop("vxn", None)
    return value

def get_vix3m_close(self, trade_date: date) -> float | None:
    bars = self._fetch("vix3m", trade_date, _CLOSE_LOOKBACK_DAYS)
    # ... idem avec clé "vix3m"

def get_move_close(self, trade_date: date) -> float | None:
    bars = self._fetch("move", trade_date, _CLOSE_LOOKBACK_DAYS)
    # ... idem avec clé "move"

def get_rvx_close(self, trade_date: date) -> float | None:
    bars = self._fetch("rvx", trade_date, _CLOSE_LOOKBACK_DAYS)
    # ... idem avec clé "rvx"
```

#### d) `StooqMacroProvider` — retourner `None` pour les 4

Stooq ne couvre probablement pas ces indices. Toutes les méthodes retournent `None` + pop du `_last_source_by_signal`.

#### e) `CompositeMacroProvider` — ajouter le routage

```python
def get_vxn_close(self, trade_date: date) -> float | None:
    return self._first_non_none("get_vxn_close", trade_date)
def get_vix3m_close(self, trade_date: date) -> float | None:
    return self._first_non_none("get_vix3m_close", trade_date)
def get_move_close(self, trade_date: date) -> float | None:
    return self._first_non_none("get_move_close", trade_date)
def get_rvx_close(self, trade_date: date) -> float | None:
    return self._first_non_none("get_rvx_close", trade_date)
```

#### f) `TableFirstMacroProvider` — ajouter cache DB + fallback

Pour chaque nouvel indicateur, même pattern que `get_vix_close` :

1. Lecture `_load_cached_row()` → colonne `vxn`/`vix3m`/`move`/`rvx`
2. Si absent → fallback provider → `_persist_fallback_value()`

#### g) `_build_network_macro_provider()` — lire les symboles depuis `config.yaml`

Ajouter la lecture de :
```python
vxn_sym = (cfg.get("vxn") or {}).get("symbol")
vix3m_sym = (cfg.get("vix3m") or {}).get("symbol")
move_sym = (cfg.get("move") or {}).get("symbol")
rvx_sym = (cfg.get("rvx") or {}).get("symbol")
```

Et les mapper dans `eodhd_overrides` (même logique que `vix_sym`).

---

## 📋 Étape 2 — Base de données

### 2.1 Migration Alembic

Créer un fichier de migration dans `alembic/versions/` :

```python
"""add vxn vix3m move rvx to stock_macro_indicators_daily

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    for col in ["vxn", "vix3m", "move", "rvx"]:
        op.add_column("stock_macro_indicators_daily",
                       sa.Column(col, sa.Float(), nullable=True))
        op.create_index(f"idx_stock_macro_indicators_daily_{col}",
                        "stock_macro_indicators_daily", [col])

def downgrade():
    for col in ["vxn", "vix3m", "move", "rvx"]:
        op.drop_index(f"idx_stock_macro_indicators_daily_{col}",
                       table_name="stock_macro_indicators_daily")
        op.drop_column("stock_macro_indicators_daily", col)
```

### 2.2 `database/macro_indicators.py`

Mettre à jour `_ALLOWED_MACRO_COLUMNS` :

```python
_ALLOWED_MACRO_COLUMNS = {"vix", "vix9d", "ten_y", "vxn", "vix3m", "move", "rvx"}
```

Mettre à jour `get_macro_indicators_daily_table()` pour ajouter les 4 colonnes au schéma SQLAlchemy `Table`.

### 2.3 Mettre à jour `persist_macro_indicator_daily()`

S'assurer que la fonction accepte `value_key` = `"vxn"`, `"vix3m"`, `"move"`, `"rvx"` et les insère dans la colonne correspondante.

---

## 📋 Étape 3 — Configuration `config.yaml`

### 3.1 `service/market/config.py` — ajouter `VxnConfig`

```python
@dataclass(frozen=True, slots=True)
class VxnConfig:
    enabled: bool = False
    symbol: str = "VXN"
    high_threshold: float = 23.0  # seuil plus bas que VIX (Nasdaq plus volatile)

@dataclass(frozen=True, slots=True)
class Vix3mConfig:
    enabled: bool = False
    symbol: str = "VIX3M"
    backwardation_threshold: float = 1.0

@dataclass(frozen=True, slots=True)
class MoveConfig:
    enabled: bool = False
    symbol: str = "MOVE"
    high_threshold: float = 120.0

@dataclass(frozen=True, slots=True)
class RvxConfig:
    enabled: bool = False
    symbol: str = "RVX"
    high_threshold: float = 30.0
```

Mettre à jour `MarketRegimesConfig` pour inclure ces 4 configs.

### 3.2 `config.yaml` — ajouter les blocs

```yaml
market_regimes:
  # ... existant ...

  vxn:
    enabled: true
    symbol: "VXN.INDX"
    high_threshold: 23.0

  vix3m:
    enabled: true
    symbol: "VIX3M.INDX"
    backwardation_threshold: 1.0

  move:
    enabled: true
    symbol: "MOVE.INDX"
    high_threshold: 120.0

  rvx:
    enabled: true
    symbol: "RVX.INDX"
    high_threshold: 30.0
```

---

## 📋 Étape 4 — Logique Régime (`regime_manager.py`)

### 4.1 `build_snapshot()` — ajouter évaluation VXN + term structure

Dans la section "2. Macro VIX" existante, ajouter après le bloc VIX :

```python
# 2b. Macro VXN (Nasdaq volatility)
if config.vxn.enabled:
    vxn_value, vxn_high, dq = evaluate_vxn(
        macro_provider, trade_date,
        high_threshold=config.vxn.high_threshold,
    )
    macro_metrics["vxn"] = vxn_value
    data_quality.update(dq)
    if vxn_high:
        mode = _escalate(mode, "capital_preservation")
        reasons.append(f"vxn_high:{vxn_value:.1f}")
    # trace VXN...

# 2c. Term structure VIX/VIX3M
if config.vix3m.enabled:
    ts = evaluate_vix_term_structure(
        macro_provider, trade_date,
        backwardation_threshold=config.vix3m.backwardation_threshold,
    )
    macro_metrics["vix3m"] = ts.vix3m_value
    macro_metrics["vix_term_structure_ratio"] = ts.ratio
    macro_metrics["vix_backwardation"] = ts.backwardation
    data_quality.update(ts.data_quality)
    if ts.backwardation:
        mode = _escalate(mode, "capital_preservation")
        reasons.append("vix_backwardation")

# 2d. MOVE (bond volatility)
if config.move.enabled:
    move_value = ...
    macro_metrics["move"] = move_value
    if move_value and move_value >= config.move.high_threshold:
        mode = _escalate(mode, "capital_preservation")
        reasons.append(f"move_high:{move_value:.1f}")

# 2e. RVX (Small Caps volatility)
if config.rvx.enabled:
    rvx_value = ...
    macro_metrics["rvx"] = rvx_value
    if rvx_value and rvx_value >= config.rvx.high_threshold:
        mode = _escalate(mode, "capital_preservation")
        reasons.append(f"rvx_high:{rvx_value:.1f}")
```

### 4.2 `MarketRegimeSnapshot.macro` — inclure les nouvelles valeurs

Le dictionnaire `macro_metrics` alimente déjà `snapshot.macro`. Ajouter les clés :

```python
macro_metrics = {
    "vix": vix_value,
    "vix_short": vix_short_value,
    "vix_curve_inverted": curve_inverted,
    "vxn": vxn_value,                    # ← nouveau
    "vix3m": ts.vix3m_value,             # ← nouveau
    "vix_term_structure_ratio": ts.ratio, # ← nouveau
    "vix_backwardation": ts.backwardation,# ← nouveau
    "move": move_value,                   # ← nouveau
    "rvx": rvx_value,                     # ← nouveau
    "yield_10y": ...,
    "yield_10y_5d_pct": ...,
}
```

---

## 📋 Étape 5 — Feature Engineering ML (`modelFactory/`)

### 5.1 `modelFactory/config.py` — `DataConfig`

Ajouter 4 nouveaux booléens :

```python
@dataclass(frozen=True, slots=True)
class DataConfig:
    # ... existant ...
    include_macro_vix_features: bool = False     # VIX + VIX9D
    include_macro_vxn_features: bool = False     # VXN
    include_macro_vix3m_features: bool = False   # VIX3M + ratio
    include_macro_move_features: bool = False    # MOVE
```

### 5.2 `modelFactory/cli.py` — arguments CLI

Ajouter les flags `--include-macro-vix`, `--include-macro-vxn`, `--include-macro-vix3m`, `--include-macro-move` (même pattern que `--include-sentiment`).

### 5.3 `modelFactory/features.py` — nouvelles features

Ajouter une fonction `compute_macro_features()` :

```python
MACRO_FEATURE_COLUMNS: list[str] = [
    "vix_close",
    "vix_momentum_5j",
    "vxn_close",
    "vxn_spread_vix",
    "vix3m_close",
    "vix_term_structure_ratio",
    "vix_backwardation",
    "move_close",
]

def compute_macro_features(
    df: pd.DataFrame,
    macro_df: pd.DataFrame,  # issu de stock_macro_indicators_daily
    *,
    include_vix: bool = False,
    include_vxn: bool = False,
    include_vix3m: bool = False,
    include_move: bool = False,
) -> pd.DataFrame: ...
```

### 5.4 `modelFactory/dataset.py` — injection dans les séquences

Dans la construction du `SequenceDataset`, charger `stock_macro_indicators_daily` sur la plage de dates concernée, puis merger sur `date`. Les features macro sont ajoutées **après** les features OHLCV, préservant l'ordre canonique.

```python
if data_config.include_macro_vix_features:
    macro_df = load_macro_indicators(...)
    df = compute_macro_features(df, macro_df, include_vix=True, ...)
```

---

## 📋 Étape 6 — IHM Streamlit

### 6.1 Page Pipeline — bloc "Paramétrage ML"

Dans `ihm/pages/pipeline.py`, section ML train, ajouter 4 checkboxes sous la forme :

```
📊 Features Macro pour l'entraînement ML
┌──────────────────────────────────────────────────────┐
│ ☑ VIX  (volatilité S&P 500, déjà actif)              │
│ ☐ VXN  (volatilité NASDAQ, Small Caps)               │
│ ☐ VIX3M (term structure, contango/backwardation)     │
│ ☐ MOVE (volatilité obligataire, taux)                │
└──────────────────────────────────────────────────────┘
```

**Implémentation technique :**

```python
# Dans _render_ml_train_scope_block() ou une nouvelle fonction _render_ml_macro_features_block()

st.markdown("#### 📊 Features Macro contextuelles")
st.caption("Ajoutez des indicateurs de volatilité implicite aux features du LSTM. "
           "Chaque indicateur coûte ~1 appel EODHD pour le backfill initial, "
           "puis est servi depuis le cache DB `stock_macro_indicators_daily`.")

col1, col2 = st.columns(2)
with col1:
    include_macro_vix = st.checkbox(
        "VIX / VIX9D (volatilité S&P 500)",
        value=bool(getattr(options, "ml_include_macro_vix", True)),
        key="pipeline_ml_macro_vix",
        help="Volatilité implicite 30j du S&P 500 + courbe (VIX9D). Déjà backfillé.",
    )
    include_macro_vxn = st.checkbox(
        "VXN (volatilité NASDAQ-100)",
        value=bool(getattr(options, "ml_include_macro_vxn", False)),
        key="pipeline_ml_macro_vxn",
        help="Volatilité implicite du NASDAQ. Utile pour les valeurs Tech.",
    )
with col2:
    include_macro_vix3m = st.checkbox(
        "VIX3M + ratio (term structure)",
        value=bool(getattr(options, "ml_include_macro_vix3m", False)),
        key="pipeline_ml_macro_vix3m",
        help="Ratio VIX/VIX3M : détecte la backwardation (panique court terme).",
    )
    include_macro_move = st.checkbox(
        "MOVE (volatilité obligataire)",
        value=bool(getattr(options, "ml_include_macro_move", False)),
        key="pipeline_ml_macro_move",
        help="Indice ICE BofA MOVE : volatilité des bons du Trésor US.",
    )
```

### 6.2 Page "Régime Marché" — jauges visuelles

Dans `ihm/pages/market_regime.py`, ajouter une section "Indicateurs Macro" avec des métriques Streamlit :

```python
st.markdown("### 📈 Indicateurs de Volatilité")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("VIX", f"{macro.get('vix', '—')}", delta=None)
with col2:
    st.metric("VXN", f"{macro.get('vxn', '—')}", delta=None)
with col3:
    ratio = macro.get('vix_term_structure_ratio')
    ratio_str = f"{ratio:.2f}" if ratio else "—"
    st.metric("VIX/VIX3M", ratio_str,
              delta="⚠️ Backwardation" if macro.get('vix_backwardation') else None)
with col4:
    st.metric("MOVE", f"{macro.get('move', '—')}", delta=None)
```

### 6.3 `PipelineLaunchOptions` — nouveaux champs

Dans `ihm/pages/_shared.py` (ou là où est défini `PipelineLaunchOptions`), ajouter les 4 booléens :

```python
@dataclass
class PipelineLaunchOptions:
    # ... existant ...
    ml_include_macro_vix: bool = True
    ml_include_macro_vxn: bool = False
    ml_include_macro_vix3m: bool = False
    ml_include_macro_move: bool = False
```

### 6.4 `ihm/services/pipeline_runner.py` — transmission CLI

Dans `build_pipeline_command()`, ajouter les flags :

```python
if options.ml_include_macro_vix:
    cmd.append("--include-macro-vix")
if options.ml_include_macro_vxn:
    cmd.append("--include-macro-vxn")
if options.ml_include_macro_vix3m:
    cmd.append("--include-macro-vix3m")
if options.ml_include_macro_move:
    cmd.append("--include-macro-move")
```

---

## 📋 Étape 7 — Backfill historique

### 7.1 Commande de backfill

Utiliser la fonction existante `populate_macro_indicators_table()` :

```bash
python -c "
from service.market.macro_providers import populate_macro_indicators_table
from datetime import date
result = populate_macro_indicators_table(
    start_date=date(2020, 1, 1),
    end_date=date(2026, 6, 24),
)
print(f'{result[\"persisted_rows\"]} lignes persistées, {result[\"missing_rows\"]} manquantes')
"
```

Coût estimé : ~1250 séances NYSE × 4 nouveaux symboles = **~5000 appels EODHD** pour le backfill complet. À faire par tranches ou sur plusieurs jours.

### 7.2 Alternative : IHM

Ajouter un bouton dans `ihm/pages/market_regime.py` section "Réalimenter `stock_macro_indicators_daily`" avec sélecteur de plage de dates.

---

## 📋 Étape 8 — Tests & Validation

### 8.1 Tests unitaires

| Test | Fichier | Vérification |
|------|---------|-------------|
| `test_eodhd_symbols_vxn` | `tests/test_macro_providers.py` | `to_eodhd("VXN.INDX")` → `"VXN.INDX"` |
| `test_get_vxn_close` | `tests/test_macro_providers.py` | Mock EODHD → valeur cohérente |
| `test_evaluate_vxn` | `tests/test_macro_signals.py` | Seuil VXN ≥ 23 → `vxn_high=True` |
| `test_term_structure` | `tests/test_macro_signals.py` | VIX=28, VIX3M=25 → ratio=1.12 → backwardation |
| `test_regime_vxn_high` | `tests/test_regime_manager.py` | VXN=25 → mode ≥ capital_preservation |
| `test_macro_features_columns` | `tests/test_model_factory_features.py` | Colonnes ajoutées sans casser l'existant |

### 8.2 Régression PIT

Après backfill, lancer un backtest complet et vérifier :
- Les décisions de régime aux dates de crise (mars 2020, juin 2022) restent cohérentes
- Aucun look-ahead bias (le VIX3M du jour J ne doit pas être connu le jour J-1 en mode strict)

### 8.3 Ablation ML

Entraîner 5 modèles et comparer les métriques :

| Modèle | Features | F1 macro attendu |
|--------|----------|-----------------|
| Baseline | OHLCV seules | référence |
| +VIX | OHLCV + VIX/VIX9D | ≥ baseline |
| +VXN | OHLCV + VIX + VXN | ≥ +VIX |
| +Term | OHLCV + VIX + VXN + VIX3M | ≥ +VXN |
| +MOVE | OHLCV + VIX + VXN + VIX3M + MOVE | ≥ +Term |

---

## ✅ Statut d'implémentation (2026-06-25)

| Étape | Statut | Fichiers |
|-------|--------|----------|
| 1. Protocol + Providers | ✅ Terminé | `macro_signals.py`, `macro_providers.py` |
| 2. Base de données | ✅ Terminé | `0043_*.py`, `macro_indicators.py`, SQL |
| 3. Configuration | ✅ Terminé | `config.py`, `config.yaml` |
| 4. Logique Régime | ✅ Terminé | `regime_manager.py` |
| 5. Features ML | ✅ Terminé | `modelFactory/config.py`, `cli.py`, `features.py`, `dataset.py` |
| 6. IHM Streamlit | ✅ Terminé | `_execution_center/__init__.py`, `market_regime.py`, `pipeline_runner.py`, `pipeline_ml_defaults.py` |
| 7. Backfill | ✅ Terminé | `macro_providers.py` (row_payload), `market_regime.py` (IHM) |
| 8. Tests | ✅ Terminé | `test_macro_signals.py` (nouveau, 10 tests), `test_macro_providers.py` (+10 tests), `test_regime_manager.py` (nouveau, 10 tests) |

**Total : 30 tests, 16 fichiers modifiés, 3 créés.**

---

| Fichier | Modification | Effort |
|---------|-------------|--------|
| `service/market/macro_signals.py` | Protocol +4 méthodes, `evaluate_vxn()`, `evaluate_vix_term_structure()` | 2h |
| `service/market/macro_providers.py` | `_DEFAULT_EODHD_SYMBOLS` +4, `EodhdMacroProvider` +4 getters, `StooqMacroProvider` +4 (None), `CompositeMacroProvider` +4, `TableFirstMacroProvider` +4, `_build_network_macro_provider()` +4 symboles | 3h |
| `service/market/config.py` | `VxnConfig`, `Vix3mConfig`, `MoveConfig`, `RvxConfig` + `MarketRegimesConfig` | 1h |
| `config.yaml` | Blocs `vxn:`, `vix3m:`, `move:`, `rvx:` | 15min |
| `service/market/regime_manager.py` | `build_snapshot()` sections 2b-2e + `macro_metrics` | 2h |
| `database/macro_indicators.py` | `_ALLOWED_MACRO_COLUMNS` +4, schéma `Table` +4 colonnes | 30min |
| `alembic/versions/xxx_add_vxn_vix3m_move_rvx.py` | Migration | 30min |
| `modelFactory/config.py` | `DataConfig` +4 booléens | 15min |
| `modelFactory/cli.py` | +4 flags `--include-macro-*` | 30min |
| `modelFactory/features.py` | `compute_macro_features()` + `MACRO_FEATURE_COLUMNS` | 2h |
| `modelFactory/dataset.py` | Chargement `stock_macro_indicators_daily` + merge | 2h |
| `ihm/pages/pipeline.py` | Bloc checkboxes "Features Macro" | 1h30 |
| `ihm/pages/market_regime.py` | Section jauges VIX/VXN/VIX3M/MOVE | 1h |
| `ihm/pages/_shared.py` | `PipelineLaunchOptions` +4 champs | 15min |
| `ihm/services/pipeline_runner.py` | `build_pipeline_command()` +4 flags | 15min |
| `ihm/services/pipeline_ml_defaults.py` | +4 constantes default | 10min |

**Total estimé : ~17h**

---

## ⚠️ Risques & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| `MOVE.INDX` indisponible sur EODHD | Bloquant | Vérifier avant ; fallback → `TYVIX` (CBOE 10Y UST Vol) ou TLT implied vol |
| Quota EODHD saturé pendant le backfill | Ralentissement | Backfill par tranches de 250 jours ; cache DB first |
| Surapprentissage LSTM avec trop de features macro | Dégradation F1 | Ablation obligatoire avant mise en prod ; les checkboxes IHM permettent de désactiver |
| Le RVX n'apporte pas de valeur ajoutée vs VIX | Temps perdu | Le RVX n'est pas inclus dans les features ML par défaut ; activable via checkbox si l'univers Small Caps le justifie |

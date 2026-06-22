# Contrainte de Liquidité Dynamique — Position Size vs ADV

> **Date** : 2026-06-22
> **Statut** : ✅ P1, P3, P4 implémentés (2026-06-22). P2 non retenu (redondant avec P1).
> **Verdict** : Le filtre ADV est présent ($30M minimum), et désormais une **contrainte explicite** position/ADV existe dans le `ConstraintChecker`.

---

## 1. La question posée

> *L'AlphaScanner filtre par capitalisation, mais il manque un filtre basé sur le Volume Moyen Quotidien en Dollars (ADV). Si l'algorithme génère un signal fort sur une action très peu liquide, la taille de position calculée par le critère de Kelly pourrait être trop grosse, rendant impossible la sortie de position en direct sans faire s'effondrer le cours.*

---

## 2. Ce qui existe — le filtre ADV

### 2.1 ✅ Filtre d'éligibilité : `min_avg_dollar_volume_20d = $30M`

**Fichier** : `core/filter_profiles.py` → `STRICT_SWING_CASH_FILTERS`

```python
STRICT_SWING_CASH_FILTERS = StrictFilterProfile(
    min_avg_dollar_volume_20d=30_000_000.0,  # ← $30M minimum
    ...
)
```

Mappé vers `liquidity_threshold` dans `AlphaScannerConfig` et utilisé à deux niveaux :

1. **SQL pre-selection** (`selector/db_io.py` L755) :
   ```python
   avg_dollar_volume_value <= float(config.liquidity_threshold)
   # → rejeté avant même le calcul des facteurs
   ```

2. **Post-filter** (`core/filter_profiles.py` L178) :
   ```python
   frame[adv_col] >= self.min_avg_dollar_volume_20d
   ```

### 2.2 ✅ Filtre market cap : `min_market_cap = $2B`

Complément au filtre ADV, mais ne garantit pas la liquidité (une grosse capitalisation peut avoir un faible volume).

### 2.3 ✅ ADV utilisé pour le slippage volume-aware

**Fichier** : `backtesting/simulator.py` → `_try_open_entries()` et `_try_close_positions()`

```python
adv_usd = self._get_adv_usd(adv_usd_df, trade_day, symbol)
extra_slippage_pct = micro.slippage.compute_bps(size_usd, adv_usd) / 10_000.0
```

L'ADV est utilisé pour **estimer le coût** de la transaction (via le modèle sqrt Almgren-Chriss), mais pas pour **limiter** la taille.

---

## 3. Ce qui MANQUE — pas de contrainte position ≤ X% ADV

### 3.1 ❌ Aucune contrainte dans le PositionSizer

**Fichier** : `risk_management/position_sizer.py` → `PositionSizer.compute()`

Le sizing ATR ne connaît pas l'ADV :
```python
risk_budget = equity * risk_per_trade_pct * risk_multiplier
risk_per_share = atr_20 * atr_stop_multiple
raw_shares = risk_budget / risk_per_share  # ← aucune notion de volume
```

### 3.2 ❌ Aucune contrainte dans le KellySizer

**Fichier** : `risk_management/kelly.py` → `KellySizer.compute()`

```python
kelly_notional = equity * fractional_kelly
kelly_shares = floor(kelly_notional / price)
# ← aucune vérification : kelly_shares * price < 5% * ADV ?
```

### 3.3 ❌ Aucune contrainte dans le ConstraintChecker

**Fichier** : `risk_management/constraints.py` → `ConstraintChecker.check()`

Contraintes existantes :
| Contrainte | Présente |
|---|---|
| `max_position_weight` (10% equity) | ✅ |
| `max_gross_exposure` (100% equity) | ✅ |
| `max_sector_weight` (30% equity) | ✅ |
| `max_tickers_per_sector` | ✅ |
| `min_position_notional` | ✅ |
| **`max_position_pct_of_adv`** | ❌ **Absent** |

### 3.4 ❌ Aucune contrainte dans le simulateur backtest

Le simulateur utilise l'ADV uniquement pour le slippage, jamais pour rejeter ou réduire une position.

---

## 4. Analyse du risque par taille de compte

### Scénario 1 : Micro compte ($2K)

```
ADV minimum      = $30M
Position max     = 10% × $2K = $200
Ratio position/ADV = $200 / $30M = 0.0007%
```
✅ **Risque inexistant.** Même sur le ticker le moins liquide accepté, la position est microscopique.

### Scénario 2 : Petit compte ($25K)

```
ADV minimum      = $30M
Position max     = 10% × $25K = $2.5K
Ratio position/ADV = $2.5K / $30M = 0.008%
```
✅ **Risque négligeable.**

### Scénario 3 : Compte standard ($100K)

```
ADV minimum      = $30M
Position max     = 10% × $100K = $10K
Ratio position/ADV = $10K / $30M = 0.03%
```
✅ **Risque très faible** (0.03% de l'ADV, soit 3 secondes de volume).

### Scénario 4 : Compte large ($500K) — risque modéré

```
ADV minimum      = $30M
Position max     = 10% × $500K = $50K
Ratio position/ADV = $50K / $30M = 0.17%
```
⚠️ **Commence à être significatif.** Pour sortir, il faut ~0.17% du volume quotidien. Sur un marché stressé, cela peut prendre plusieurs heures et générer du slippage.

### Scénario 5 : Compte large + Kelly agressif — risque réel

```
ADV minimum      = $30M
Kelly fraction   = 25% × 10% = 2.5% de l'equity
Position         = 2.5% × $500K = $12.5K
Ratio            = 0.04% de ADV → OK
```

Mais si `max_position_weight` est monté à 20% et `kelly_fraction_multiplier` à 0.5 :
```
Position         = 20% × 0.5 × $500K = $50K
Ratio            = 0.17% de ADV → commence à être problématique
```

### Scénario catastrophe : le vrai risque

Le vrai risque n'est pas la taille de position individuelle, mais le **portefeuille entier** :

```
20 positions × $10K = $200K de notional
ADV moyen des 20 tickers = $50M
Ratio agrégé = $200K / $50M = 0.4%
```

Si les 20 positions doivent être liquidées le même jour (circuit breaker, krach) :
- $200K à écouler sur des tickers faisant $30-100M de volume/jour
- En pratique, c'est faisable mais avec un slippage significatif
- Le slippage volume-aware (sqrt) le capture, mais c'est un coût, pas une contrainte

**Conclusion** : pour les comptes < $100K visés par le système, le filtre ADV à $30M est une protection suffisante. Mais le code ne contient **aucune contrainte explicite** position/ADV, ce qui expose à un risque si :
1. Le `max_position_weight` est augmenté au-dessus de 10%
2. Le compte dépasse $250K
3. Le filtre ADV est abaissé (ex: $5M au lieu de $30M)

---

## 5. Plan d'action

### Priorité 1 (immédiat) : Ajouter un garde-fou `max_position_pct_of_adv` dans le ConstraintChecker

**Fichier à modifier** : `risk_management/constraints.py`

```python
# Dans ConstraintChecker.check(), après les contraintes existantes :

# Contrainte de liquidité : position ≤ X% de l'ADV
if self._cfg.max_position_pct_of_adv is not None and adv_usd is not None:
    max_notional_from_adv = adv_usd * self._cfg.max_position_pct_of_adv
    if notional > max_notional_from_adv:
        proposed_shares = self._normalize_approved_shares(max_notional_from_adv / price)
        notional = proposed_shares * price
        if proposed_shares < minimum_viable_shares:
            return 0.0, "max_position_pct_of_adv atteint"
        reduction_reason = "max_position_pct_of_adv atteint"
        LOGGER.info(
            "Position réduite par contrainte ADV pour %s : %s → %s (%.1f%% ADV)",
            symbol, original_notional, notional, self._cfg.max_position_pct_of_adv * 100,
        )
```

**Ajouter dans `RiskConfig`** :
```python
# Contrainte de liquidité : position max en % de l'ADV (None = désactivé)
max_position_pct_of_adv: float | None = None  # ex: 0.01 = 1% de l'ADV
```

**Ajouter dans `EnrichedCandidate` ou `PriceInfo`** : le champ `adv_usd` pour que le checker y ait accès.

### Priorité 2 (court terme) : Réduire la position Kelly si elle dépasse N% de l'ADV

```python
# Dans KellySizer.compute(), après le calcul de kelly_shares :
if cfg.max_position_pct_of_adv is not None and adv_usd is not None:
    max_shares_from_adv = (adv_usd * cfg.max_position_pct_of_adv) / price
    if kelly_shares > max_shares_from_adv:
        LOGGER.info(
            "Kelly réduit par ADV pour %s : %.0f → %.0f shares (%.1f%% ADV → %.1f%% ADV)",
            symbol, kelly_shares, max_shares_from_adv,
            (kelly_shares * price / adv_usd) * 100,
            cfg.max_position_pct_of_adv * 100,
        )
        kelly_shares = int(max_shares_from_adv)
```

### Priorité 3 (moyen terme) : Contrainte ADV agrégée au niveau portefeuille

Vérifier que le notional total du portefeuille ne dépasse pas X% de l'ADV agrégé :

```python
# Dans PortfolioBuilder.build() :
total_portfolio_notional = sum(e.target_notional for e in accepted)
avg_portfolio_adv = np.mean([adv for adv in adv_map.values()])
if total_portfolio_notional > 0.05 * avg_portfolio_adv:  # 5%
    LOGGER.warning(
        "Portfolio notional (%.0f) > 5%% ADV agrégé (%.0f) — risque de liquidité en cas de liquidation",
        total_portfolio_notional, avg_portfolio_adv,
    )
```

### Priorité 4 (long terme) : ADV minimum adaptatif

Ajuster dynamiquement le seuil ADV minimum en fonction de la taille du compte :

```python
def adaptive_min_adv(equity: float, max_position_weight: float = 0.10) -> float:
    """ADV minimum pour qu'une position ≤ 1% de l'ADV."""
    max_position = equity * max_position_weight
    return max_position / 0.01  # ADV ≥ 100x la position max
```

Exemples :
- $2K compte → ADV ≥ $200 / 0.01 = $20K (très permissif)
- $100K compte → ADV ≥ $10K / 0.01 = $1M
- $500K compte → ADV ≥ $50K / 0.01 = $5M

---

## 6. Synthèse (mise à jour post-implémentation 2026-06-22)

| Point | Statut | Détail |
|---|---|---|
| Filtre ADV minimum ($30M) | ✅ Présent | Élimine les penny stocks et micro-caps |
| Filtre market cap ($2B) | ✅ Présent | Redondance partielle avec ADV |
| ADV utilisé pour slippage | ✅ Présent | Modèle sqrt Almgren-Chriss |
| **Contrainte position ≤ X% ADV** | ✅ **P1 implémenté** | `max_position_pct_of_adv` dans `RiskConfig` + `ConstraintChecker.check()` |
| **Kelly réduit par ADV** | ❌ Non retenu | Redondant avec P1 — le `ConstraintChecker` capture déjà tout cas de dépassement |
| **ADV agrégé portefeuille** | ✅ **P3 implémenté** | `LOGGER.warning` dans `PortfolioBuilder.build()` si notional > 5% ADV agrégé |
| **ADV minimum adaptatif** | ✅ **P4 implémenté** | `adaptive_min_adv()` dans `common/capital_presets.py` + `with_adaptive_adv()` dans `core/filter_profiles.py` |

### Fichiers modifiés

| Fichier | Modification |
|---|---|
| `risk_management/models.py` | `PriceInfo` + champ `adv_usd: float \| None` |
| `risk_management/enums.py` | + `CONSTRAINT_MAX_POSITION_PCT_OF_ADV` |
| `risk_management/config.py` | `RiskConfig` + `max_position_pct_of_adv: float \| None` |
| `risk_management/constraints.py` | `ConstraintChecker.check()` + contrainte ADV (P1) + reason mapping |
| `risk_management/risk_checker.py` | `check_position_size()` + param `adv_usd=` |
| `risk_management/portfolio_builder.py` | Passe `adv_usd` au checker + P3 warning agrégé |
| `common/capital_presets.py` | + `adaptive_min_adv()` + `resolve_adaptive_liquidity_threshold()` (P4) |
| `core/filter_profiles.py` | + `with_adaptive_adv()` (P4) |
| `risk_management/db_io.py` | Live : `load_prices_asof()` calcule l'ADV 20j depuis `stock_bars_daily` |
| `backtesting/risk_bridge.py` | Backtest : `_build_prices()` + `volume_df`, calcule ADV 20j |
| `backtesting/cli/_impl.py` | Backtest : passe `volume_df=pivoted.get("volume")` |

### Verdict final : ✅ Protection complète

- **P1** : contrainte dure `position ≤ max_position_pct_of_adv × ADV` dans le `ConstraintChecker`. Activée dès que `max_position_pct_of_adv` est défini dans la config (ex: `0.01` pour 1%).
- **P3** : warning passif si le notionnel total du portefeuille dépasse 5% de l'ADV agrégé.
- **P4** : seuil ADV minimum adaptatif via `adaptive_min_adv(equity)` — utilisable dans l'IHM/pipeline pour ajuster dynamiquement le filtre d'éligibilité.

Pour les **petits comptes (< $100K)** avec `max_position_pct_of_adv=0.01`, la contrainte n'est pas contraignante (position max ~0.03% ADV). Elle devient active automatiquement si le compte grossit ou si les paramètres changent.

**Note** : P2 n'a pas été implémenté car redondant — le `ConstraintChecker` (P1) est exécuté après le `KellySizer` dans `PortfolioBuilder.build()`, donc toute position surdimensionnée par Kelly est de toute façon réduite par P1.

---

## 7. Fichiers clés

| Fichier | Rôle |
|---|---|
| `core/filter_profiles.py` | Définition du seuil ADV ($30M) |
| `selector/db_io.py` | Préselection SQL avec filtre ADV |
| `risk_management/position_sizer.py` | Sizing ATR — **ne regarde pas l'ADV** |
| `risk_management/kelly.py` | Kelly sizing — **ne regarde pas l'ADV** |
| `risk_management/constraints.py` | Contraintes de risque — **pas de contrainte ADV** |
| `risk_management/config.py` | `RiskConfig` — **pas de `max_position_pct_of_adv`** |
| `backtesting/simulator.py` | Simulateur — ADV utilisé pour slippage uniquement |
| `backtesting/microstructure.py` | `SlippageConfig.compute_bps(size_usd, adv_usd)` |

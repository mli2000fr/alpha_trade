# Impact de Marché — Slippage, Spread et Frais de Courtage

> **Date** : 2026-06-22
> **Statut** : ⚠️ Couvert mais améliorable — le spread réel n'est pas modélisé comme coût
> **Verdict** : Le système a une bonne base (slippage volume-aware, commission tiered, spread filter) mais le **coût du spread n'est pas débité des trades**. Le modèle peut être trop optimiste en live.

---

## 1. La question posée

> *Votre modèle de backtest semble valider des performances, mais prend-il en compte le coût réel du spread (l'écart achat-vente) et les frais de courtage à haute fréquence ? Un modèle théoriquement rentable peut devenir déficitaire en direct à cause du slippage.*

---

## 2. Ce qui existe — état des lieux

### 2.1 ✅ Modèle de slippage volume-aware

**Fichier** : `backtesting/microstructure.py` → `SlippageConfig`

| Modèle | Formule | Usage |
|---|---|---|
| `fixed` (défaut) | `base_bps` (= 0.0 par défaut) | Aucun slippage additionnel |
| `linear` | `base_bps + impact_coef * (size/ADV)` | Impact proportionnel |
| `sqrt` | `base_bps + impact_coef * sqrt(size/ADV)` | Almgren-Chriss, plus réaliste |

**Application** : le slippage volume-aware est appliqué **en plus** du `fees_pct` sur l'entrée ET la sortie :

```python
# Entrée (simulator.py L1250-1251)
extra_slippage_pct = micro.slippage.compute_bps(preliminary_size_usd, adv_usd) / 10_000.0
effective_unit_cost = entry_price * (1.0 + cfg.fees_pct + extra_slippage_pct)

# Sortie (simulator.py L1687-1688)
extra_slippage_pct = micro.slippage.compute_bps(exit_notional, adv_usd) / 10_000.0
fees_rate = float(cfg.fees_pct) + extra_slippage_pct
```

⚠️ **Problème** : par défaut, `base_bps=0.0` et `impact_coef=0.0` → le slippage volume-aware est **désactivé**. Il faut l'activer explicitement.

### 2.2 ✅ Frais de transaction (`fees_pct`)

**Fichier** : `backtesting/simulator.py` → `BacktestConfig`

```python
fees_pct: float = 0.001        # 10 bps par défaut
commission_bps: float = 5.0     # part commission
slippage_bps: float = 5.0       # part slippage
# fees_pct = (commission_bps + slippage_bps) / 10_000
```

**Application** : `fees_pct` est débité sur **chaque trade** (entrée et sortie) :

| Opération | Formule |
|---|---|
| Entrée long | `cash -= quantity * entry_price * (1 + fees_pct)` |
| Sortie long | `cash += quantity * exit_price * (1 - fees_pct)` |
| Entrée short | `cash += quantity * entry_price * (1 - fees_pct)` (crédit diminué) |
| Sortie short | `cash -= quantity * exit_price * (1 + fees_pct)` (coût augmenté) |

✅ Les frais sont bien symétriques entrée/sortie et direction-aware (long vs short).

### 2.3 ✅ Presets de commission/stress par tranche de capital

**Fichier** : `common/capital_presets.py`

Les presets ajustent `commission_bps` et `slippage_bps` selon le capital :

| Taille de compte | Commission | Slippage | Total (aller-retour) |
|---|---|---|---|
| Micro (≤$2K) | 15 bps | 25 bps | **80 bps** |
| Small ($2K-$10K) | 10 bps | 18 bps | **56 bps** |
| Standard ($10K-$50K) | 5 bps | 10 bps | 30 bps |
| Large (>$50K) | 5 bps | 5 bps | 20 bps |

✅ Ces presets sont cohérents avec la réalité Alpaca (commission gratuite mais spread + slippage significatifs pour petits ordres).

### 2.4 ✅ Modèle de commission tiercé (non intégré au simulateur)

**Fichier** : `backtesting/trading_constraints.py` → `TieredCommissionConfig`

Modèle plus réaliste avec commission fixe + taux dégressif :
- Micro : $0.50 fixe + 15 bps
- Small : $0.35 fixe + 10 bps
- Standard : 0 fixe + 6 bps
- Large : 0 fixe + 4 bps

⚠️ Ce modèle existe mais **n'est pas câblé dans le simulateur** — il est utilisé ailleurs (analyse de viabilité des tickets).

### 2.5 ✅ Filtre de spread dans le selector

**Fichier** : `selector/` → `max_spread_bps`

Le scanner filtre les tickers dont le spread dépasse un seuil :
- Strict swing cash : `max_spread_bps = 25.0`
- IEX plus large : `max_spread_bps_iex = 40.0`

✅ Cela protège contre les tickers illiquides, mais c'est un **filtre binaire**, pas un coût modélisé.

### 2.6 ✅ TCA (Transaction Cost Analysis) post-trade

**Fichier** : `execution_engine/tca.py`

Mesure le slippage réalisé : `(fill_price - decision_price) / decision_price * 10000`

✅ Permet de comparer le slippage modélisé vs réalisé en live.

---

## 3. Ce qui MANQUE — les faiblesses

### 3.1 🔴 Le spread réel n'est PAS modélisé comme coût

C'est le point le plus important. Le système dispose de données de spread réelles (`spread_bps` dans `stock_quote_snapshots`) mais les utilise uniquement comme **filtre d'éligibilité** (tickers avec spread > 25 bps exclus), pas comme **coût de transaction**.

**Conséquence** : en backtest, un trade sur AAPL (spread 1 bps) et un trade sur un small-cap (spread 20 bps) subissent le **même coût** via `slippage_bps = 5.0`. En réalité, le small-cap coûte 20 bps de spread + 5 bps de slippage = 25 bps.

```
Backtest (modèle actuel) :
  AAPL  : frais = 10 bps (aller-retour)
  XYZ   : frais = 10 bps (aller-retour)
  → PnL backtesté identique pour les deux

Live (réalité Alpaca) :
  AAPL  : spread 1 bps + slippage 5 bps ≈ 6 bps par trade
  XYZ   : spread 20 bps + slippage 25 bps ≈ 45 bps par trade
  → XYZ perd 35 bps de plus que modélisé → PnL réel inférieur
```

### 3.2 🟡 Le slippage volume-aware est désactivé par défaut

```python
# Par défaut : aucun slippage additionnel
slippage: SlippageConfig = field(default_factory=SlippageConfig)
# → SlippageConfig(base_bps=0.0, impact_coef=0.0, model="fixed")
```

Pour un petit compte qui trade des small-caps, ne pas activer le modèle sqrt (Almgren-Chriss) sous-estime significativement le coût d'exécution.

### 3.3 🟡 Le modèle de commission tiercé n'est pas intégré au simulateur

`TieredCommissionConfig` est un modèle plus fin (commission fixe + taux) mais le simulateur utilise un `fees_pct` plat. Pour un micro-compte qui fait des trades de $100, la commission fixe de $0.50 représente 50 bps — bien plus que les 5 bps du modèle plat.

### 3.4 🟡 Exécution à `next_open` uniquement

Toutes les entrées se font au prix d'ouverture du lendemain. Il n'y a pas de modélisation :
- D'exécution au marché avec slippage intraday
- De l'impact du gap overnight sur le prix d'exécution (partiellement couvert par `max_entry_gap_pct`)
- De VWAP/TWAP pour les ordres plus gros

Le filtre de gap (`should_skip_entry_for_gap`) est un bon début mais il skip l'entrée plutôt que d'ajuster le prix.

### 3.5 🟡 Pas de modélisation de la profondeur du carnet d'ordres

Pour un ordre qui représente > 1% de l'ADV, le prix d'exécution réel peut être significativement moins bon que le mid-price + spread. Le modèle sqrt (Almgren-Chriss) donne une approximation, mais sans information sur la profondeur du carnet.

---

## 4. Plan d'action

### Priorité 1 (immédiat) : Intégrer le spread réel comme coût par ticker

**Modifier** `backtesting/simulator.py` pour utiliser les données de spread réelles :

```python
# Au lieu de :
effective_unit_cost = entry_price * (1.0 + cfg.fees_pct + extra_slippage_pct)

# Faire :
spread_cost_pct = self._get_spread_cost(symbol, trade_day)  # depuis stock_quote_snapshots
total_cost_pct = cfg.fees_pct + extra_slippage_pct + spread_cost_pct
effective_unit_cost = entry_price * (1.0 + total_cost_pct)
```

Où `_get_spread_cost()` lit le `spread_bps` réel du ticker à la date donnée et le convertit en pourcentage (divisé par 10 000). Si la donnée n'est pas disponible, fallback à `slippage_bps / 10_000` (comportement actuel).

**Impact** : les backtests refléteront la réalité du spread, les small-caps seront pénalisées à leur juste valeur.

**Fichiers à modifier** :
- `backtesting/simulator.py` — ajouter `_get_spread_cost()` et l'intégrer dans `_try_open_entries()` et `_try_close_positions()`
- `backtesting/data_loader.py` — charger les spreads historiques depuis `stock_quote_snapshots`

### Priorité 2 (court terme) : Activer le slippage volume-aware par défaut

Changer les défauts de `SlippageConfig` pour les petits comptes :

```python
# Pour les presets micro/small :
microstructure = MicrostructureConfig(
    slippage=SlippageConfig(
        base_bps=5.0,      # demi-spread moyen
        impact_coef=5.0,   # 5 bps par sqrt(size/ADV)
        model="sqrt",
    )
)
```

Valeurs suggérées calibrées sur les données Alpaca :
- `base_bps = 5.0` (≈ moitié du spread médian US equities)
- `impact_coef = 5.0` (conservateur pour small-cap)

### Priorité 3 (moyen terme) : Câbler le TieredCommissionConfig dans le simulateur

Remplacer le `fees_pct` plat par le modèle tiercé :

```python
# Dans BacktestConfig.__post_init__() ou _try_open_entries() :
commission_config = resolve_commission_preset(current_equity)
trade_commission = commission_config.compute_commission_usd(notional)
trade_cost_pct = trade_commission / notional + extra_slippage_pct + spread_cost_pct
```

**Impact** : les très petits ordres (<$150) seront correctement pénalisés par la commission fixe.

### Priorité 4 (long terme) : Modèle d'exécution intraday

Remplacer l'exécution `next_open` par un modèle plus réaliste :
- Arrival price : prix d'ouverture + slippage estimé
- Pour les ordres > 1% ADV : échelonner sur la journée (TWAP simulé)
- Modéliser le coût d'opportunité du non-remplissage (limit orders)

---

## 5. Comparaison Backtest vs Live actuel

| Coût | Modèle backtest | Réalité live Alpaca | Écart |
|---|---|---|---|
| **Commission** | 5 bps (plat) | 0 bps (gratuit) | Backtest **trop pessimiste** de 5 bps |
| **Slippage générique** | 5 bps (plat) | 5-25 bps selon liquidité | Backtest **trop optimiste** pour small-caps |
| **Spread bid-ask** | ❌ Non modélisé | 1-30 bps selon ticker | Backtest **trop optimiste** de 5-20 bps |
| **Impact volume** | 0 bps (défaut) | 0-50 bps selon taille/ADV | Backtest **trop optimiste** pour gros ordres |
| **Total effectif** | ~10 bps AR | ~10-60 bps AR | **Écart potentiel : 0 à 50 bps par trade** |

Pour un portefeuille qui fait 200 trades/an avec un profit moyen de 50 bps par trade, un écart de 20 bps non modélisé représente **40% du PnL théorique qui s'évapore en live**.

---

## 6. Fichiers clés

| Fichier | Rôle |
|---|---|
| `backtesting/microstructure.py` | Modèle de slippage volume-aware (SlippageConfig) |
| `backtesting/simulator.py` | Application des frais dans `_try_open_entries()` et `_try_close_positions()` |
| `backtesting/trading_constraints.py` | Modèle de commission tiercé (TieredCommissionConfig) |
| `common/capital_presets.py` | Presets de commission/slippage par tranche de capital |
| `execution_engine/tca.py` | Analyse post-trade du slippage réalisé |
| `execution_engine/tca.py` → `compute_slippage_bps()` | Mesure du slippage réel |
| `dataIntegrityEngine/sync_latest_quotes.py` → `_compute_spread_bps()` | Calcul du spread depuis bid/ask |
| `selector/` → `max_spread_bps` | Filtre d'éligibilité (pas un coût) |
| `backtesting/data_loader.py` | Chargement des données pour le backtest (à enrichir avec les spreads) |

---

## 7. Synthèse

| Point | Statut |
|---|---|
| Frais de transaction (aller-retour) | ✅ Modélisé (fees_pct symétrique) |
| Slippage volume-aware | ✅ Existe mais désactivé par défaut |
| Commission tiercé | ✅ Code présent mais non intégré au simulateur |
| Presets par capital | ✅ Bien calibrés |
| Filtre de spread (éligibilité) | ✅ Présent |
| **Spread réel comme coût** | ❌ **Absent — priorité 1** |
| **Exécution intraday** | ❌ Absent (next_open uniquement) |
| **Profondeur de carnet** | ❌ Absent |

**Verdict** : le système n'est pas naïf — il a une bonne architecture de frais. Mais le spread réel n'étant pas débité, le backtest est **structurellement optimiste** de 5 à 20 bps par trade pour les small-caps. La priorité absolue est d'intégrer les spreads réels comme coût de transaction.

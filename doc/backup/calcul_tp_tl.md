# Calcul TP / SL / trailing : live vs backtest

## Objet

Clarifier comment sont déterminés les trois niveaux de protection/sortie :

- **TP** = take-profit
- **SL** = stop-loss initial
- **Trailing stop**

et expliquer pourquoi, dans l'IHM backtesting, on voit des champs par défaut comme `TP=0.08` et `TS=0.05`.

---

## 1) Pipeline live : ce n'est pas entièrement « fixe »

### 1.1 Stop-loss initial (SL)

Fichiers principaux :

- `execution_engine/order_intents.py`
- `execution_engine/models.py`
- `execution_engine/config.py`

La logique live passe par `resolve_initial_stop_price()` dans `execution_engine/order_intents.py`.

Règle :

1. si `target.stop_price_initial` existe et est valide, il est utilisé tel quel ;
2. sinon, si `target.risk_per_share` existe, le stop est calculé comme :

```text
stop_initial = prix_de_référence - risk_per_share
```

Donc, pour les ordres normaux issus du pipeline, le **SL initial est calculé** à partir des données de risque du selector / risk engine, et **n'est pas un simple pourcentage fixe**.

Référence utile : dans `execution_engine/config.py`, le commentaire de `manual_buy_stop_loss_pct` précise explicitement que ce pourcentage fixe ne s'applique **qu'aux achats manuels orphelins adoptés par le watcher** ; pour les achats normaux, le stop initial reste basé sur `ATR / risk_per_share`.

### 1.2 Take-profit (TP)

La logique live passe par `build_take_profit_intent()` dans `execution_engine/order_intents.py`.

Le moteur calcule d'abord :

```text
TP_pct = fill_price * (1 + profit_taker_pct)
```

puis, si `risk_per_share` est disponible, il calcule aussi :

```text
TP_risk = fill_price + 2.0 * risk_per_share
```

et prend :

```text
TP_live = max(TP_pct, TP_risk)
```

Conclusion :

- il existe bien un **plancher fixe** via `profit_taker_pct` (souvent `0.08`) ;
- mais en live, le **TP peut devenir calculé dynamiquement** si le `risk_per_share` donne une cible plus éloignée.

### 1.3 Trailing stop

La logique live passe par `build_trailing_stop_intent()` dans `execution_engine/order_intents.py`.

Le pourcentage de trailing est déterminé ainsi :

1. si `target.stop_price_initial` existe :

```text
trail_pct = (reference_price - stop_price_initial) / reference_price
```

2. sinon, si `target.risk_per_share` existe :

```text
trail_pct = risk_per_share / reference_price
```

3. sinon fallback sur la config :

```text
trail_pct = trailing_stop_pct
```

Conclusion :

- le champ `trailing_stop_pct=0.05` est un **fallback** ;
- en live, pour les ordres normaux issus des cibles d'exécution, le trailing est **souvent dérivé du risque initial**, donc **calculé**.

### 1.4 Déclenchement de la transition vers trailing

La promotion du stop initial vers le trailing passe par `resolve_trailing_activation_price()` dans `execution_engine/order_intents.py`.

Mode principal :

```text
trigger_price = fill_price + risk_per_share * trailing_activation_r_multiple
```

Fallback si `risk_per_share` absent :

```text
trigger_price = fill_price * (1 + trailing_activation_profit_pct)
```

Donc même l'activation du trailing n'est pas seulement un simple seuil fixe universel.

### 1.5 Cas spécial : achats manuels orphelins

Pour les achats manuels récupérés par le watcher (`build_manual_buy_initial_stop_intent()`), la logique est différente :

- si `trailing_stop.enabled=True` et `mode="dynamic_atr"`, le stop initial manuel peut être calculé via :

```text
stop = prix - ATR * atr_multiplier
```

- sinon fallback sur `trailing_stop.fallback_fixed_pct` ;
- sinon fallback historique sur `manual_buy_stop_loss_pct`.

Ce cas ne représente **pas** la logique standard des ordres normaux du pipeline.

---

## 2) Backtest standard : par défaut, TP et trailing sont fixes

Fichiers principaux :

- `ihm/pages/backtesting/__init__.py`
- `ihm/services/backtesting_runner.py`
- `backtesting/cli/_impl.py`
- `backtesting/simulator.py`
- `backtesting/microstructure.py`

### 2.1 Ce que montre l'IHM

Dans `ihm/pages/backtesting/__init__.py`, l'IHM affiche :

- `Take-profit (fraction)` avec défaut `0.08`
- `Trailing stop (fraction)` avec défaut `0.05`
- plus bas dans les options micro-structure : `Stop-loss initial dur (fraction)` avec défaut `0.0`

Ces valeurs sont injectées dans `BacktestRunOptions` (`ihm/services/backtesting_runner.py`), puis converties en CLI :

- `--tp`
- `--ts`
- `--initial-stop-pct`

### 2.2 Ce que fait le simulateur standard

Dans `backtesting/simulator.py`, chemin standard :

- le **SL initial** est calculé comme :

```text
initial_stop_price = entry_price * (1 - initial_stop_pct)
```

- le **TP** est calculé comme :

```text
take_profit_price = entry_price * (1 + profit_taker_pct)
```

- le **trailing stop** est calculé comme :

```text
trailing_stop_price = peak_high * (1 - trailing_stop_pct)
```

Donc, en **mode backtest standard**, oui :

- `TP=0.08` est un **paramètre fixe** ;
- `TS=0.05` est un **paramètre fixe** ;
- le `SL initial` est lui aussi **fixe** si on renseigne `initial_stop_pct`.

Autrement dit, **le backtest standard n'applique pas par défaut la même logique calculée que le pipeline live**.

---

## 3) Pourquoi ce n'est pas identique par défaut ?

### 3.1 Le backtest standard est un mode « research » simplifié

Le simulateur standard fonctionne directement sur des barres journalières OHLCV et sur des paramètres globaux simples (`tp`, `ts`, `initial_stop_pct`).

Objectifs de ce mode :

- vitesse ;
- reproductibilité ;
- simplicité d'analyse ;
- compatibilité historique avec les runs existants.

### 3.2 La logique live dépend de métadonnées supplémentaires

La logique live exploite des informations que le backtest standard n'emploie pas automatiquement dans son chemin de base, par exemple :

- `stop_price_initial`
- `risk_per_share`
- le cycle d'exécution / fills
- la transition watcher stop initial → trailing
- le lifecycle OCO

Ces données passent par `ExecutionTarget`, `OrderIntent`, le watcher et les replays d'exécution/protection.

### 3.3 Donc les champs 0.08 / 0.05 dans l'IHM ne veulent pas dire que le live est 100% fixe

Ils signifient seulement que :

- **dans le backtest standard**, ce sont les valeurs utilisées directement ;
- **dans le live**, ce sont surtout des **fallbacks** / garde-fous ou des seuils minimums, pas forcément la formule finale pour chaque trade.

---

## 4) Est-ce possible d'avoir exactement la même logique en backtest ?

## Oui, et il existe déjà une partie de l'infrastructure

Le projet contient déjà une chaîne de replay orientée fidélité live :

- `phase2_mode = risk_execution`
- `phase3_mode = execution_replay`
- `phase4_mode = protection_replay`
- `phase5_mode = watcher_replay`
- `phase7_mode = exit_lifecycle_replay`

Dans l'IHM, il existe même des presets :

- `pipeline_live_like`
- `production_parity`

Ils préremplissent justement cette chaîne pour rejouer le comportement au plus près du pipeline live.

### 4.1 Ce que fait déjà `protection_replay`

`backtesting/execution_lifecycle_replay.py` reconstruit les protections à partir des mêmes fonctions du moteur live (`execution_engine/order_intents.py`) :

- take-profit issu de `build_take_profit_intent()` ;
- stop initial issu de `build_initial_stop_intent()` ;
- trailing issu de `build_trailing_stop_intent()` ;
- prix d'activation trailing issu de `resolve_trailing_activation_price()`.

Donc **oui, le codebase sait déjà rejouer des protections calculées comme en live**.

### 4.2 Limite importante

Ce comportement n'est **pas** le chemin par défaut du backtest standard `research`.

Si on laisse :

- `phase3_mode=off`
- `phase4_mode=off`
- `phase5_mode=off`
- `phase7_mode=off`

alors on retombe sur la logique simple et fixe du simulateur.

---

## 5) Réponse directe à la question utilisateur

### « Dans l'IHM, on propose TP=0.08 et trailing=0.05 ; ça veut dire que ces 2 sont fixes ? »

**Oui en backtest standard.**

Dans le chemin standard du simulateur :

- `TP` est traité comme un pourcentage fixe ;
- `Trailing stop` est traité comme un pourcentage fixe ;
- `SL initial` est aussi fixe si on utilise `initial_stop_pct`.

**Non, ce n'est pas forcément fixe en pipeline live.**

En live :

- le `SL initial` est en priorité dérivé de `stop_price_initial` / `risk_per_share` ;
- le `TP` peut être augmenté par une règle `2R` ;
- le `Trailing stop` peut être dérivé du risque initial au lieu d'utiliser simplement `0.05`.

### « Pourquoi on ne fait pas la même chose dans backtest ? »

Parce que le mode backtest par défaut a été conçu comme un **simulateur simplifié et rapide**, tandis que la logique live complète dépend d'une **chaîne d'exécution plus riche** (targets, fills, protections, watcher, lifecycle OCO).

### « Je veux que les 3 soient calculés de la même manière que pipeline live, est-ce possible ? »

**Oui, c'est possible.**

Même mieux : **une partie est déjà disponible** via les presets IHM :

- `pipeline_live_like`
- `production_parity`

qui activent la chaîne de replay la plus proche du live.

---

## 6) Recommandation pratique

### Si l'objectif est la vitesse / exploration research

Conserver le mode standard :

- `TP` fixe
- `Trailing` fixe
- `SL initial` fixe éventuel

### Si l'objectif est la fidélité maximale au live

Utiliser dans l'IHM le preset :

- `pipeline_live_like`
ou
- `production_parity`

car ils activent les replays nécessaires pour se rapprocher de la logique réelle du pipeline live.

### Si l'objectif est de rendre ce comportement le défaut global du backtest

C'est faisable, mais ce serait un **changement de produit / de design** :

1. soit en rendant la chaîne de replay live-like activée par défaut ;
2. soit en refactorant le chemin standard du simulateur pour calculer systématiquement TP / SL / trailing à partir des `ExecutionTarget` comme le live.

Cela demanderait un arbitrage car on perdrait en partie :

- simplicité,
- vitesse,
- continuité historique des backtests standard.

---

## 7) Conclusion courte

- **Live** : les 3 protections ne sont pas purement fixes ; elles sont largement **calculées** à partir du risque (`stop_price_initial`, `risk_per_share`, parfois ATR pour achats manuels orphelins).
- **Backtest standard** : les valeurs visibles dans l'IHM (`0.08`, `0.05`, etc.) sont **bien des paramètres fixes**.
- **Parité live ↔ backtest** : **possible**, et déjà partiellement implémentée via les presets `pipeline_live_like` / `production_parity` et la chaîne `execution_replay → protection_replay → watcher_replay → exit_lifecycle_replay`.



---

## Direction-aware — Long vs Short (Plan v2 Sprint 3)

Depuis le Sprint 3, tous les calculs de TP/SL/Trailing sont **direction-aware**.
Le parametre `side` (`"buy"` = long, `"sell"` = short) est propage par `core/direction.py`.

### Take Profit

| Direction | Formule | Exemple (entree 100$, TP=12%) |
|---|---|---|
| **Long** | `entry * (1 + tp_pct)` → au-dessus | **112 $** |
| **Short** | `entry * (1 - tp_pct)` → en-dessous | **88 $** |

Si `risk_per_share` est disponible (ATR), un second TP base sur `2 × risk_per_share`
est calcule et le plus favorable (le plus eloigne) est retenu.

### Stop Loss initial

| Direction | Formule | Exemple (entree 100$, risk=3$) |
|---|---|---|
| **Long** | `entry - risk_per_share` → en-dessous | **97 $** |
| **Short** | `entry + risk_per_share` → au-dessus | **103 $** |

### Trailing Stop

- **Long** : `reference_price * (1 - trailing_pct)` — suit le prix vers le haut
- **Short** : `reference_price * (1 + trailing_pct)` — suit le prix vers le bas

### Activation du trailing

- **Long** : `entry + risk_per_share * r_multiple` → activation > entry
- **Short** : `entry - risk_per_share * r_multiple` → activation < entry

### Force-close (liquidations)

Le force-close detecte `pos.side` et utilise `buy-to-cover` pour fermer les shorts
(dans `execution_engine/executor.py` et `backtesting/simulator.py`).

### Fonctions de reference

Dans `core/direction.py` :
- `compute_take_profit_price(side, entry_price, tp_pct)`
- `compute_initial_stop_price(side, entry_price, risk_per_share, stop_pct)`
- `compute_trailing_stop_price(side, reference_price, trailing_pct)`

Dans `execution_engine/order_intents.py` :
- `resolve_initial_stop_price(reference_price, target, side)`
- `resolve_trailing_activation_price(fill_price, config, target, side)`
- `build_take_profit_intent(parent, fill_qty, avg_fill_price, config, target)`
- `build_initial_stop_intent(parent, fill_qty, avg_fill_price, config, target)`
- `build_trailing_stop_intent(parent, fill_qty, avg_fill_price, config, target)`

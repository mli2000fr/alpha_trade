# Audit du backtest `20260817_165433_2785da86` (+63.9% sur 1 an 5 mois)

> **Date de l'audit** : 2026-08-17
> **Auteur** : revue technique (audit profond demandé car le résultat semblait « trop beau »)
> **Usage** : document de revue — peut être transmis à un relecteur externe (GPT) pour contre-analyse

---

## 1. Contexte général du système (à lire avant tout)

Le projet **AlphaTrade** (dossier `F:\projets`) est un système de trading swing ML
sur actions US (NYSE/NASDAQ), horizon de détention de quelques jours à quelques
semaines.

**Architecture ML (pivot per-symbol, 2026-08-14)** :
- **Global Ranking Model** (CatBoost RMSE) : classe cross-sectionnellement les
  symboles de l'univers par rendement futur attendu sur 5 horizons (H3/H5/H10/H15/H20)
  → `global_rank ∈ [0,1]`. IC Rank ≈ 0.02, IC IR > 1.
- **Cascade ML** : filtre `global_rank_{best_horizon}` (top 10% pour LONG, bottom 10%
  pour SHORT) + proba per-symbol `min_prob_classification = 0.55`.
- **Batch champion** : `B25` = `model-factory-20260811223551-ef2cd0`
  (B21 Short+SPY+CAPM+YetiRank, entraîné 2016-01-01 → 2025-12-31). Stocke
  `best_horizon = 10` dans son metadata, mais la **production gèle H20** via
  `config.yaml` (`backtest_horizon: 20` / `live_horizon: 20`).
- Le batch est **per-sector synthétique** : les probas per-symbol sont dérivées des
  rangs globaux via `modelFactory/synthesize_global_rank_predictions.py`
  (run `{batch}_globalrank_synth`). `predicted_side` = `global_rank_20` pour le live.

**Pile « gelée » validée par la campagne de robustesse (2026-08-17)** :
`B25 → H20 → top 10% → P14 → m8` (max_positions 8), coûts canoniques réels
(spread bid-ask `stock_quote_snapshots` + commission 1 bps + slippage 2 bps).
Benchmark OOS 2026 archivé (`OOS2026_B25_P14_m8_v1`) : **+27.09% / DD 3.10% /
PF 2.22 / 77 trades (46L/31S)**, parité bit-for-bit vérifiée.

**Briques d'exécution (pipeline production-parity)** :
`--engine-mode pipeline --ml-pit-strategy use-persisted --phase2-mode risk_execution
--phase3-mode execution_replay --phase4-mode protection_replay --phase5-mode
watcher_replay --phase7-mode exit_lifecycle_replay`. PIT strict
(`strict_pit=True`, `scores_pit_mode=exact`, `macro_pit_mode=yaml_default`).

---

## 2. Identification du backtest audité

- **Run ID** : `20260817_165433_2785da86` (format IHM `YYYYMMDD_HHMMSS_hash`)
- **Emplacement** : `artifacts/ihm_backtesting_runs/run/20260817_165433_2785da86/`
- **Lancé depuis l'IHM** (page Backtesting) le 2026-08-17 à 16:54:33
- **Statut** : terminé
- **Résultat affiché** : **+63.92%** sur 1 an 5 mois → jugé « trop beau », d'où cet audit.

Fichiers d'artefacts présents (tous les réplicats du pipeline) :
`report.json`, `trade_audit_log.csv` (1 294 événements), `trades.csv`,
`equity_curve.csv`, `phase2_risk_entries.csv`, `phase3_execution_replay_signals.csv`,
`phase4_protection_replay.csv`, `phase5_watcher_replay_signals.csv`,
`phase7_exit_lifecycle_replay.csv`, `execution_broker_like_events.csv`,
`fidelity_manifest.json`, `selection_target_parity_summary.json`, `combined.log`,
`stdout.log`, `stderr.log`.

---

## 3. Configuration exacte du run (extraits du log `stdout.log`)

```
risk_management.config -- load_risk_config: equity=4000 preset=capital_2001_5000
  short_selling_enabled=True (preset=capital_2001_5000)
  conviction_calibration_mode=off
Backtest Alpha Trade : 2025-01-01 → 2026-05-31, capital=4,000$
  preset_capital=capital_2001_5000 (explicit_key)
  TP=12.0%, TS=7.0%, max_positions=8
  protection_logic=live_like
  engine_mode=pipeline strict_pit=True
  scores_pit_mode=exact
  macro_pit_mode=yaml_default
  phase2_mode=risk_execution
  phase3_mode=execution_replay
  phase4_mode=protection_replay
  phase5_mode=watcher_replay
  phase7_mode=exit_lifecycle_replay
  ml_mode=auto, sentiment_mode=auto
```

Paramètres retenus :

| Paramètre | Valeur | Commentaire |
|---|---|---|
| Période | 2025-01-01 → 2026-05-31 | 352 jours ouvrés (1 an 5 mois) |
| Capital initial | 4 000 $ | compte 2001-5000 (preset `capital_2001_5000`) |
| Modèle ML | **B25** = model-factory-20260811223551-ef2cd0 | champion |
| Cascade | `top_pct 0.10`, `min_prob 0.55`, horizon `global_rank_20` | identique pile gelée |
| TP | **12.0% fixe** | ⚠️ différent de la pile gelée (TP = min(3×ATR, 7%)) |
| TS | **7.0% fixe** | proche du trailing long 7% de la pile gelée |
| max_positions | 8 | identique pile gelée (m8) |
| Coûts | canoniques réels (spread réel chargé) | ✓ |
| PIT | strict, exact | ✓ pas de look-ahead |

> ⚠️ **Premier point de vigilance** : le run IHM utilise **TP = 12% fixe**, alors que
> la pile gelée validée (P14) utilise un take-profit **dynamique ATR**
> `min(3 × ATR_20, 7% du prix)`. Un TP plus large modifie le profil de gain.

---

## 4. Résultats globaux (report.json)

| Métrique | Valeur |
|---|---|
| final_value | 6 556.61 $ |
| **total_return_pct** | **+63.92%** |
| CAGR | 42.45% |
| Sharpe | 3.25 |
| Sortino | 5.40 |
| Max drawdown | **5.64%** |
| Calmar | 7.52 |
| **total_trades** | **276** (168 LONG / 108 SHORT) |
| Win rate | 46.74% |
| Profit factor | **1.811** |
| Long PnL | +1 133.47 $ |
| Short PnL | +1 161.24 $ |
| PnL net | +2 294.70 $ |
| Gross exposure moyen | 72.75% (max 124%) |
| Net exposure moyen | −24.88% (bias short) |
| Turnover | 37.16% |
| Force close exits | 0 |

---

## 5. Décomposition par année (equity_curve.csv) — LE +63.9% est COHÉRENT

| Année | Jours | Rendement | Référence validée |
|---|---|---|---|
| **2025** | 250 | **+46.38%** | P23 m8 2025 = **+45.95%** (bootstrap robustesse) ✅ quasi identique |
| **2026** | 102 | **+11.79%** | Benchmark 2026 pile gelée = **+27.09%** ⬇️ inférieur |

**Lecture** :
- Le +63.9% total est **porté par 2025** (+46.4%), une année excellente pour la
  stratégie (cohérente avec la campagne de robustesse).
- Sur 2026, ce run (TP 12%) est **MOINS bon** que le benchmark pile gelée (TP ATR 7%) :
  +11.79% vs +27.09%. Le TP plus large n'est PAS un « gonfleur » — il dégrade même 2026.
- **Le résultat n'est donc pas « trop beau » par rapport aux composantes validées.**
  (1.464 × 1.118 − 1 = +63.7% ≈ +63.9% observé.)

---

## 6. Audit des coûts et frais

### 6.1 Spread réel chargé
```
backtesting.data_loader -- Spreads chargés : 352 jours, 7595 symboles,
médiane=31.4 bps, [2025-01-01 → 2026-05-31]
```
- Le spread bid-ask réel est chargé et appliqué (coût canonique).
- Notional RT total : ~137 369 $ ; coût estimé à ~10.3 bps RT ≈ **142 $**.
- P&L net 2 294.70 $ → P&L brut estimé ≈ 2 436 $ (coût ~6% du P&L brut).

### 6.2 Vérification de la pénalité d'entrée (prix vs open réel)
Comparaison `entry_price` du log avec `open` réel de `stock_bars_daily` :

| trade | side | date | open | entry_price | diff_bps |
|---|---|---|---|---|---|
| CPRI | buy | 2025-01-03 | 20.65 | 20.4435 | −100.0 |
| CHRD | sell | 2025-01-03 | 119.48 | 120.6748 | +100.0 |
| MD | buy | 2025-01-03 | 13.03 | 12.8997 | −100.0 |
| MUR | sell | 2025-01-03 | 30.97 | 31.2797 | +100.0 |
| … | | | | | ±100.0 sur TOUS |

**Résultat : 284/284 entrées (100%) à `entry_price = open ± 1%` exact** :
- Longs : achetés à **open − 1%**
- Shorts : vendus à **open + 1%**

> ⚠️ C'est le **mécanisme de pullback limit** (`entry_limit_offset_pct = 0.01`,
> défaut du simulateur, non exposé en CLI avant cet audit) — voir §7.

---

## 7. DÉCOUVERTE MAJEURE : le pullback limit 1% à l'entrée (biais d'exécution)

### 7.1 Origine dans le code (`backtesting/simulator.py`)

```python
# BacktestConfig (défaut, ligne ~217)
entry_limit_offset_pct: float = 0.01  # 1% sous le prix signal

# Dans la boucle d'entrée (ligne ~1504)
if cfg.entry_limit_offset_pct > 0:
    limit_price = compute_pullback_limit_price(side, signal_price, float(cfg.entry_limit_offset_pct))
    if is_short_side(side):
        entry_price = limit_price          # ← INCONDITIONNEL pour le SHORT
    else:
        day_low = ...
        if day_low is not None and ... and day_low <= limit_price:
            entry_price = limit_price      # ← conditionnel pour le LONG
        else:
            ... entry_rejected (pullback_limit_not_reached) ...
            continue
```

### 7.2 Comportement observé
- **LONG** : ordre limit d'achat à `open × (1 − 0.01)` = open − 1%. Rempli si le plus
  bas du jour ≤ open×0.99. Comme un repli intraday de 1% est très fréquent, **rempli
  ~100% du temps** → on achète systématiquement 1% sous l'open.
- **SHORT** : le code fait `entry_price = limit_price` **SANS aucune condition de
  remplissage** (le commentaire « short_selling_enabled=false donc ce chemin n'est
  pas emprunté » est **obsolète** : les shorts sont actifs). → on vend systématiquement
  à `open + 1%`, même si le plus haut du jour n'atteint jamais ce niveau.
  C'est un **BUG d'exécution short** (remplissage impossible dans le cas d'une journée
  baissière où high < open×1.01).

> Confirmation externe dans `prompt/archive/short/plan_v2.md` :
> « Le `entry_limit_offset_pct` de 0.01 (pullback -1%) doit être inversé pour le short
> (limit +1% au-dessus du signal). » — le prix est inversé, mais la **condition de
> remplissage** ne l'est pas.

### 7.3 Impact estimé
- Chaque trade gagne ~1% du notional d'entrée (longs achetés moins cher, shorts vendus
  plus cher).
- Notional d'entrée moyen ≈ 496 $ × 284 entrées ≈ 141 k$ → **gain pullback ≈ 1 410 $**
  sur un P&L net de **2 294 $** (~60% du P&L net).
- **Sans pullback** (exécution au marché = open), le P&L serait ≈ 880 $ → rendement
  ≈ **+22%** au lieu de **+63.9%**.

> ✅ **Mesuré en §8** : le vrai rendement au marché est **+25.86%** (vs ≈ +22% estimé
> ici) — l'estimation était du bon ordre de grandeur, et surtout le **P&L short
> s'effondre de +1 151 $ à −77 $** quand le pullback est désactivé (cf. §8) : le bug
> de remplissage short était la source dominante du biais.

### 7.4 ⚠️ Ce biais est-il spécifique à ce run ? NON
Le **même ±100 bps** est observé sur le **benchmark validé** OOS 2026
(`cmp_b25_h20_2026_prodparity_repro_h20cfg_m8`, +27.09% archivé) :
```
benchmark 2026 : FMC buy -100, GDDY sell +100, VRNS buy -100, LBRDK sell +99.99, ...
```
→ Le pullback 1% est un **biais du simulateur présent dans TOUS les backtests**
(parité bit-for-bit de la pile gelée incluse). Il ne rend PAS ce run particulier
plus gonflé que les autres, mais il gonfle **tous** les backtests de ~1% par trade
à l'entrée (et le remplissage short inconditionnel est un bug à part entière).

### 7.5 Conséquence pour la production
- La **production exécute au marché** (pas d'ordres limit pullback systématiques).
- → Les backtests sont **optimistes de ~1% par trade** par rapport à l'exécution réelle.
- → Impact sur la décision de mise en réel : à quantifier précisément (voir §8).

---

## 8. Mesure précise du biais pullback — RÉSULTATS

Pour quantifier le biais, un flag de diagnostic **`--entry-limit-offset-pct`** a été
ajouté au CLI. 4 runs lancés le 2026-08-17 18:11 :

| Run | Période | Config | Offset | Rendement | DD | PF | trades |
|---|---|---|---|---|---|---|---|
| `pb_ctl_2026` | 2026 | pile gelée (TP ATR 7%) | 0.01 | **+27.093%** | 3.096% | 2.224 | 77 |
| `pb0_2026` | 2026 | pile gelée (TP ATR 7%) | **0** | **+21.313%** | 3.369% | 1.717 | 85 |
| `ihm2526_ctl` | 2025-2026 | TP12/TS7/m8 | 0.01 | **+63.768%** | 5.55% | 1.815 | 276 |
| `ihm2526_pb0` | 2025-2026 | TP12/TS7/m8 | **0** | **+25.863%** | 7.81% | 1.223 | 301 |

**Contrôles validés** :
- `pb_ctl_2026` = **+27.093%** → parité bit-for-bit avec le benchmark OOS 2026 archivé
  (le flag `0.01` reproduit exactement l'ancien comportement).
- `pb0_2026` = **+21.313%** → exécution au marché (offset 0).

### Impact mesuré du biais pullback sur le benchmark 2026

| Métrique | Avec pullback (0.01) | Sans pullback (0) | Écart |
|---|---|---|---|
| Rendement | +27.09% | +21.31% | **−5.78 pts** |
| Profit factor | 2.224 | 1.717 | −0.51 |
| Max drawdown | 3.10% | 3.37% | +0.27 pt |
| Trades | 77 | 85 | +8 (le pullback rejetait des trades) |
| Win rate | 50.6% | 49.4% | −1.2 pt |

**Le biais du pullback est réel et significatif : ~5.8 pts de rendement sur 2026**
(et PF −0.5). Il gonfle TOUS les backtests qui utilisent l'ancien défaut.

### Impact mesuré du biais pullback sur le run audité (2025-2026)

| Métrique | Avec pullback (0.01) | Sans pullback (0) | Écart |
|---|---|---|---|
| Rendement | +63.77% | +25.86% | **−37.9 pts** |
| Profit factor | 1.815 | 1.223 | −0.59 |
| Max drawdown | 5.55% | 7.81% | +2.26 pts |
| Sharpe | 3.26 | 1.37 | −1.89 |
| Trades | 276 | 301 | +25 |
| Win rate | 46.7% | 43.2% | −3.5 pts |
| Long PnL | +1 138 $ | +889 $ | −249 $ |
| Short PnL | +1 151 $ | **−77 $** | **−1 228 $** |

**Lecture décisive** : désactiver le pullback fait passer le **P&L short de +1 151 $ à
−77 $** — le remplissage short inconditionnel à `open + 1%` générait **pratiquement tout
le profit du book short**. Le long n'est affecté que de −249 $. Le **+63.9% du run audité
était donc très largement un artefact du bug short à l'entrée** : en exécution au marché,
le rendement réaliste est **+25.86% / PF 1.22 / DD 7.8%** — positif, mais avec une marge
de robustesse nettement plus faible.

---

## 8bis. Correction appliquée (2026-08-17)

Suite à cet audit, le souci de **1% à l'entrée** a été corrigé dans le simulateur :

1. **Bug du remplissage short corrigé** (`simulator.py`) : l'ordre limit short était
   rempli **inconditionnellement** à `open + 1%` (le code faisait `entry_price =
   limit_price` sans vérifier que le plus haut du jour atteignait la limite).
   Désormais, comme pour le long (`day_low <= limit`), le short n'est rempli que si
   `day_high >= limit_price`, sinon `entry_rejected` (`pullback_limit_not_reached`).

2. **Pullback désactivé par défaut** : `entry_limit_offset_pct` passe de **0.01 → 0.0**
   (`simulator.py`). L'exécution par défaut est désormais **au marché (open)**,
   réaliste par rapport à la production. Le flag `--entry-limit-offset-pct > 0`
   permet de réactiver le pullback (réservé à la reproduction des runs d'avant
   2026-08-17). Le flag CLI a été aligné (défaut `0.0`).

**Aucun biais de sortie détecté** : les prix de sortie (`replay_exit_price`) sont
identiques avec/sans pullback — le replay de sortie (TP/SL/trailing) n'est pas affecté.
Le biais de 1% était entièrement à l'entrée (le prix d'entrée biaisé faussait ensuite
indirectement les sorties via les niveaux TP/SL calculés sur ce prix).

**⚠️ Conséquence** : les résultats antérieurs au 2026-08-17 (benchmark OOS 2026
+27.09%, campagne de robustesse, stress coûts/fills) ont été calculés AVEC le pullback
0.01. Ils sont donc optimistes de ~5.8 pts sur 2026. **Ils doivent être relus à la
lumière de cette correction** (le benchmark « au marché » 2026 est +21.31% / PF 1.72).

Sur le run audité (2025-2026), l'impact mesuré est encore plus fort :
**+63.77% → +25.86%** (−37.9 pts), PF 1.81 → 1.22, DD 5.55% → 7.81%, 276 → 301 trades.
L'essentiel du biais vient du **remplissage short inconditionnel** : le P&L short chute
de +1 151 $ à **−77 $** quand le pullback est désactivé, contre seulement −249 $ pour le
long. **Le +63.9% du run IHM était très largement un artefact du biais short à l'entrée.**


---

## 9. Autres points vérifiés (rien d'anormal)

- **PIT / look-ahead** : `strict_pit=True`, `scores_pit_mode=exact`, cache OHLCV
  `2024-10-26 → 2026-05-31` (cache hit) → aucune fuite de données futures détectée.
- **Taille de positions / levier** : notional entrée moyen 496 $ (poids ~12.4% du
  capital 4 000 $), gross moyen 72.8%, max 124% → cohérent avec max_positions 8,
  pas de sur-levier anormal.
- **Raisons de sortie** : 246 trailing_stop, 29 take_profit, 1 initial_stop —
  répartition normale.
- **Réjections d'entrée** : 100 `entry_rejected` (sur 384 tentatives) — taux normal.
- **Réconciliation** : `force_close_exits = 0`, fichiers `fidelity_manifest`,
  `selection_target_parity_summary`, `compare_to_live_summary` présents et remplis.

---

## 10. Verdict

1. **Le run IHM n'a PAS de bug de gonflement spécifique.** Il est cohérent avec les
   runs validés : 2025 (+46.4%) ≈ P23 m8 validé (+45.95%) ; 2026 (+11.8%) est même
   **inférieur** au benchmark pile gelée (+27.09%) à cause du TP 12%.
2. **MAIS le simulateur a un biais d'exécution systématique** : le **pullback limit 1%**
   à l'entrée (`entry_limit_offset_pct=0.01`, défaut) gonfle **tous** les backtests de
   ~1% par trade à l'entrée — **y compris le benchmark OOS 2026 archivé (+27.09%)**.
   Le remplissage **short inconditionnel** est un bug du code.
3. **Le +63.9% était un artefact du biais d'exécution à l'entrée** : au marché
   (offset 0), le run audité tombe à **+25.86% / PF 1.22 / DD 7.8%**. Le remplissage
   short inconditionnel à `open + 1%` générait presque tout le P&L short (+1 151 $ →
   −77 $). Le run reste cohérent en structure (2025 forte, 2026 faible), mais sa marge
   de robustesse est bien plus faible qu'affichée. Tous les backtests (y compris les
   benchmarks de robustesse) doivent être lus en connaissant ce biais d'exécution.

## 11. Recommandations

1. **Quantifier et corriger le biais pullback** : mesurer les 4 runs de contrôle (§8),
   puis décider :
   - Soit corriger le bug du remplissage short inconditionnel (ajouter la condition
     `day_high >= limit_price` pour les shorts) ;
   - Soit désactiver le pullback par défaut (`entry_limit_offset_pct = 0`) pour que
     les backtests reflètent l'exécution au marché de la production.
2. **Revalider le benchmark OOS 2026** sans pullback (ou avec pullback corrigé) avant
   toute décision de mise en réel, car le benchmark archivé intègre le même biais.
3. **Garder la pile gelée** (B25 → H20 → top 10% → P14 → m8) : ce run IHM n'est pas
   une remise en cause du modèle, seulement un signal sur la qualité d'exécution
   simulée.

---

## 12. DÉCOUVERTE #2 — le bug de propagation du TP ATR (corrigé le 2026-08-17)

### 12.1 Constat
Dans **tous** les runs pipeline (benchmark OOS 2026, `pb0_2026`, `ihm2526_*`, run IHM),
les sorties `take_profit` sortaient à **11,8 % → 30,6 %** malgré les flags
`--tp-atr-multiple 3.0 --tp-max-pct 0.07` → le TP effectif était **12 % fixe**
(fallback), jamais le TP ATR `min(3×ATR, 7 %)` attendu en P14.

### 12.2 Cause racine (`execution_bridge.py` + `execution_replay.py`)
Le TP ATR était bien calculé dans `portfolio_builder.py`
(`PortfolioEntry.take_profit_price` via `tp_params_for()`), mais **perdu à la
conversion vers l'`ExecutionTarget`** :

```
PortfolioEntry (TP ATR ✓) → ExecutionTarget (take_profit_price = None)
    → build_take_profit_intent() → fallback config.profit_taker_pct = 0.12 → TP 12 %
```

Les 2 bridges copiaient `stop_price_initial`, `risk_per_share`, `atr_20`… mais
**pas** `take_profit_price` (champ ajouté en 2026-08-09, jamais branché).

### 12.3 Correctif
Ajout de `take_profit_price=entry.take_profit_price` dans
`portfolio_entries_to_execution_targets()` (execution_bridge.py) et
`_entry_to_target()` (execution_replay.py). Vérifié : smoke test OK, targets phase2
remplis (ex. CPRI TP 22.05 = +6,8 %, CHRD short 110.57 = −7,5 %).

### 12.4 Impact
**Tous les résultats antérieurs au correctif utilisaient le TP 12 % fixe**, pas le
TP ATR. La campagne de robustesse et le benchmark +27,09 % sont donc à relire avec
cette correction.

---

## 13. DÉCISION — le risk/TP passe en H20 par défaut (config.yaml)

- `config.yaml` gelait **H20 pour la cascade ML** (sélection TOP/BOTTOM) mais le
  `RiskConfig.best_horizon` restait **10** (batch metadata B25, codé en dur) → stop
  2,5×ATR / TP `min(3×ATR, 7 %)` par défaut.
- Correctif (`risk_management/config.py`) : `load_risk_config` lit désormais
  `batch_diagnostics.backtest_horizon` / `live_horizon` (= 20) comme `best_horizon`
  par défaut → **stop 3,5×ATR / TP `min(4×ATR, 13 %)`**.
- Pipeline live (`pipeline_runner.py`) aligné sur `live_horizon`.
- Le flag `--best-horizon` reste disponible pour reproduire H10.

---

## 14. Test A (H10 risk) vs Test B (H20 risk) — 2025-2026

| Métrique | Test A — H10 risk | **Test B — H20 risk** |
|---|---|---|
| Rendement | +9,53 % | **+29,52 %** |
| 2025 / 2026 YTD | +6,62 % / +2,73 % | **+21,91 % / +6,24 %** |
| Profit factor | 1,064 | **1,52** |
| Max DD | 12,60 % | **10,67 %** |
| Trades | 428 | 237 |
| Win rate | 45,3 % | 48,9 % |
| Holding moyen | 7,75 j | 15,43 j |
| Long / Short PnL | +909 / −565 | **+765 / +400** |
| Sharpe | 0,55 | **2,08** |

**Lecture** : laisser courir les positions sur l'horizon H20 du modèle (stop 3,5×ATR →
positions plus petites à risque monétaire constant, TP jusqu'à 13 %) produit
**simultanément** un rendement supérieur, un DD plus faible, moins de trades et un
**short redevenu rentable** (+400 vs −565).

---

## 15. Validation OOS 2026 (H20 risk)

`oos2026_p14_h20risk` — 2026-01-02 → 2026-05-31, 4 000 $, marché, P14, overlays :

| Métrique | Valeur |
|---|---|
| **Rendement** | **+14,37 %** (5 mois, ≈ 39 % annualisé) |
| **Profit factor** | **1,76** |
| Max DD | **3,04 %** |
| Sharpe / Sortino | 3,51 / 6,16 |
| Trades | 82 (50 L / 32 S) |
| Win rate | 50,0 % |
| Long / Short PnL | +250 / **+320** |

Le gain H20 tient **hors période** (PF 1,76, short positif, DD 3 %). Correctif
pullback confirmé (0 entrée à ±100 bps, fill = open réel), TP H20 actif (médiane
+12,5 %, max +15,3 %).

---

## 16. Bootstrap H20 — P(DD > 10/15/20 %)

Block bootstrap (bloc 20 j, 5 000 trajectoires) sur les rendements journaliers du
run H20 (351 jours, 2025-2026) :

| Horizon | DD moyen | DD p99 | **P(DD>10 %)** | **P(DD>15 %)** | **P(DD>20 %)** |
|---|---|---|---|---|---|
| 1 an | 6,0 % | 14,3 % | 7,5 % | 0,7 % | 0,0 % |
| 2 ans | 7,6 % | 16,1 % | 16,2 % | 1,8 % | 0,2 % |
| 3 ans | 8,5 % | 17,4 % | 25,4 % | 3,1 % | 0,4 % |
| 4 ans | 9,2 % | 18,9 % | 32,9 % | **4,8 %** | 0,6 % |

**Lecture** : sur 4 ans, **P(DD > 15 %) ≈ 4,8 %** (1 fois sur ~20) et le DD p99
≈ 19 %. ⚠️ **Le 3,04 % observé (OOS 5 mois) n'est pas le DD plausible** — tout levier
> 1 élargirait cette distribution.

---

## 17. Stress coûts H20 (2025-2026)

| Métrique | Base | **×2** | **×3** | **RT44** |
|---|---|---|---|---|
| Rendement | +29,52 % | +24,55 % | +15,78 % | +16,95 % |
| **Profit factor** | **1,52** | **1,41** | **1,25** | **1,27** |
| Max DD | 10,67 % | 11,16 % | 12,90 % | 12,52 % |
| Trades | 237 | 238 | 239 | 239 |
| Short PnL | +400 | +310 | +84 | +75 |

**Lecture** : **les coûts détruisent progressivement le rendement mais ne détruisent
pas le signal** — le PF reste ≥ 1,25 sous ×3 et RT44 (44 bps aller-retour = ~3-4× le
coût réel), le short reste positif partout. Formulation précise sur le DD : *le
stress coûts n'entraîne pas d'explosion du DD sur 2025-2026 (10,7 → 12,9 %), tandis
que le bootstrap 4 ans indique qu'un DD proche de 19 % reste plausible dans une
trajectoire défavorable* (deux échelles temporelles différentes, non comparables
directement).

---

## 18. Verdict final (2026-08-17)

| Volet | Verdict |
|---|---|
| Backtest (pile **B25 → sélection H20 → risk H20 → marché → P14 → m8**) | **validé** ✅ |
| Robustesse coûts | **validée** ✅ (PF ≥ 1,25 sous ×3 / RT44) |
| Robustesse statistique | **raisonnable** ✅ (limitée par l'historique H20 disponible, 17 mois) |
| **Levier** | **ne pas toucher** ⚠️ (budget 15 % = plafond psychologique, pas un objectif ; P(DD>15 %) 4 ans ≈ 4,8 % sans levier) |
| **Paper Alpaca** | **GO** 🚀 |

Pendant le paper, surveiller : prix de remplissage vs backtest, spread réel,
slippage, nb de trades exécutés, exposition brute/nette, poids moyen, P&L L/S,
durée moyenne, DD réel, divergence signaux ML vs trades — **sans changer la config**.

> **Note finale** : après toutes les corrections (pullback, short fill, TP ATR,
> H10/H20), le fait que la stratégie reste **positive** (OOS 2026 : PF 1,76 ; 2025-26 :
> PF 1,52) est beaucoup plus intéressant que le +63,9 % initial, qui était en grande
> partie un artefact d'exécution simulée.

---

## 19. Analyse ORACLE de la sélection — run IHM `20260817_205031_2a2836d1` (2026-08-17)

**Question** : le modèle trouve-t-il les achats/ventes « oracle » (avec information
parfaite) ? Pour chaque entrée, le symbole est-il dans le **TOP 10 %** (long) /
**BOTTOM 10 %** (short) des rendements futurs RÉELS du jour ?

**Méthode** (script `scripts/oracle_selection_audit.py`) :
- Univers = **~399 symboles/jour** prédits par le Global Ranking ML
  (`model_predictions`, run `model-factory-20260811223551-ef2cd0_globalrank_synth`) —
  le vrai pool où la cascade top-10 % opère *(⚠️ un premier passage sur
  `stock_scores_history` (~44 syms/jour) était faux — c'est `model_predictions` qu'il faut)*.
- Rendement futur = `adj_close[D+H]/adj_close[D] − 1` (close-to-close), H = 10 et 20.
- Baseline aléatoire = 10 %.

### 19.1 % dans l'oracle (3331 entrées : 2639 long / 692 short)

| Horizon | Longs dans top-10 % | Longs dehors | Shorts dans bottom-10 % | Shorts dehors |
|---|---|---|---|---|
| **H10** | **16.1 %** | 83.9 % | **9.5 %** | 90.5 % |
| **H20** | **16.7 %** | 83.3 % | **8.2 %** | 91.8 % |

- **Longs** : ~1,6× le hasard (16,7 % vs 10 %) → **skill réel mais faible** ; loin de l'oracle (100 %).
- **Shorts** : ≈ hasard (8-9,5 % vs 10 %) → **pas de preuve de signal directionnel short**.
- Distribution des longs en **U** (surreprésentés en D10 **et** D1) → signal d'amplitude/volatilité
  plus que directionnel pur.

### 19.2 Courbe de rendement par décile (univers entier, n≈13 900/jour)

Le ranking est **monotone** — c'est économiquement utile :

| Décile | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **H10** ret moyen | −12.33 % | −6.24 % | −3.80 % | −2.08 % | −0.61 % | +0.78 % | +2.29 % | +4.07 % | +6.66 % | **+14.08 %** |
| **H20** ret moyen | −17.14 % | −9.15 % | −5.67 % | −3.19 % | −0.99 % | +1.07 % | +3.37 % | +6.07 % | +10.00 % | **+20.86 %** |

- **Spread D10 − D1** = **+26.4 pts (H10)** et **+38.0 pts (H20)** → l'opportunité est énorme.
- Les trades ML longs tombés en D10 battent la moyenne du décile (H20 : +24.85 % vs +20.86 %).

### 19.3 Capture ratio (plafond oracle, même mix long/short 79/21)

| Portefeuille (H20, par entrée) | Retour |
|---|---|
| **Random** (même mix) | +0.32 % |
| **Book ML** (réel) | **+2.65 %** |
| **Oracle plafond** (top-10 % long + bottom-10 % short) | +20.09 % |

→ **Capture ratio ≈ 12 %** (10 % en H10) : le ML gagne ~8× le hasard par entrée, mais ne capte
qu'une petite fraction de l'alpha théorique disponible. La marge d'amélioration est grande.

### 19.4 Test moteur complet ML vs Random

Pour vérifier que ce skill **survit à la mécanique complète** (coûts, TP/stop H20,
exécution), un backtest d'ablation a été ajouté : `--cascade-rank-mode {ml,random}`
(les rangs globaux sont randomisés — seedé —, les prédictions per-symbol et toutes les
mécaniques restent identiques : même top_pct, min_prob, risque H20, P14, m8, coûts).

**Résultats (2025-01-01 → 2026-05-31, 3 seeds random)** :

| Métrique | ML (B25) | Random 42 | Random 777 | Random 2026 | Random moy. | ML vs moy. |
|---|---|---|---|---|---|---|
| Rendement | **+29.52 %** | +12.07 % | +22.91 % | +16.39 % | +17.12 % | **+12.4 pts** |
| Sharpe | **2.08** | 0.85 | 1.45 | 1.09 | 1.13 | **+0.95** |
| Profit Factor | **1.52** | 1.19 | 1.36 | 1.30 | 1.28 | **+0.24** |
| Win rate | **48.9 %** | 39.7 % | 42.0 % | 43.4 % | 41.7 % | **+7.2 pts** |
| Trades | 237 (156L/81S) | 214 | 207 | 205 | ≈209 | |
| PnL Long | **+764.61** | +543.23 | +361.97 | +343.79 | +416 | |
| PnL Short | **+400.47** | −88.56 | +461.48 | +318.40 | +230 | |
| Max DD | 10.67 % | 9.75 % | 7.51 % | 6.43 % | 7.9 % | |

**Lecture** : le ranking ML **bat robustement le Random sur les 3 seeds** — le ML surpasse
le **meilleur** seed random en rendement (+29.52 vs +22.91), en Sharpe (2.08 vs 1.45) et
en PF (1.52 vs 1.36). Le Random reste positif (+12 à +23 %) car les mécaniques
(direction per-symbol + TP/stop H20 + marché 2025-26) ont un fort « base rate », mais le
ranking ML ajoute en moyenne **+12.4 pts de rendement** et améliore Sharpe/PF/win rate.
Le short random est très variable (−88 à +461) : sans le ranking, le short n'a pas
d'espérance stable — c'est la sélection short du ranking qui le rend positif en moyenne.

> ⚠️ Note : à la fin de chaque run CLI, la sauvegarde de `report.json`/`trades.csv`
> échoue de façon intermittente (seed 42 : processus sorti après l'audit log ; seeds
> 777/2026 : sauvegarde complète OK) — en cas d'échec, les métriques sont extraites du
> résumé imprimé dans `logs_ablation_*.txt` + `equity_curve.csv` + `bootstrap_result.json`.

---

## Annexe — Commandes et scripts utiles

- Audit du backtest : `scripts/audit_ihm_backtest_costs.py`, `scripts/audit_ihm_final.py`,
  `scripts/cmp_entry_price.py`
- Mesure du biais pullback : `scripts/measure_pullback_bias.py`, `scripts/analyze_pullback_bias.py`
- Audit des runs corrigés : `scripts/audit_run_20260817_191418.py`, `scripts/audit_p14_atrfix.py`,
  `scripts/audit_oos2026.py`, `scripts/audit_tp_atr_check.py`
- Preuve coûts réels : `scripts/audit_spread_real_vs_fallback.py`
- Bootstrap H20 : `scripts/bootstrap_h20_dd.py` ; vérif défaut H20 : `scripts/verify_h20_default.py`,
  `scripts/verify_tp_propagation.py`
- Flag de diagnostic : `--entry-limit-offset-pct` (défaut **0.0** = exécution au marché ;
  0.01 pour reproduire les runs d'avant 2026-08-17)
- Correctifs code : propagation `take_profit_price` (`backtesting/execution_bridge.py`,
  `backtesting/execution_replay.py`) ; défaut `best_horizon` depuis config.yaml
  (`risk_management/config.py`, `ihm/services/pipeline_runner.py`, `backtesting/cli/_impl.py`)
- Rapport de robustesse global : `doc/robustesse_4tests_2026-08-17.md`
- Dossier OOS : `logs/analyse_oos.txt` (doc/ml)

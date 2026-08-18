# Synthèse — Balayage TP / risque-exécution (Point 8) — verdict NO-GO (2026-08-18)

> Branche d'investigation fermée : améliorer le moteur risk/exécution **sans toucher B25**.
> Résultat : **l'effet mécanique existe, mais l'avantage économique n'est pas suffisamment persistant** → configuration inchangée.

---

## 1. Contexte & périmètre

- **Objectif** : tester si un meilleur TP / trailing / sizing améliore le système sans modifier
  le modèle B25 (`model-factory-20260811223551-ef2cd0`), le ranking, l'Oracle, le per-symbol.
- **Fenêtre de recherche (IS)** : 2025-01-01 → 2026-05-31, coûts réels, moteur pipeline complet
  (phase2 risk_execution → phase3 execution_replay → phase4 protection → phase5 watcher → phase7 exit_lifecycle).
- **Baseline (production)** : `TP = min(ATR×4, 13 %)`, `stop = 3.5×ATR` → **29.52 %**, Sharpe 2.08,
  PF 1.52, 237 trades, DD 10.67 %, PnL +$1 165.

## 2. Découverte critique : les flags TP/stop n'étaient PAS câblés

- `--tp-atr-multiple`, `--tp-max-pct`, `--atr-risk-stop-multiple` étaient **parsés mais jamais
  appliqués** au risk config du pipeline. Le TP réel venait des maps config.yaml.
- **Fix** : `backtesting/cli/_impl.py` → helper `_risk_tp_overrides(args)` injecté dans les
  `cli_overrides` du phase2 risk config (maps par best_horizon du batch, défaut H20).
- **Validation** : relance avec flags = config (4.0/0.13/3.5) → reproduit exactement 29.52 % ✅.

## 3. Décomposition P&L baseline (237 trades, +$1 165) — l'edge est dans l'exécution

| Sortie | Trades | WR | PnL | Lecture |
|---|---|---|---|---|
| take_profit | 76 | 100 % | **+$3 212** | TOUT le profit |
| trailing_stop | 160 | 24.4 % | **−$2 058** | le drag |
| durée 5-20 j | — | — | PF ~1.8 | zone rentable |
| durée 0-5 j | — | — | PF 0.70 | perdante |
| LONG / SHORT | — | — | PF 1.85 / 1.29 | LONG > SHORT |

Hypothèse : le TP (13 %) coupait peut-être des winners trop tôt → balayage du TP.

## 4. Balayage TP — 7 configurations (B25 intact, stop 3.5×ATR)

| Run | TP | Rend. | Sharpe | PF | Trades | WR | DD | PnL |
|---|---|---|---|---|---|---|---|---|
| baseline | 4× / 13 % | 29.52 % | 2.08 | 1.52 | 237 | 48.9 % | 10.67 % | $1 165 |
| B | 3× / 10 % | 11.08 % | 0.81 | 1.14 | 298 | 46.0 % | 11.27 % | $435 |
| **C** | **5× / 16 %** | **35.97 %** | **2.70** | **1.77** | 206 | 52.4 % | **3.94 %** | **$1 306** |
| D | 3.5× / 7 % | 21.19 % | 1.50 | 1.26 | 347 | 51.9 % | 6.63 % | $831 |
| E | 6× / 20 % | 18.07 % | 1.35 | 1.26 | 215 | 44.7 % | 4.62 % | $556 |
| F | 5× / 13 % | 19.94 % | 1.44 | 1.32 | 226 | 46.5 % | 11.01 % | $720 |
| G | 4.5× / 16 % | 28.46 % | 2.14 | 1.51 | 217 | 49.3 % | 4.67 % | $1 003 |

**Lecture 2D** : relation **non monotone**. Optimum local à `min(ATR×5, 16 %)` :
- cap 16 % > 13 % à ATR×5 (C 35.97 vs F 19.94) — le cap 16 % est crucial
- ATR×5 > ATR×4.5 à cap 16 % (C 35.97 vs G 28.46)
- trop large = effondrement (E 6×/20 % → 18.07)
- sous-périodes 2025 ET 2026 H1 : C > baseline → a priori « robuste »

## 5. Analyse MFE/MAE — l'effet mécanique est RÉEL

MFE/MAE calculés depuis `stock_bars_daily` entre entrée et sortie (script
`scripts/mfe_mae_analysis.py`) :

| Métrique | Baseline | C | |
|---|---|---|---|
| MFE médian | 7.18 % | **8.02 %** | C a plus de potentiel |
| MAE médian | 4.24 % | 4.00 % | risque ≈ |
| Réalisation (final/MFE) | 12.5 % | **17.2 %** | C capture mieux |
| take_profit (MFE / réal) | 13.24 % / 90.9 % | **16.56 % / 92.2 %** | la baseline coupait à 13 % des winners à 16 %+ |
| trailing_stop (réal / WR) | −36.0 % / 25.6 % | **−10.0 % / 38.7 %** | C perd 2× moins |
| durée 10-20 j (MFE / réal / WR) | 9.07 % / 21.6 % / 63.8 % | **10.48 % / 27.6 % / 70.0 %** | cœur de l'edge |

**Conclusion mécanique** : « B25 coupe certains mouvements trop tôt » est **vrai**.
C laisse courir, capture plus, et les trailing stops perdent beaucoup moins.

## 6. Validation 2026 H1 (2026-01-01 → 2026-05-31) — C = NO-GO

A/B strict baseline vs C, même moteur, paramètre C gelé :

| Métrique | Baseline | C | Verdict |
|---|---|---|---|
| Rendement | **14.37 %** | 14.12 % | ≈ (baseline +0.25 pt) |
| Sharpe | 3.51 | **3.80** | C |
| PF | **1.76** | 1.71 | ≈ |
| Max DD | 3.04 % | **2.41 %** | C |
| PnL net | **$569** | $431 | baseline +$138 |
| Trades | 82 | 69 | — |
| SHORT PnL | **+$320** | +$117 | baseline nettement mieux |

**Verdict méthodologiquement propre** : sur la validation récente, **baseline ≈ C**, voire
baseline légèrement devant sur le PnL. L'avantage de C était concentré sur 2025 ; il ne se
**reproduit pas** sur 2026 H1. C améliore le **profil de risque** (Sharpe, DD) mais **pas le
rendement économique** hors échantillon.

## 7. Conclusion — expérience négative de valeur

> **L'effet mécanique existe, mais son avantage économique n'est pas suffisamment persistant
> pour justifier un changement de configuration.**

Leçon sur le moteur :
> **Le moteur sait exploiter les winners longs, mais le niveau optimal de TP dépend du régime
> temporel.**

- **Configuration conservée** : `TP = min(ATR×4, 13 %)`, stop 3.5×ATR, B25 baseline — rien n'est modifié.
- **Ne PAS faire** de fine-tuning autour de C (4.75/15, 5/15, 5/17, 5.25/16…) = parameter mining
  sur le même échantillon (optimisation IS → joli résultat → validation récente ≈ baseline).

## 8. Cadre des pistes (état au 2026-08-18)

**🟢 À conserver** : B25 baseline · moteur risque actuel · TP 4×/13 % · coûts réels · sélection actuelle.

**🔴 Fermées** :
- Oracle comme générateur / remplacement / filter avec réallocation
- per-symbol directional veto
- fondamentaux / sentiment comme détecteur catastrophe
- **TP C (5×/16 %) comme nouveau défaut**

**🟡 Recherche future (seulement avec OOS suffisant)** :
- Oracle **quality/sizing** (uniquement si l'analyse monotone B25∩Oracle le justifie)
- **TP adaptatif par régime** (« quand laisser courir davantage les trades ? ») — hypothèse
  différente et plus intéressante que « quel TP fixe ? »
- nouvelles features directionnelles (mais S7.1/S7.2 : la persistance historique est le blocage)

## 9. Prochain chantier prioritaire : étendre l'OOS

- **Contrainte** : `global_rank_history` pour B25 s'arrête au 2026-05-29 (backfill in-sample) ;
  la fenêtre 2026-06-01 → 07-09 est vide (seul 07-10 a un snapshot live). `rebuild-missing`
  régénère `model_predictions` mais **pas** les rangs → cascade vide → 0 trade.
- **Solution validée** : `scripts/backfill_global_rank_oos.py` → `predict_global_rank_history`
  (predictor.py:2138) backfille les rangs B25 (smoke test OK : 43 symboles sur 06-01, ~15 s/jour).

## 10. Décision de gouvernance (2026-08-18) — PARKING OOS + GEL B25

**Constat** : l'OOS récent n'est pas comparable au protocole de recherche B25 —
univers tradable instable (43 → 5 → 190), barres au 10/07, scores au 25/06. Un backtest sur
cette période répondrait à « univers accidentellement réduit ? » et non à « B25 généralise-t-il ? ».

**Décisions** :

- **Parking de l'extension OOS** : on ne force pas un OOS artificiel.
- **Gel de B25 baseline comme référence immuable** : pas de nouveau TP, fine-tuning trailing,
  filtre Oracle, directional veto per-symbol, optimisation de seuil, ni nouveau sizing.
- `backfill_global_rank_oos.py` devient **un outil de validation future** (une fois la chaîne
  de données accumulée : barres + scores + univers).
- Les runs `tp-oos-*` (invalides comme preuve OOS) sont **conservés pour traçabilité** :
  « test réalisé → données insuffisantes → résultat non interprété ».

**Règle de gouvernance (la plus importante)** :
> **Aucune nouvelle optimisation n'est acceptée sans un protocole OOS suffisamment alimenté.**

**Plan futur** : quand les données seront suffisamment accumulées, **un seul grand protocole de
validation** : B25 gelé comme baseline, chaque candidat testé **une seule fois** sur la nouvelle
période — pour éviter la boucle optimisation → sélection → re-validation sur les mêmes données.

## 11. S8 — Oracle quality/sizing : expérience positive → falsifiée (2026-08-18)

### 11.1 Contexte
Après le NO-GO du TP C, retour sur l'Oracle : tester si `oracle_edge = P_top − P_bottom` mesure
la **qualité conditionnelle des trades que B25 a déjà décidé de prendre** (et non un nouveau signal).

### 11.2 S8.1 — Monotonie oracle_edge sur trades B25 exécutés (2025-2026, 237 trades)
| Quintile | n | WR | PF | PnL |
|---|---|---|---|---|
| Q1 (edge faible) | 48 | 39.6 % | 0.76 | −$152 |
| Q2 | 47 | 38.3 % | 0.80 | −$111 |
| Q3 | 47 | 48.9 % | 2.15 | +$366 |
| Q4 | 47 | 63.8 % | 2.66 | +$566 |
| Q5 (edge élevé) | 48 | 58.3 % | 2.25 | +$496 |
- Spearman `oracle_edge` vs return : **rho = 0.174, p = 0.007** ✅
- `P_top` seul : rho 0.093 (p=0.15 NS) → c'est `oracle_edge` qui porte le signal

### 11.3 S8.2 — Contrôle des confounders (POSITIF)
- Corrélation partielle après contrôle global_rank + score B25 + ATR : **rho = 0.162, p = 0.013**
- OLS (rangs) : `oracle_edge` **seule variable significative** (p=0.013) ; global_rank_20 p=0.72 NS,
  score B25 p=0.16 NS, ATR p=0.65 NS
- Double tri GR×edge : discrimine dans les deux moitiés de global_rank
- → le signal n'est pas un artefact du rank / score / ATR

### 11.4 S8.2b — Stabilité temporelle : le test de falsification (583 trades, 5 périodes)
| Période | n | rho | p | PF bas (Q1-Q2) | PF haut (Q3-Q5) |
|---|---|---|---|---|---|
| 2022 | 187 | +0.002 | 0.98 | 1.05 | 1.07 |
| 2023 H1 | 85 | +0.065 | 0.55 | 0.70 | 1.24 |
| 2024 H1 | 74 | +0.008 | 0.94 | 0.99 | 0.88 |
| **2025** | 165 | **+0.181** | **0.02** | 0.86 | 2.50 |
| 2026 H1 | 72 | +0.159 | 0.18 | 0.85 | 1.71 |
| **Total** | **583** | **+0.020** | **0.64** | 0.79 | 1.13 |
- La relation n'existe **que sur 2025** ; 2022 / 2024 H1 : rho ≈ 0 ; **consolidé 583 trades nul**
- → probablement une interaction avec le régime / la distribution de 2025, pas une propriété stable

### 11.5 Verdict S8
- **Invalidé** : Oracle comme sizing / filtre / générateur / reranking / quality score permanent.
- **Démontré** : l'Oracle détecte des situations particulières sur certaines périodes, mais n'a
  **pas de relation temporelle stable** → ne peut pas être une feature de production.
- C'est un **faux positif attrapé par le filtre de persistance** (2ᵉ après TP C).

### 11.6 Règle formelle de gouvernance du projet α-Trade
> **Une amélioration ne peut pas être promue simplement parce qu'elle améliore le backtest global.
> Elle doit démontrer une relation stable sur plusieurs périodes temporelles indépendantes de la
> période ayant servi à la découvrir.**

Séquence obligatoire : **1) découverte → 2) validation temporelle → 3) validation OOS → 4) production.**

### 11.7 Faux positifs évités par ce filtre
| Candidat | Fenêtre de découverte | Résultat | Verdict |
|---|---|---|---|
| TP C (5× ATR / 16 %) | IS 2025-2026 | pas supérieur sur 2026 H1 | NO-GO |
| Oracle `oracle_edge` | 2025-2026 | rho consolidé 0.02 (p=0.64) | NO-GO |

C'est le mécanisme qui empêche progressivement le système de devenir un monstre de sur-optimisation.

---
*Références : runs `tp-sweep-{b,c,d,e,f,g}`, `tp-sweep-ref`, `tp-val-2026h1-{baseline,c}`,
`s8-ext-{2022,2023h1,2024h1}`, scripts `backfill_global_rank_oos.py`, `mfe_mae_analysis.py`,
`s8_oracle_monotonicity.py`, `s8_confound_control.py`, `s8_temporal_stability(_full).py`,
mémoire `/memories/session/tp_sweep_state.md`, `/memories/session/s8_oracle_quality_sizing.md`.*

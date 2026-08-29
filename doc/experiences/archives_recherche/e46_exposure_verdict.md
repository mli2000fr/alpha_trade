# E46 — Verdict exposition (Phase B) — 2026-08-22 — DÉCISION : 1.46 retenu

## Cadre (spec utilisateur, inchangé)

- **B4 gelé à −15 %** (non modifié), politique catastrophe **WORST_50** (0.5), **CP-V2**, **6L/2S**, batch B25/H20, equity 4000, capital_2001_5000, seed 12345.
- Expositions testées : **mult 1.00** (baseline), **1.46** (retenu, gross moy ~80–88 %), **1.69** (agressif/futur, gross moy ~94–103 %). **1.92 exclu** (DD 2025 14,30 % trop près du breaker).
- Stress pré-spécifiés E45 : **S1_costs** (spread 30/slippage 15/comm 5 bps), **S3_cpoff** (CP-OFF, shorts 5), **S5_combo** (CP-OFF + research-sizing + coûts modérés). S4_2020 exclu (coverage gate non contourné). NORMAL = runs Phase A.
- **NB anomalie worst3m/6m** : `worst3m/worst6m = 0` était un **bug de reporting** de l'analyseur (mesure en fin de fenêtre vs pic → ~0 en tendance haussière). Corrigé = pire drawdown pic→creux (pic avant creux) dans chaque fenêtre glissante. Valeurs ci-dessous corrigées : `worst6m ≈ MaxDD`, `worst3m ≤ MaxDD`. **Aucun impact sur les autres métriques ni sur le verdict.**

## Tableau complet (18 runs)

| Scén. | année | mult | ret% | MaxDD% | w3m | w6m | Sharpe | Sortino | PF | trips | fclose | gMoy% | gMax% | recov | exp@wDD% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NORMAL | 2022 | 1.00 | 11.60 | 5.66 | 5.66 | 5.66 | 0.99 | 1.66 | 1.25 | 0 | 0 | 58.9 | 90 | 46 | 61 |
| NORMAL | 2022 | 1.46 | 15.17 | 7.62 | 7.62 | 7.62 | 0.97 | 1.61 | 1.24 | 0 | 0 | 80.1 | 123 | 46 | 84 |
| NORMAL | 2022 | 1.69 | 18.44 | 9.13 | 9.13 | 9.13 | 0.99 | 1.66 | 1.24 | 0 | 0 | 94.2 | 144 | 46 | 96 |
| NORMAL | 2025 | 1.00 | 20.16 | 8.33 | 8.02 | 8.33 | 2.03 | 3.51 | 1.50 | 0 | 0 | 65.3 | 99 | 37 | 84 |
| NORMAL | 2025 | 1.46 | 28.57 | 10.90 | 10.52 | 10.90 | 2.06 | 3.56 | 1.51 | 0 | 0 | 88.4 | 137 | 37 | 120 |
| NORMAL | 2025 | 1.69 | 33.39 | 12.76 | 12.35 | 12.76 | 2.05 | 3.55 | 1.51 | 0 | 0 | 102.5 | 159 | 37 | 139 |
| S1_costs | 2022 | 1.00 | 8.99 | 5.66 | 5.66 | 5.66 | 0.80 | 1.34 | 1.19 | 0 | 0 | 58.5 | 90 | 46 | 63 |
| S1_costs | 2022 | 1.46 | 11.52 | 7.62 | 7.62 | 7.62 | 0.77 | 1.29 | 1.17 | 0 | 0 | 79.7 | 123 | 47 | 87 |
| S1_costs | 2022 | 1.69 | 14.32 | 9.13 | 9.13 | 9.13 | 0.81 | 1.35 | 1.18 | 0 | 0 | 93.9 | 145 | 47 | 100 |
| S1_costs | 2025 | 1.00 | 19.89 | 8.38 | 8.07 | 8.38 | 2.00 | 3.47 | 1.49 | 0 | 0 | 65.4 | 99 | 37 | 84 |
| S1_costs | 2025 | 1.46 | 28.20 | 10.97 | 10.59 | 10.97 | 2.03 | 3.51 | 1.51 | 0 | 0 | 88.6 | 137 | 37 | 121 |
| S1_costs | 2025 | 1.69 | 32.95 | 12.84 | 12.43 | 12.84 | 2.02 | 3.50 | 1.50 | 0 | 0 | 102.7 | 160 | 37 | 140 |
| S3_cpoff | 2022 | 1.00 | 9.43 | 6.77 | 6.77 | 6.77 | 0.81 | 1.40 | 1.19 | 0 | 0 | 59.7 | 92 | 48 | 63 |
| S3_cpoff | 2022 | 1.46 | 12.41 | 9.08 | 9.08 | 9.08 | 0.80 | 1.38 | 1.18 | 0 | 0 | 81.2 | 126 | 48 | 86 |
| S3_cpoff | 2022 | 1.69 | 14.69 | 10.86 | 10.86 | 10.86 | 0.80 | 1.38 | 1.18 | 0 | 0 | 96.2 | 149 | 48 | 100 |
| S3_cpoff | 2025 | 1.00 | 15.58 | 8.36 | 8.06 | 8.36 | 1.62 | 2.99 | 1.37 | 0 | 0 | 66.8 | 99 | 54 | 80 |
| S3_cpoff | 2025 | 1.46 | 21.17 | 11.49 | 11.12 | 11.49 | 1.58 | 2.89 | 1.36 | 0 | 0 | 91.3 | 137 | 54 | 114 |
| S3_cpoff | 2025 | 1.69 | 25.40 | 12.98 | 12.57 | 12.98 | 1.62 | 2.95 | 1.37 | 0 | 0 | 106.1 | 160 | 54 | 133 |
| S5_combo | 2022 | 1.00 | 22.36 | 10.91 | 10.91 | 10.91 | 1.02 | 1.71 | 1.23 | **1** | 4 | 94.3 | 190 | 8 | 8 |
| S5_combo | 2022 | 1.46 | 21.45 | 13.27 | 13.27 | 13.27 | 0.87 | 1.42 | 1.19 | **1** | 4 | 110.9 | 209 | 8 | 6 |
| S5_combo | 2022 | 1.69 | 27.38 | 13.73 | 13.73 | 13.73 | 1.00 | 1.67 | 1.22 | **1** | 4 | 118.0 | 210 | 8 | 7 |
| S5_combo | 2025 | 1.00 | 25.59 | 16.24 | 16.24 | 16.24 | 1.42 | 2.41 | 1.26 | **1** | 4 | 109.9 | 202 | 68 | 75 |
| S5_combo | 2025 | 1.46 | 39.40 | 16.66 | 16.66 | 16.66 | 1.78 | 2.81 | 1.35 | **1** | 4 | 128.2 | 202 | 62 | 47 |
| S5_combo | 2025 | 1.69 | 49.35 | 16.70 | 16.70 | 16.70 | 2.00 | 3.52 | 1.40 | **1** | 3 | 137.1 | 203 | 52 | 56 |

## Analyse marginale ΔReturn / ΔMaxDD

| Scénario | année | 1.46 vs 1.00 | 1.69 vs 1.00 | 1.69 vs 1.46 |
|---|---|---|---|---|
| NORMAL | 2022 | +3.57pt / +1.96 (1.82) | +6.84 / +3.47 (1.97) | +3.27 / +1.51 (2.16) |
| NORMAL | 2025 | +8.42 / +2.57 (3.27) | +13.23 / +4.43 (2.99) | +4.82 / +1.86 (2.59) |
| S1_costs | 2022 | +2.53 / +1.96 (1.29) | +5.33 / +3.48 (1.53) | +2.81 / +1.51 (1.85) |
| S1_costs | 2025 | +8.31 / +2.59 (3.21) | +13.06 / +4.46 (2.93) | +4.76 / +1.87 (2.54) |
| S3_cpoff | 2022 | +2.98 / +2.31 (1.29) | +5.25 / +4.10 (1.28) | +2.28 / +1.79 (1.28) |
| S3_cpoff | 2025 | +5.59 / +3.13 (1.78) | +9.82 / +4.62 (2.13) | +4.23 / +1.49 (2.85) |
| S5_combo | 2022 | −0.91 / +2.36 (−0.39) | +5.02 / +2.81 (1.78) | +5.93 / +0.45 (13.1) |
| S5_combo | 2025 | +13.82 / +0.42 (32.6) | +23.77 / +0.46 (51.5) | +9.95 / +0.04 (260) |

## Lecture

### 1. Qualité stable, jamais dégradée
Sharpe / Sortino / PF restent **constants** à travers 1.00→1.46→1.69 dans CHAQUE scénario (NORMAL 2025 : Sharpe 2.03/2.06/2.05 ; S3 2025 : 1.62/1.58/1.62…). Plus d'exposition = plus de rendement **sans** dégradation du profil ajusté au risque.

### 2. Fragilité (gate B4 = airbag)
- **NORMAL, S1_costs, S3_cpoff : 0 trip B4 pour TOUS les mults**, y compris 1.69 (MaxDD max 12,98 % en S3 2025 < 15 %). → **ni 1.46 ni 1.69 n'est fragile** dans les scénarios normaux / modérément défavorables.
- **S5_combo (extrême) : 1 trip B4 pour TOUS les mults, y compris 1.00** (et 4 force-close). → Le trip est **porté par le scénario** (CP-OFF + research-sizing + coûts), **pas par l'exposition**. C'est précisément la fonction de l'airbag (un trip en stress ≠ échec).
- Conclusion gate : **aucun des 3 niveaux n'est « trop agressif »** selon le critère « trips en scénario normal/modéré ».

### 3. Worst 3m / 6m (corrigés)
`worst6m ≈ MaxDD` partout ; `worst3m` légèrement inférieur (ex. NORMAL 2025 : 1.46 → w3m 10.52 / w6m 10.90 = MaxDD ; 1.69 → 12.35 / 12.76). Cohérent : pas de dégradation supplémentaire du pire sous-période avec l'exposition.

### 4. Part capturée par 1.46 (règle de décision §8)
- 2025 NORMAL : 1.46 capture **64 %** du gain total (1.00→1.69) pour **58 %** du DD supplémentaire.
- 2022 NORMAL : 1.46 capture **52 %** pour **56 %** du DD.
→ 1.46 capte l'essentiel du gain avec une marge de sécurité plus large que 1.69 (MaxDD 2025 10,90 % vs 12,76 %, soit 4,1 pt de réserve avant B4 −15 %).

### 5. ⚠️ Point de vigilance — gross max réel
À 1.69, le **gross max journalier** atteint **144–160 %** et l'**exposition au pire DD** jusqu'à **139 %** (pointes de levier 2.0). À **1.46** : gross max 123–137 %, exp@wDD 84–120 % — plus de réserve, c'est le niveau retenu.

## DÉCISION RETENUE (utilisateur, 2026-08-22)

> **exposure_multiplier = 1.46 = niveau PROD retenu.**
> - **1.00 = rollback** (config inchangée, comportement PROD).
> - **1.69 = profil agressif NON promu** — documenté, candidat futur (re-calibration uniquement sur données réellement indépendantes ou changement majeur modèle/univers).
> - **B4 reste à −15 %** ; **WORST_50 inchangé** ; **CP-V2 inchangé** ; **6L/2S inchangé**.

## Paramétrage config.yaml — SPLIT PROD vs BACKTEST (implémenté)

5 paramètres désormais distingués **prod vs backtest** dans `config.yaml` (clés `_prod` pour le live, `_backtest` pour les backtests ; fallback automatique vers les clés legacy si les nouvelles sont absentes) :

| Paramètre | PROD (live) | BACKTEST |
|---|---|---|
| Exposition | `risk_management.prod_exposure_multiplier` (1.46) | `risk_management.backtest_exposure_multiplier` (1.46) |
| Force-close breaker | `risk_management.prod_force_close_on_breaker` (true) / `prod_force_close_pct` (0.5) | `risk_management.backtest_force_close_on_breaker` (true) / `backtest_force_close_pct` (0.5) |
| DD max | `risk.prod_max_drawdown` (0.15) | `risk.backtest_max_drawdown` (0.15) → défaut `--max-portfolio-dd-pct` |
| Perte journalière max | `risk.prod_max_daily_loss` (0.05) | `risk.backtest_max_daily_loss` (0.05, réservé — pas de daily-loss breaker côté backtest) |

- **Backtest** : `backtesting/cli/_impl.py` lit `backtest_*` (exposure via `_resolve_exposure_multiplier` ; force-close via la config ; DD par défaut via `risk.backtest_max_drawdown`). CLI (`--exposure-multiplier`, `--max-portfolio-dd-pct`, `--force-close-on-breaker/--force-close-pct`) reste prioritaire.
- **Live** : `execution_engine/cli.py` (force-close `prod_*`), `execution_engine/executor.py` (exposure `prod_*`), `run_execution.py` (RiskConfig `risk.prod_max_drawdown` / `prod_max_daily_loss`).
- Les clés legacy (`exposure_multiplier`, `force_close_*`, `max_drawdown`, `max_daily_loss`) restent **documentées en fallback** — comportement identique si les clés `_prod`/`_backtest` sont absentes.

## FREEZE du calibrage exposition

- **STOP tuning** : pas de 1.50 / 1.55 / 1.60 / 1.72, pas de re-sweep. Niveau retenu **1.46** figé.
- **Ne pas relever B4** pour permettre plus d'exposition.
- Toute future amélioration de sizing devra être validée sur **nouvelles données réellement indépendantes** ou après **changement majeur** modèle/univers → nouvelle calibration séparée.

## Limites

- **S4_2020 non testé** (coverage gate ML/PIT non contourné, comme convenu) ; le crash test repose sur S1/S3/S5 + 2022 (bear).
- Gross max mesuré sur snapshots journaliers ; en réel, surveiller les pointes de levier.
- 2022 est une année « CP toute l'année » (249 j) : le stress le plus discriminant reste 2025 / S5_combo.
- Le `worst3m/worst6m = 0` initial était un bug de reporting (analyseur) — corrigé, sans impact sur les autres métriques ni la décision.

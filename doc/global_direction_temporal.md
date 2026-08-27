# GlobalDirectionTemporal — Hypothèse temporelle (J-5/J-10) — 2026-08-26

## Hypothèse

Les features statiques à J portent presque pas de direction ; leur **trajectoire
sur les 5-10 jours précédents** pourrait distinguer futurs mauvais longs (D1-D5)
des bons longs (D6-D10).

Protocole : **même pipeline GlobalDirection** (H20, target `rank`, walk-forward
PIT, LightGBM) — seul le jeu de features change. **Diagnostic de séparabilité
AVANT entraînement** (pas de nouveau modèle, pas de LSTM).

## Module

`modelFactory/global_direction/temporal.py` :
- 12 features de base (petit groupe) → dérivées temporelles intra-symbole
  strictes J..J-10 : `t0, lag_1/3/5/10, delta_1/3/5/10, mean_3/5/10,
  slope_3/5/10, std_5/10, pos_frac_5/10, sign_change_5`.
- Sources PIT : 8 features de score (`stock_scores_history`, merge_asof backward
  + `snapshot_age_days`) ; `momentum_20/60` (bars adj_close) ;
  `stock_vs_sector_ret_20/60` (moteur sectoriel).
- Séparabilité : IC décile, AUC(D1-D5 vs D6-D10), AUC(D1-D3 vs D8-D10),
  AUC(D1 vs D10), `dir_vs_amp`, stabilité par fold, coverage ; **comparaison
  static vs temporal** (`delta_auc`).

## Audit de couverture `stock_scores_history` (2026-08-26) — INSUFFISANT

`modelFactory/global_direction/audit_scores.py` → `artifacts/audit_scores_coverage.csv`.
Mesures sur jours de MARCHÉ réels (calendrier `stock_bars_daily` par symbole),
univers pool (194 symboles), 2020-2026.

### Snapshots par symbole / année
| Année | Symboles | Snapshots/symb (méd) | Snap le jour même | Gap max (j.t.) |
|---|---|---|---|---|
| 2020 | 162 | 23 | 9.1 % | 439 |
| 2021 | 189 | 27 | 9.9 % | 405 |
| **2022** | 191 | **0** ❌ | **0 %** | 402 |
| **2023** | 193 | **3** | 1.2 % | 397 |
| 2024 | 193 | 19 | 7.5 % | 397 |
| 2025 | 193 | 39 | 14.8 % | 397 |
| 2026 | 193 | 3 | 2.9 % | 397 |

### Dans le pool Oracle TOP20% (NB : le pool ne couvre que 2022-2024)
- Couverture lags (jours de marché réels) : J=78.2 % · J-1=78.2 % · J-3=78.1 %
  · J-5=78.0 % · J-10=77.8 % — **quasi plat** (le forward-fill couvre tout ou
  rien).
- **Âge du snapshot PIT à J : médiane 157 j.t. · p90 508 j.t. · max 1081 j.t.**
  → le score à J a en moyenne ~157 jours de trading.
- Par année : 2022=70 % · 2023=76 % · 2024=87 %.

### Verdict audit : couverture INSUFFISANTE pour l'hypothèse temporelle
- **2022 (1ère année du pool) : 0 snapshot/symbole en médiane.**
- L'âge médian du snapshot (157 j.t.) est **> 15× la fenêtre J-10** : la
  trajectoire J-1..J-10 est un point quasi constant (forward-fill) → les
  variations (delta/slope/mean) sont plates et **non mesurables**.
- La couverture « 78 % » est trompeuse : un snapshot PIT existe, mais vieux.
- → **NE PAS re-tester le temporal sur `stock_scores_history`** (conforme à la
  consigne). Le temporal n'est testable que sur les séries quotidiennes
  (momentum/secteur, couverture 95-100 %, âge 0) — déjà testé → NO-GO.

## Construire la couverture via le backfill PIT (2026-08-27) — résultat inchangé

Pour dépasser la sparsité, backfill PIT officiel `backtesting.cli backfill-scores-history`
(pool 194 symboles, 2022-2024, 769 séances) :
- **Pilotes OK** (2024 + 2022) : snapshots quotidiens, **les 8 features
  prioritaires à 100 % renseignées**, ~6-8 s/séance.
- **Limite structurelle** : le backfill ne persiste QUE les **candidats du
  selector** (~26 lignes/jour), pas les 194 symboles du pool ; en 2022-2023 les
  **quotes PIT manquent** (`stock_quote_snapshots` non collectées) → le selector
  ne peut pas scorer → 4-5 lignes/jour. 2024 exploitable (24/jour, 147 symboles,
  médiane 39 j/symbole, gap médian 1 jour).
- **Ré-run de la séparabilité temporelle avec les données backfillées :
  RÉSULTAT IDENTIQUE** — 0 GO / 144 coverage_insuffisante / 108 NO-GO ; couverture
  pool ~49 % (les candidats sont un sous-ensemble du pool) ; AUC temporelles
  inchangées (`company_idio_score__lag_10` 0.510, `RSI_neutralized__lag_10` 0.526…).
- **Restauration** : le `--overwrite-existing` avait remplacé 19 469 lignes
  existantes par 8 679 (moins denses) → restauré depuis
  `artifacts/backup_ssh_cap2001_2022_2024.parquet`.

**Leçon** : le backfill officiel ne donne pas de couverture plein-pool. Pour les
features de prix (`RSI_neutralized`, `trend_score`, `weekly_trend_score`), une
vraie couverture quotidienne exigerait de les recalculer depuis les bars (le
screener le fait, mais ses sorties ne sont pas persistées pour les non-candidats).
Le verdict temporel global reste **NO-GO**.

## Résultats — TOP 20 % ET TOP 10 % (2 runs)

**0 GO · 0 candidat · 108 NO-GO · 144 coverage_insuffisante** (identique aux 2
profondeurs de pool).

### Statiques à J
| Feature | TOP20 AUC | TOP10 AUC | Coverage |
|---|---|---|---|
| `relative_strength_index_neutralized` | 0.526 | **0.542** | 0.49 / 0.39 ❌ |
| `sentiment_net_agg` (≈ idio) | 0.499 | 0.512 | 0.49 / 0.39 ❌ |
| `trend_score` | 0.506 | 0.506 | ❌ |
| `momentum_20/60`, `stock_vs_sector_ret_20/60` | 0.47-0.49 | 0.47-0.49 | ✓ |

### Meilleures dérivées temporelles (par base)
| Feature | TOP20 AUC | TOP10 AUC | Verdict |
|---|---|---|---|
| `relative_strength_index_neutralized__lag_10 / mean_10` | 0.530 | 0.543 | coverage_insuffisante |
| `momentum_60__sign_change_5` | 0.506 | **0.508 (3/3 folds)** | NO-GO |
| `stock_vs_sector_ret_60__sign_change_5` | 0.510 | 0.504 | NO-GO |
| `company_idio_score__lag_10` | 0.506 | 0.519 | coverage_insuffisante |

## VERDICT : NO-GO

- **Aucune feature temporelle n'atteint AUC ≥ 0.53 avec signe stable** (seuil
  « intéressant » : 0.54-0.56). La dynamique J-5/J-10 **n'ajoute pas de
  direction** au-delà de la valeur statique à J.
- Le seul motif un peu moins bruité : `sign_change_5` (volatilité directionnelle
  récente) sur momentum/secteur, **stable 2-3/3 folds** mais AUC ≈ 0.50-0.51.
- Les 8 features de score sont **non testables** : sparsité de
  `stock_scores_history` (2022 = 0 snapshot/symbole en médiane) et **âge médian
  du snapshot à J = 157 j.t.** → la fenêtre J-5/J-10 est un point quasi constant,
  les dérivées temporelles sont plates (delta ≤ +0.007). Ce n'est pas « pas de
  signal », c'est « donnée trop clairsemée pour mesurer une trajectoire ».

## Conclusion (étape 8 non atteinte)

Pas d'entraînement `GlobalDirectionTemporal` : la condition « plusieurs features
temporelles avec signal directionnel OOS stable » n'est pas remplie. L'hypothèse
« la trajectoire porte la direction absente des statiques » est **non soutenue**
par les données disponibles — et **non testable** pour les features de score
(couverture insuffisante, audit ci-dessus).

Évidences : `artifacts/global_direction_temporal_separability.csv` (TOP20),
`global_direction_temporal_separability_top10.csv` (TOP10) et
`artifacts/audit_scores_coverage.csv`.

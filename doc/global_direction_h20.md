# GlobalDirection H20 — Recherche anti-D1

> Module de recherche (2026-08-26) : séparer les futurs **D10** (bon long) des
> futurs **D1** (mauvais long) dans l'univers Extreme, **sans prédire l'amplitude**.

## Objectif

Le modèle Oracle Extreme (`proba_extreme`) est **agnostique à la direction** :
~23% des picks top 10% finissent en D1 (bottom 10% réalisé, retour moyen −19%).
`GlobalDirection` apprend un **score directionnel** `direction_score = P(D10 | D1∨D10)`
pour classer les candidats extrêmes : Oracle = **gate** (univers), GlobalDirection
= **ranking** (sélection LONG).

## Pipeline de test

```
1. direction_score pour TOUT l'univers (walk-forward OOS)
2. proba_extreme (Oracle) indépendant
3. garder Oracle TOP 20% du jour (gate)
4. dans le pool, classer par direction_score décroissant
5. conserver le TOP m24
6. LONG uniquement
```

Pas de seuil sur `direction_score` au premier test. `proba_extreme` n'est **pas**
une feature (premier test).

**Comparaison :**
- **A** = Oracle pur (pool → top m24 par `proba_extreme`)
- **B** = Oracle + B25 (pool → top m24 par `global_rank_20`)
- **C** = Oracle + GlobalDirection (pool → top m24 par `direction_score`)

## Labels

Depuis `global_oracle_labels` (`oracle_decile`, H20) — deux cibles (`--target-mode`) :

| mode | D1 | D2-D9 (middle) | D10 | usage |
|---|---|---|---|---|
| `binary` (défaut) | 0 | NaN | 1 | entraîne sur D1/D10 ; **scorer TOUT l'univers** (D2-D9 exclus du training, conservés à l'inférence) |
| `ordinal` (V1b) | 0 | 1 | 2 | **toutes les lignes entraînées** — le modèle connaît le milieu qu'il rencontre à l'inférence |

`direction_score = P(D10)` dans les deux cas.

## Features

Modes configurables (`--feature-mode`) :

| mode | contenu | nb |
|---|---|---|
| `minimal` | momentum/trend absolu + 3 xs_rank (1er test) | 25 |
| `directional` | famille momentum/trend absolu | 31 |
| `directional+xs` | + force relative cross-sectionnelle | 45 |
| `sector` | minimal + famille sectorielle (V2) | 33 |
| `complete` | directional+xs + famille sectorielle (V3) | 53 |
| `all` | expert + xs (fallback, non recommandé) | 129+ |

La **famille sectorielle** (`stock_vs_sector_ret_20/60/5`, `sector_ret_20/60/5`,
`sector_relative_strength_20`, `momentum_20_sector_neutral`) est calculée par le
moteur cross-sectionnel (`modelFactory/cross_sectional.py`, `DIRECTIONAL_FEATURES`),
le même que le Global Ranking avec `--include-directional-features`.

Exclues du 1er test : `rolling_volatility_*`, `atr_*`, `intraday_range` (éviter
d'apprendre « gros mouvement » au lieu du « bon côté »).

## Comparaison (baselines)

- **A** = Oracle pur (pool → top m24 par `proba_extreme`)
- **B0** = Oracle + ranking B25 **H10** (baseline réelle, `global_rank_10`)
- **B1** = Oracle + `global_rank_20` (contrôle H20)
- **C** = Oracle + GlobalDirection (pool → top m24 par `direction_score`)

## Diagnostics obligatoires

- Table par **quintile de `direction_score`** (dans le pool Oracle) :
  `n · D1% · Middle% · D10% · GOOD/BAD (=D10/D1) · mean · med · P(>0)`
- **GO pré-enregistré par fold** : Q5 doit présenter **simultanément** D1 ↓,
  D10 ↑ et GOOD/BAD ↑ vs Q1 — reproductible sur la majorité des folds.
- mean / median / P(return>0) / coverage / n ; par fold WF, par semestre, par
  régime (`regime_marche/regime.ttx`).

**Critère principal :** gradient stable — `direction_score ↑ ⇒ D10 ↑ ET D1 ↓`.
Ne PAS sélectionner le modèle sur le seul PnL du backtest.

## Usage

```bash
# 1. Entraîner + OOS (univers entier)
python -m modelFactory.global_direction.walk_forward --feature-mode minimal            # binaire (défaut)
python -m modelFactory.global_direction.walk_forward --feature-mode minimal --target-mode ordinal  # V1b

# 2. Pipeline A/B0/B1/C + diagnostics
python -m modelFactory.global_direction.pipeline --batch-id model-factory-... --gd-run global-direction-wf-...
```

Artefacts : `artifacts/models/global_direction/<run_id>/oos_predictions.parquet`
(+ `batch_id.txt` sidecar).

## Anti-leakage

- PIT strict, walk-forward causal identique à l'Oracle (fold `oracle_available_date < test_start`).
- `proba_extreme`, `global_rank_*` et toute colonne `future_*`/`oracle_*` bannis des features (assertions bloquantes T3/T4).
- `direction_score` calculé à la date D avec les données de D uniquement.

## Étape suivante

- **Ordinal (V1b)** : run `--target-mode ordinal` en cours — le modèle connaît le
  milieu (D2-D9). Comparer le gradient par quintile avec le binaire.
- **V2 sectorielle** : entraîner les modes `sector` / `complete`.
- **Conditionnel Oracle OOF (GD-B/GD-C)** : entraîner uniquement sur le pool
  Oracle TOP20 (proba_extreme OOS PIT à J, ABSENT des features — sert seulement
  de training universe). ⚠️ L'Oracle OOS ne couvre que 2022+ → le 1er fold
  (train 2020-2021) serait vide en mode conditionnel ; à évaluer.

### Étude de séparabilité (étapes 7-8) — 2026-08-26

`modelFactory/global_direction/separability.py` → `artifacts/global_direction_separability.csv`.
182 features analysées **dans le pool Oracle TOP20% uniquement**.

**Résultat : la direction n'est PAS observable avec les features actuelles.**

- max `IC_décile` = **0.033** (meanrev_signal_xs_rank) — aucun IC > 0.05.
- max `AUC_direction` (D6-D10 vs D1-D5) = **0.515** — **0 feature > 0.53**, tout est ≈ bruit.
- Les meilleures (meanrev_signal, distance_high_20, ema20_minus_sma20) ont un signe
  stable par fold mais AUC ~0.51 (bruit).
- Piège confirmé : `rolling_volatility_*`, `atr_*`, `intraday_range` ont une forte
  `AUC_amplitude` (0.55-0.57, extrême vs milieu) mais `dir_vs_amp` **négatif**
  (−0.06 à −0.09) → elles feraient réapprendre Oracle Extreme (amplitude) à
  GlobalDirection, pas la direction.

**Conclusion (étape 9) : direction non suffisamment observable avec l'information
actuelle à J.** Ne pas chercher à la créer avec des pénalités/loss. → Ouvrir une
branche **données** : estimate/earnings revisions, news sentiment, options skew /
implied vol asymétrie, short interest, insider, analyst upgrades, breadth
sectorielle, volume directionnel, gap/premarket (si PIT).

## Critère GO pré-enregistré (étape 5) — C4 vs B1 (sélections top 24)

Distribution complète des sélections (BAD5/GOOD5/VERY_BAD/VERY_GOOD) :

| Variante | BAD5 | GOOD5 | VERY_BAD | VERY_GOOD | mean |
|---|---|---|---|---|---|
| A Oracle pur | 50.2 | 49.8 | 193.8 | 194.4 | +2.82% |
| B0 Oracle+B25 H10 | 47.5 | 52.5 | 173.9 | 199.1 | +3.05% |
| **B1 Oracle+B25 H20** | **46.9** | **53.1** | **171.1** | **201.1** | **+3.36%** |
| C3 rank minimal | 49.8 | 50.2 | 179.2 | 185.7 | +2.08% |
| C4 rank sector | 50.1 | 49.9 | 181.2 | 184.5 | +1.98% |

GO C4 vs B1 (BAD5↓, GOOD5↑, VERY_BAD↓, VERY_GOOD↑, mean↑) : **échec sur les 5
critères** — C4 a BAD5 plus haut (50.1 vs 46.9), GOOD5 plus bas (49.9 vs 53.1),
VERY_BAD plus haut, VERY_GOOD plus bas, mean plus bas. C3 aussi échoue.
**Le GO n'est pas atteint ; les features sectorielles n'aident pas.**

### Test sectoriel (V2 : minimal + famille sectorielle, cible rank) — 2026-08-26

Run `global-direction-wf-20260826200124` :

| Variante | D1% | Mid% | D10% | GOOD/BAD | mean | GO/fold |
|---|---|---|---|---|---|---|
| A Oracle pur | 24.5% | 50.2% | 25.3% | 1.03 | +2.82% | — |
| B0 Oracle+B25 H10 | 19.8% | 56.0% | 24.2% | 1.22 | +3.05% | — |
| B1 Oracle+B25 H20 | 19.6% | 56.0% | 24.4% | 1.25 | +3.36% | — |
| C3 rank minimal | 18.9% | 59.9% | 21.2% | 1.12 | +2.08% | 2/3 |
| C3 rank **sector** | 19.9% | 59.0% | 21.1% | 1.06 | +1.98% | **3/3** |

Les features sectorielles **n'améliorent pas** le classement : C3_sector ≈ ou légèrement
< C3_minimal sur D1/D10/GOOD/BAD/mean. Le gradient poolé reste non monotone
(malgré un GO simple Q5-vs-Q1 3/3 par fold).

**VERDICT FINAL : NO-GO.** Avec features minimales OU sectorielles, aucune cible
(binaire/ordinal/rank) ne bat la baseline B25 (H10/H20) dans le pool Oracle.
B25 momentum = meilleur rang LONG du pool. L'anti-D1 doit passer par
sizing/exposition (plafond omniscient +2.48%→+8.94%), pas par un nouveau rang.
→ suite : **étude de séparabilité** feature-par-feature (étapes 7-8).

## Résultats intermédiaires (pool Oracle top20%, TOP 24, features `minimal`)

### C1 binaire / C2 ordinal / C3 rank (2026-08-26)

| Variante | D1% | Mid% | D10% | GOOD/BAD | mean | GO/fold |
|---|---|---|---|---|---|---|
| A Oracle pur | 24.5% | 50.2% | 25.3% | 1.03 | +2.82% | — |
| B0 Oracle+B25 H10 | 19.8% | 56.0% | 24.2% | 1.22 | +3.05% | — |
| B1 Oracle+B25 H20 | 19.6% | 56.0% | 24.4% | 1.25 | +3.36% | — |
| C1 GD binaire | 18.4% | 59.8% | 21.8% | 1.18 | +2.15% | 2/3 |
| C2 GD ordinal 3cl | 21.2% | 55.8% | 23.0% | 1.08 | +2.38% | **0/3** |
| C3 GD rank | 18.9% | 59.9% | 21.2% | 1.12 | +2.08% | 2/3 |

- C2 ordinal : gradient INVERSÉ sur D1 (Q1 18.5 → Q5 21.8) — le haut du score
  concentre D1 ET D10 (extrêmes), pas les bons longs. Pire pour le GO.
- C1/C3 : D1 ↓ mais D10 non monotone ; mean < B0/B1. GO 2/3 (non reproductible).

**Verdict intermédiaire : NO-GO.** Avec 25 features directionnelles, GlobalDirection
(binaire/ordinal/rank) ne bat pas la baseline B25 (H10/H20) sur le critère pré-
enregistré. B25 momentum reste le meilleur rang LONG dans le pool Oracle.

**Prochaines pistes** : features **sectorielles** (V2 `sector`/`complete` — l'hypothèse
GPT), entraînement **conditionnel Oracle-OOF** (GD-B/GD-C), ou accepter B25 comme
rang LONG et concentrer l'anti-D1 ailleurs (sizing/exposition).

### V1 binaire seul (2026-08-26, premier run)

Run `global-direction-wf-20260826175019`, pool Oracle top20%, TOP 24 :

| Variante | D1% | Mid% | D10% | GOOD/BAD | mean |
|---|---|---|---|---|---|
| A Oracle pur | 24.5% | 50.2% | 25.3% | 1.03 | +2.82% |
| B0 Oracle+B25 H10 | 19.8% | 56.0% | 24.2% | 1.22 | +3.05% |
| B1 Oracle+B25 H20 | 19.6% | 56.0% | 24.4% | 1.25 | +3.36% |
| C Oracle+GD | 18.4% | 59.8% | 21.8% | 1.18 | +2.15% |

Gradient des quintiles : D1 ↓ (21.3→18.1) **OUI** ; D10 non monotone (Q2 dip)
**NON** ; GOOD/BAD non monotone **NON**. GO pré-enregistré : **2/3 folds**.

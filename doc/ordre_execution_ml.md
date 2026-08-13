# Ordre d'exécution ML — Calibration & Validation

> **Date** : 2026-08-13
> **Contexte** : workflow complet pour un nouveau batch ML (entraînement → calibration → validation OOS → production).
> S'applique à la page **Backtesting** de l'IHM (9 onglets) et à la page **Pipeline** (mise en production).

---

## Vue d'ensemble

Le workflow sépare deux familles d'actions :

- **Producteurs** : créent une calibration (run DB `weights_calibration_runs`, JSON `config/p21_sector_multipliers.json`)
- **Consommateurs** : appliquent la calibration dans un backtest (selectboxes de l'onglet Backtest)

> **Prédiction sous deux formes** :
> - **Prédiction historique** = le backfill (étape 1) : rejoue le modèle jour par jour sur l'historique pour produire les rangs PIT consommés par les backtests.
> - **Prédiction live** = l'étape 10 du Pipeline : uniquement après validation, lors de la mise en production.

---

## Ordre d'exécution

| # | Onglet / Page | Action | Pourquoi |
|---|---------------|--------|----------|
| 0 | — | **Entraîner le modèle** global + per-symbol (nouveau batch) | Prérequis : le batch doit exister |
| 1 | 🧱 Backfill scores history | **Lancer le backfill (rangs PIT du batch)** — c'est la **prédiction historique** | Sans historique de rangs, aucun backtest/calibration ne peut tourner |
| 2 | ▶️ Backtest | **Run baseline** : dates de calibration, sizing `equal_weight`, **tout `off`** | Produit `trades.csv` + référence de comparaison |
| 3 | 🎯 Calibrate conviction | Lancer `calibrate-conviction-weights` (fenêtre se terminant **≤ début de l'étape 5**) | Produit le run en DB (`weights_calibration_runs`) |
| 3' | ▶️ Backtest → expander « 🔧 Calibrer les multiplicateurs... » | Choisir le run de l'étape 2 → « ⚙️ Calibrer et écrire le JSON » | Produit `config/p21_sector_multipliers.json` |
| 4 | 🔄 Walk-forward conviction | Lancer sur toute l'histoire | Vérifie la stabilité des poids conviction |
| 5 | ▶️ Backtest | **Runs de validation OOS, un par un** :<br>a) sizing `rank_weighted` seul<br>b) + selectbox « Multiplicateurs sectoriels » = `default`<br>c) + selectbox « Calibration conviction/Kelly » = `auto`/`pinned`<br>d) combo a+b+c | Chaque A/B doit battre son parent avant adoption |
| 6 | 🎛️ Calibration trimestrielle | Au rythme du job (fin de trimestre) | Indépendant du batch, garde-fou de dérive |
| 7 | — | **Décision** : adopter uniquement ce qui est validé OOS | Aucune promotion automatique |
| 8 | 🚀 Pipeline | **Mise en production** : promouvoir le batch (`live_batch_id`) + activer le flux live → **prédiction live** (étape 10) | La production consomme le batch et le sizing validés |

---

## Producteurs vs Consommateurs

| Couche | Producteur (calibrer) | Consommateur (appliquer dans le backtest) |
|--------|----------------------|-------------------------------------------|
| **Conviction/Kelly** | Onglet « 🎯 Calibrate conviction » → bouton « Lancer calibrate-conviction-weights » → run persisté en DB | Selectbox « 🎯 Calibration conviction/Kelly » (`off`/`auto`/`pinned`) dans l'onglet Backtest, Phase 2 ≠ `off` |
| **Multiplicateurs sectoriels** | Expander « 🔧 Calibrer les multiplicateurs sectoriels depuis un run passé » (écrit le JSON) | Selectbox « 🏷️ Multiplicateurs sectoriels (P2-1) » (`off`/`default`/`custom`) |

La calibration seule ne change rien — il faut qu'un backtest la **consomme** pour qu'elle agisse.

---

## Règles de discipline

1. **Producteurs avant consommateurs** : calibrer (étapes 3, 3') AVANT les backtests qui consomment (étape 5).
2. **Fenêtre de calibration strictement antérieure** à la fenêtre de validation (pas de look-ahead). La selectbox conviction l'applique automatiquement (`window_end ≤ start`).
3. **Un A/B par variante** : ne jamais empiler deux changements dans un run de validation sans avoir validé chacun séparément.
4. **Le run baseline (étape 2) reste pur** : `equal_weight`, calibration conviction `off`, multiplicateurs `off`.
5. **Les étapes 3 et 3' sont indépendantes** : elles consomment toutes deux le run de l'étape 2, ordre libre.

---

## Cas concret : nouveau batch entraîné 2016-2025

```
0. Entraîner le batch (global + per-symbol)
1. Backfill rangs 2016-2025                      ← prédiction historique
2. Backtest equal 2016-2024         → b26_calib  (baseline)
3. Calibrate conviction 2016-2024   → run DB
3'. Multiplicateurs depuis b26_calib → JSON
4. Walk-forward conviction 2016-2025
5. Backtests OOS 2025 :
   a. rank_weighted
   b. rank_weighted + secteur (default)
   c. Phase 2 + conviction (auto)
   d. les trois combinés
6. Job trimestriel (à part)
7. Décision (garde-fou : OOS positif sur 5/6 métriques minimales)
8. Promotion live + prédiction pipeline
```

> ⚠️ **Piège de période** : si le batch est entraîné sur 2016-2025, il ne reste plus de période OOS.
> Faire du walk-forward : calibrer sur 2016-2020, valider sur 2021-2025.

---

## Multiplicateurs sectoriels — rappel

- **Règle de dérivation** : efficience secteur (pnl/notional, bps) → facteur :
  - ≥ +150 bps → ×1.25
  - +50..+150 → ×1.10
  - ±50 → ×1.00
  - −150..−50 → ×0.75
  - ≤ −150 → ×0.50
- **Outil** : `python -m modelFactory.analyze_p21_attribution --run-dir <run> --out-json config/p21_sector_multipliers.json` (option `--min-trades` pour filtrer les petits secteurs, 0 = pas de filtre comme B25)
- **Validation B25 (OOS 2025)** : rank_weighted 33.4%/Sharpe 1.18 → rankw+secteur 34.4%/1.20 → adopté
- Les multiplicateurs sont **figés** dans le JSON : à re-calibrer à chaque nouveau batch (l'efficience sectorielle peut dériver)

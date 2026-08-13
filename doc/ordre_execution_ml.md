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
| 5 | ▶️ Backtest | **Runs de validation OOS, un par un (4 runs)** :<br>**5a)** sizing `rank_weighted` seul → vs étape 2<br>**5b)** + selectbox « Multiplicateurs sectoriels » = `default` → vs 5a<br>**5c)** + selectbox « Calibration conviction/Kelly » = `auto`/`pinned` (sans secteur) → vs 5a<br>**5d)** combo complet : rank_weighted + secteur + conviction → vs 5b et 5c | Chaque A/B doit battre son parent avant adoption |
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

## Étape 5 en détail — les 4 runs de validation

Principe : **un seul changement à la fois**, chaque run se compare à son parent.

| Run | Configuration | Comparé à | Question posée |
|-----|---------------|-----------|----------------|
| **5a** | sizing `rank_weighted` | Étape 2 (equal) | Le rank-weighted aide-t-il OOS ? |
| **5b** | `rank_weighted` + secteur `default` | 5a | Les multiplicateurs sectoriels ajoutent-ils ? |
| **5c** | `rank_weighted` + conviction `auto` (sans secteur) | 5a | La calibration conviction ajoute-t-elle ? |
| **5d** | rank_weighted + secteur + conviction | 5b et 5c | Le combo complet est-il meilleur que chaque ingrédient ? |

### Pourquoi 4 et pas 3

- **5b** et **5c** isolent chacun un effet (secteur d'un côté, conviction de l'autre) par rapport au même parent **5a**.
- **5d** vérifie que les deux effets ne se **cannibalisent pas** une fois combinés — il arrive que chacun aide seul mais que le combo n'apporte rien de plus.

### Coût et version minimale

- Chaque run : ~10-35 min en arrière-plan → ~1-2 h au total pour l'étape 5.
- **Version minimale (3 runs)** : sauter 5c si la conviction n'est pas utilisée en production → 5a, 5b, 5d.

### Décision & application (après les 4 runs)

**Comment choisir** — chaque run se compare à son parent sur 6 métriques : retour total, Sharpe, Sortino, max DD, profit factor, PnL net.

1. Adopter si le child bat son parent sur **≥ 5/6 métriques**, avec dégradation négligeable sur les autres (ex. DD +0.2 pt toléré, +3 pts non).
2. Un gain de +1 pt de retour avec DD dégradé → **non** (bruit OOS sur un an).
3. **Descendre la chaîne** : 5d (combo) n'est adopté que s'il bat **5b ET 5c** — sinon garder le meilleur ingrédient seul.
4. **Simplicité** : si combo ≈ meilleur ingrédient seul → garder le plus simple (moins de paramètres = moins de risque).
5. **Consigner le verdict dans `prompt/ml_journal.md`** (voir section dédiée).

**Comment appliquer** — tout est pilotable depuis l'IHM :

| Cible | Application (IHM) |
|-------|-------------|
| **Backtests futurs** | Page Backtesting : selectboxes mémorisées (rank_weighted, secteur `default`, conviction `auto`) |
| **Sizing live (rank_weighted + secteur)** | Page **Pipeline > Paramètres Risk Management > expander « Allocation P2-1 »** : mode `rank_weighted` + chemin JSON (défaut `config/p21_sector_multipliers.json`) → propagé au step 11 Risk via `--sizing-mode`/`--sector-multipliers-path` |
| **Conviction en live** | Page **Calibrations poids** (🧮) : sélectionner le run → bouton « ✅ Promouvoir pour le live » (écrit `eligible_for_live=1`) ou « 🔒 Bloquer » |
| **Modèle** | Page **ML** : bouton « Promouvoir cette campagne pour le serving » → `model_serving_batch` |

> ⚠️ **Adopté côté backtest ≠ appliqué en live.** Les 4 runs valident la règle ;
> ensuite : activer le sizing dans la config live (branché dans `risk_management`
> depuis 2026-08-13, opt-in), activer la calibration
> conviction en config live, promouvoir le batch.

### Pourquoi consigner le verdict dans `prompt/ml_journal.md`

`prompt/ml_journal.md` est le **journal de recherche ML** du projet. Y noter chaque verdict sert à :

- **Traçabilité** : on garde les chiffres OOS qui ont motivé l'adoption ou le rejet (ex. B25 : 33.4% → 34.4%, +0.02 Sharpe).
- **Éviter de re-tester** : toute conclusion documentée devient un acquis ; on ne relance pas un A/B déjà tranché.
- **Passage de relais** : un lecteur du fichier sait instantanément quelle config est adoptée, ce qui reste à faire (backlog P2-3, P3...) et pourquoi.
- **Discipline scientifique** : écrire le verdict oblige à regarder les métriques et à justifier la décision, au lieu de se fier à la mémoire.

Format recommandé : une ligne par item, avec la date, les chiffres comparatifs et le statut (✅ adopté / ❌ rejeté / ⏳ en cours).

---

## Application en production via l'IHM — pas à pas

Les 3 actions de mise en production se font uniquement depuis l'IHM (aucun terminal requis).

### 1. Activer le sizing live (rank_weighted + secteurs)

1. Ouvrir la page **Pipeline**.
2. Descendre à **« Paramètres Risk Management »** → expander **« Risk — Allocation P2-1 (rank_weighted + multiplicateurs sectoriels) »**.
3. « Risk — mode d'allocation » : passer de `atr` (legacy) à **`rank_weighted`**.
4. « Risk — JSON multiplicateurs sectoriels » : garder `config/p21_sector_multipliers.json` (ou vider pour désactiver les facteurs secteurs).
5. Lancer le pipeline : le step 11 Risk reçoit `--sizing-mode rank_weighted --sector-multipliers-path ...`.
6. Contrôler le run risk (page Risk / résumé) : le payload doit montrer les facteurs appliqués (log « P2-1 allocation live »).

> Rappel : n'activer qu'après validation OOS (étape 5). Le mode est **opt-in** — `atr` par défaut = comportement legacy inchangé.

### 2. Activer la calibration conviction en live

1. Lancer la calibration : page **Backtesting → onglet « 🎯 Calibrate conviction »** → « Lancer calibrate-conviction-weights » (fenêtre se terminant avant la période OOS).
2. Valider OOS (étape 5c).
3. Ouvrir la page **« 🧮 Calibrations poids »**, sélectionner le run dans la liste.
4. Bouton **« ✅ Promouvoir pour le live »** → écrit `eligible_for_live=1` (+ raison dans `eligibility_reason`).
5. Le live le consomme automatiquement via `risk_management.empirical_calibration.fallback_levels` (config.yaml).
6. Pour retirer : bouton **« 🔒 Bloquer pour le live »** (désactive le fallback vers ce run).

### 3. Promouvoir le batch ML

1. Ouvrir la page **ML**, localiser la campagne terminée.
2. Bouton **« Promouvoir cette campagne pour le serving »** → INSERT dans `model_serving_batch` (scope `default`).
3. Lancer le pipeline (étapes 1→10) : la prédiction live utilise le batch promu.
4. Smoke test : prédictions datées du jour, univers ≥ garde-fou breadth (75 % du référentiel).

> Le batch de test `a8aadc` (2026-08-13) est ignoré : B25 (`model-factory-20260811223551-ef2cd0`) reste le batch de production.

---

## Cas concret : nouveau batch entraîné 2016-2025

```
0. Entraîner le batch (global + per-symbol)
1. Backfill rangs 2016-2025                      ← prédiction historique
2. Backtest equal 2016-2024         → b26_calib  (baseline)
3. Calibrate conviction 2016-2024   → run DB
3'. Multiplicateurs depuis b26_calib → JSON
4. Walk-forward conviction 2016-2025
5. Backtests OOS 2025 (4 runs incrémentaux) :
   5a. rank_weighted                    → vs baseline equal
   5b. rank_weighted + secteur          → vs 5a
   5c. rank_weighted + conviction (auto)→ vs 5a
   5d. rank_weighted + secteur + conviction → vs 5b et 5c
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

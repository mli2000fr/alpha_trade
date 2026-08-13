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
| 0 | — | **Entraîner le modèle** global + per-symbol avec la **config champion B25** : `--include-short-score --target-excess-vs-spy --include-factors --catboost-loss-function YetiRank`, univers **liquidité 400** (`config/ticket_mid_cap_400.txt`), training 2016, 8 splits × 252j, 756j, + **`--comment "<description>"`** (visible dans la liste des campagnes). **Gate d'entrée : IC Rank doit battre B25 (0.0241) — sinon ne pas adopter** (voir « Gates d'adoption ») | Prérequis : le batch doit exister et être meilleur que le champion |
| 1 | 🧱 Backfill scores history | **Lancer le backfill (rangs PIT du batch)** — c'est la **prédiction historique**. L'étape 10 du pipeline est **batch-agnostique** (dispatch per-symbol/per-sector automatique via `--batch-id`) | Sans historique de rangs, aucun backtest/calibration ne peut tourner |
| 2 | ▶️ Backtest | **Run baseline** : dates de calibration, sizing `equal_weight`, **tout `off`** | Produit `trades.csv` + référence de comparaison |
| 3 | 🎯 Calibrate conviction | Lancer `calibrate-conviction-weights` (fenêtre se terminant **≤ début de l'étape 5**) | Produit le run en DB (`weights_calibration_runs`) |
| 3' | ▶️ Backtest → expander « 🔧 Calibrer les multiplicateurs... » | Choisir le run de l'étape 2 → « ⚙️ Calibrer et écrire le JSON » | Produit `config/p21_sector_multipliers.json` |
| 4 | 🔄 Walk-forward conviction | Lancer sur toute l'histoire | Vérifie la stabilité des poids conviction |
| 5 | ▶️ Backtest | **Runs de validation OOS, un par un** :<br>**5a)** sizing `rank_weighted` seul → vs étape 2<br>**5b)** + selectbox « Multiplicateurs sectoriels » = `default` → vs 5a<br>**5c)** + selectbox « Calibration conviction/Kelly » = `auto`/`pinned` (sans secteur) → vs 5a<br>**5d)** combo complet : rank_weighted + secteur + conviction → vs 5b et 5c<br>**5e)** `--bull-strict-mode no_shorts` → vs étape 2 (P2-3)<br>**5f)** `--bull-strict-mode no_trades` → vs étape 2 (P2-3)<br>⚠️ 5e/5f sont **à re-valider à chaque batch** : la règle est portable, son bénéfice dépend des PnL du modèle | Chaque A/B doit battre son parent avant adoption |
| 6 | 🎛️ Calibration trimestrielle | Au rythme du job (fin de trimestre) | Indépendant du batch, garde-fou de dérive |
| 7 | — | **Décision** : adopter uniquement ce qui est validé OOS (≥ 5/6 métriques vs parent) — procédure détaillée dans « Décision & application » | Aucune promotion automatique |
| 8 | ⚙️ Pipeline → « Paramètres Risk Management » → expander « Allocation P2-1 » | **Activer le sizing live** : mode `rank_weighted` + **JSON sectoriel recalibré à l'étape 3' pour ce batch** | Le step 11 Risk applique les facteurs validés en 5a/5b |
| 9 | 🧮 Calibrations poids | **Activer la conviction live** : sélectionner le run validé (5c/5d) → « ✅ Promouvoir pour le live » (`eligible_for_live=1`) | Le live consomme le run via le fallback `empirical_calibration` |
| 10 | 🤖 ML / Prédictions → « 🧭 Gouvernance & artefacts de serving » | **Promouvoir le batch** (« Promouvoir cette campagne pour le serving » → `model_serving_batch`) **+ mettre à jour `batch_diagnostics.live_batch_id` dans `config.yaml`** + lancer le pipeline live (étapes 1→10). Le job quotidien reste `python -m modelFactory.predict_per_sector` | La production consomme le batch + sizing + conviction validés → prédiction live |
| 11 | 🤖 ML / Prédictions → résumé du run risk | **Smoke test live** : prédictions datées du jour, **univers ≥ garde-fou breadth 75 % = 300 symboles** (seuil validé par B38 : 300 parmi les 400 → IC −5 % seulement), payload `runtime_applied: true`, ingestion réparée (barres à jour) | Confirme que tout est branché avant de laisser tourner |

> Les étapes **8 et 9 sont indépendantes** (ordre libre entre elles) ; l'étape **10**
> se fait en dernier, juste avant le lancement live. Une seule de ces étapes
> peut être sautée si sa variante a été rejetée OOS (ex. conviction ❌ → étape 9 sautée).

### Applicabilité selon le mode d'entraînement

| Mode | Workflow applicable ? | Note |
|------|----------------------|------|
| **Global + per-symbol** | ✅ **Oui, intégralement** | Mode de production (B25). Toutes les étapes 0→11 sont validées dessus. |
| **Global + per-sector** | ⚠️ **Mécaniquement oui, non recommandé** | Le dispatch de prédiction et le backfill des rangs synth gèrent les deux modes, mais le per-sector est **suspendu comme signal de trading** (F1 macro ≈ 0.33 = pile ou face, DirAcc ≈ 50 %, campagne 2026-08-05 sans alpha WF exploitable). Lancer le workflow complet produirait des backtests sans alpha (étapes 5-11 = bruit). Exception : un futur batch per-sector avec F1 WF > 0.35 et DirAcc > 0.53 redeviendrait éligible. |

> En production, la gate `research_only` interdit l'exécution paper/live depuis un
> modèle per-sector tant qu'il n'a pas prouvé d'alpha walk-forward exploitable.

### Gates d'adoption d'un nouveau batch (leçons de `ml_todo.md`)

Avant même l'étape 1, vérifier ces points sur le nouveau batch :

| Gate | Condition | Source |
|------|-----------|--------|
| **IC Rank Global** | Doit **battre B25 (0.0241)** ; sinon ne pas adopter | Podium B0-B38 : B25 champion définitif |
| **Univers d'entraînement** | **Liquidité 400** (`config/ticket_mid_cap_400.txt`). 300 parmi les 400 acceptable (−5 % IC, IR +7 %, B38) | B35/B36 (196) ❌, B37 (393 swing) ❌ |
| **Flags** | `--include-short-score --target-excess-vs-spy --include-factors --catboost-loss-function YetiRank` (config B25) | B31-B34 ❌ : fondamentaux/cross-sectional/screener toxiques même en YetiRank |
| **Fenêtre** | Training from **2016**, 8 splits × 252j, fenêtre 756j, demi-vie 360j | B18/B19 ❌ (2011 = −18 à −22 %) ; 13 splits ❌ |
| **Target** | Pipeline complet (smoothing + sector-neutral + factor-neutral) — pas de raw rank | B30 ❌ (P1-3 : −36 %) |
| **Per-sector** | `research_only` tant que F1 WF ≤ 0.35 / DirAcc ≤ 0.53 | Campagne 2026-08-05 sans alpha |
| **Commentaire** | `--comment "<description>"` renseigné (affiché dans la liste des campagnes ML) | IHM « Gouvernance & artefacts de serving » |

> 🚫 **Si le batch échoue une seule gate d'entrée → ne pas lancer le workflow.**
> Les gates 0/1-5 restent applicables (baseline, calibrations, A/B) mais le verdict
> de l'étape 7 sera négatif par construction.

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

## Étape 5 en détail — les runs de validation

Principe : **un seul changement à la fois**, chaque run se compare à son parent.

| Run | Configuration | Comparé à | Question posée |
|-----|---------------|-----------|----------------|
| **5a** | sizing `rank_weighted` | Étape 2 (equal) | Le rank-weighted aide-t-il OOS ? |
| **5b** | `rank_weighted` + secteur `default` | 5a | Les multiplicateurs sectoriels ajoutent-ils ? |
| **5c** | `rank_weighted` + conviction `auto` (sans secteur) | 5a | La calibration conviction ajoute-t-elle ? |
| **5d** | rank_weighted + secteur + conviction | 5b et 5c | Le combo complet est-il meilleur que chaque ingrédient ? |
| **5e** | `--bull-strict-mode no_shorts` (sizing equal) | Étape 2 | Couper les shorts en bull strict aide-t-il ? (P2-3) |
| **5f** | `--bull-strict-mode no_trades` (sizing equal) | Étape 2 | Couper tous trades en bull strict aide-t-il ? (P2-3) |

> ⚠️ **5e/5f dépendent du modèle** : à re-valider à chaque nouveau batch (la règle
> est portable, son bénéfice non). Ils utilisent le sizing `equal_weight` pour
> isoler l'effet de l'overlay seul.

### Pourquoi 6 et pas 3

- **5b** et **5c** isolent chacun un effet (secteur d'un côté, conviction de l'autre) par rapport au même parent **5a**.
- **5d** vérifie que les deux effets ne se **cannibalisent pas** une fois combinés — il arrive que chacun aide seul mais que le combo n'apporte rien de plus.
- **5e/5f** testent l'overlay bull strict (P2-3) sur le même parent que 5a ; si un mode gagne, il se combine au sizing final (rank_weighted + bull-strict) — un run combo supplémentaire peut être ajouté avant l'adoption.

### Coût et version minimale

- Chaque run : ~10-35 min en arrière-plan → ~2-3 h au total pour l'étape 5 (6 runs).
- **Version minimale (3 runs)** : sauter 5c si la conviction n'est pas utilisée en production et 5f si le post-hoc no_trades est faible → 5a, 5b, 5e.

### Décision & application (après les runs)

**Comment choisir** — chaque run se compare à son parent sur 6 métriques : retour total, Sharpe, Sortino, max DD, profit factor, PnL net.

**Pas à pas (étape 7 du tableau)** :

1. **Récupérer les 6 métriques** de chaque run depuis son `report.json` (dossier `artifacts/backtesting/<run>/`) :

   | Métrique | Champ du report.json |
   |----------|----------------------|
   | Retour total (%) | `summary.total_return_pct` |
   | Sharpe | `summary.sharpe_ratio` |
   | Sortino | `summary.sortino_ratio` |
   | Max drawdown (%) | `summary.max_drawdown_pct` |
   | Profit factor | `summary.profit_factor` |
   | PnL net ($) | `summary.pnl_net` |

2. **Comparer chaque run à SON parent** :

   | Comparaison | Question posée |
   |-------------|----------------|
   | 5a vs étape 2 (equal) | Le rank_weighted gagne-t-il OOS ? |
   | 5b vs 5a | Les multiplicateurs sectoriels ajoutent-ils ? |
   | 5c vs 5a | La calibration conviction ajoute-t-elle ? |
   | 5d vs 5b ET 5c | Le combo est-il meilleur que chaque ingrédient ? |

3. **Appliquer les règles** :
   - **Adopter** si le child bat son parent sur **≥ 5/6 métriques**, avec dégradation négligeable sur les autres (ex. DD +0.2 pt toléré, +3 pts non).
   - Un gain de +1 pt de retour avec DD dégradé → **non** (bruit OOS sur un an).
   - **Descendre la chaîne** : 5d (combo) n'est adopté que s'il bat **5b ET 5c** — sinon garder le meilleur ingrédient seul.
   - **5e/5f** : adopter le mode bull-strict gagnant si ≥ 5/6 métriques vs étape 2 ; si les deux gagnent, prendre le meilleur des deux (puis éventuellement un run combo rank_weighted + bull-strict avant l'adoption).
   - **Simplicité** : si combo ≈ meilleur ingrédient seul → garder le plus simple (moins de paramètres = moins de risque).

4. **Consigner le verdict dans `prompt/ml_journal.md`** (voir section dédiée) : une ligne par décision, avec la date, les chiffres comparatifs et le statut ✅/❌/⏳.

> **Exemple B25 (2026-08-13)** : 5a adopté (rank_weighted 33.4 % vs equal 28.0 %, +0.08 Sharpe, DD +2.9 pts toléré) ; 5b adopté (rankw+secteur 34.4 % vs 33.4 %, +0.02 Sharpe, DD +0.2 pt) → a motivé le branchement sizing live.

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
4. « Risk — JSON multiplicateurs sectoriels » : **utiliser le JSON recalibré à l'étape 3' pour CE batch** (`config/p21_sector_multipliers.json`), ou vider pour désactiver les facteurs secteurs.
5. Lancer le pipeline : le step 11 Risk reçoit `--sizing-mode rank_weighted --sector-multipliers-path ...`.
6. Contrôler le run risk (page Risk / résumé) : le payload doit montrer les facteurs appliqués (log « P2-1 allocation live »).

> Rappel : n'activer qu'après validation OOS (étape 5). Le mode est **opt-in** — `atr` par défaut = comportement legacy inchangé.

> ⚠️ **Bull-strict live (5e/5f)** : l'overlay P2-3 est backtest-only pour l'instant.
> S'il est adopté, il faudra le brancher dans `risk_management` (même schéma que
> le sizing P2-1 : flag opt-in + benchmark SPY) avant activation live.

### 2. Activer la calibration conviction en live

1. Lancer la calibration : page **Backtesting → onglet « 🎯 Calibrate conviction »** → « Lancer calibrate-conviction-weights » (fenêtre se terminant avant la période OOS).
2. Valider OOS (étape 5c).
3. Ouvrir la page **« 🧮 Calibrations poids »**, sélectionner le run dans la liste.
4. Bouton **« ✅ Promouvoir pour le live »** → écrit `eligible_for_live=1` (+ raison dans `eligibility_reason`).
5. Le live le consomme automatiquement via `risk_management.empirical_calibration.fallback_levels` (config.yaml).
6. Pour retirer : bouton **« 🔒 Bloquer pour le live »** (désactive le fallback vers ce run).

### 3. Promouvoir le batch ML

1. Ouvrir la page **ML**, localiser la campagne terminée (la liste déroulante affiche le `--comment` du batch).
2. Bouton **« Promouvoir cette campagne pour le serving »** → INSERT dans `model_serving_batch` (scope `default`).
3. **Mettre à jour `batch_diagnostics.live_batch_id` dans `config.yaml`** avec le batch promu.
4. Lancer le pipeline (étapes 1→10) : la prédiction live utilise le batch promu.
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
5. Backtests OOS 2025 (runs incrémentaux) :
   5a. rank_weighted                    → vs baseline equal
   5b. rank_weighted + secteur          → vs 5a
   5c. rank_weighted + conviction (auto)→ vs 5a
   5d. rank_weighted + secteur + conviction → vs 5b et 5c
   5e. bull-strict no_shorts            → vs baseline (P2-3, revalidation batch)
   5f. bull-strict no_trades            → vs baseline (P2-3, revalidation batch)
6. Job trimestriel (à part)
7. Décision (garde-fou : OOS positif sur 5/6 métriques minimales)
8. Activer sizing live (Pipeline → Allocation P2-1 : rank_weighted + JSON recalibré)
9. Activer conviction live (Calibrations poids → Promouvoir pour le live)
10. Promouvoir le batch (page ML + live_batch_id dans config.yaml) + lancer le pipeline live
11. Smoke test live (prédictions du jour, univers ≥ 75 % = 300 validé par B38)
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

# Tiebreaker dip_quality — Document de synthèse

**Date :** 2026-08-28 · **Auteur :** session Copilot · **Statut :** recherche — verdict **INCONCLUSIVE_LOW_SAMPLE** (OOS 2026), non activé en production.

---

## 1. Contexte & objectif

Le modèle **`dip_quality_score`** estime la qualité d'un candidat DIP (probabilité que le DIP soit « bon », c.-à-d. `future_return_H20 > 0`), à partir de features **lag0** (jour J uniquement).

Campagne Q0–Q3 (2026-08-27) sur les politiques de sélection basées sur ce score :

| Politique | Comportement | Verdict |
|---|---|---|
| `rank` (Q1) | priorité aux DIP de meilleure qualité (écrase `proba_long`) | **NO_GO** |
| `top50` (Q2) | ne garder que les DIP au-dessus du percentile 50 | **NO_GO** |
| `top25` (Q3) | ne garder que les DIP au-dessus du percentile 75 | **NO_GO** |

Ces politiques forcent la sélection → dégradent la performance. **Hypothèse retenue (pré-spécifiée, une seule règle) :**

> Si deux candidats DIP ont un score de sélection principal **dans une bande très proche**, utiliser `dip_quality_score` comme **second critère** (tiebreak), **sans forcer** de sélection.

Objectif : tirer parti de la qualité sans casser l'ordre du modèle ML — un tiebreak, pas un gate.

---

## 2. Fonctionnement

### 2.1 Modèle dip_quality (FROZEN)

- **Modèle :** `M2 = LogisticRegression(C=0.1)`
- **Features F_FULL (12, lag0 uniquement) :**
  `pb_ratio, pos_52w, dist_52w_low, ret60, dist_sma50, sector_breadth, breadth_above_sma50, spy_dist_sma200, ten_y, yield_10y_5d_pct, atr14_pct, vol_z20`
- **Pré-traitement :** imputeur médiane + `StandardScaler` fit **TRAIN uniquement**
- **Purge/embargo :** H20, `PURGE_DAYS=30`, `MIN_TRAIN=200`
- **Cible :** `future_return_H20 > 0`
- **Source :** `modelFactory/dip_research/dip_quality_static_model.py` (FROZEN)

### 2.2 Événements DIP (filtre amont)

- **Règle N4/X2 :** `global_rank_20 >= 0.90` pendant 4 séances consécutives **ET** `ret_4 <= -2%`
- Batch de référence : `model-factory-20260811223551-ef2cd0`
- Appliqué via `selector.dip_filter.filter_day_candidates` (log `DIP_FILTER backtest ...`)

### 2.3 Règle tiebreak (définition FROZEN)

Dans `modelFactory/predictor._apply_dip_quality_tiebreak` :

1. **Bucket = décile de la position ML du jour** : `bucket = min(9, idx * 10 // n)` où `idx` = rang du candidat dans le tri ML du jour, `n` = nb candidats.
2. **Tri intra-bucket** par `dip_quality_score` **DESC** — candidats scorés d'abord, non-scorés en dernier (tri stable).
3. **Réassignation positionnelle** des probabilités : le **multiset des probas du bucket est conservé** — aucun score artificiel injecté (contrairement à `rank`/`top50`/`top25` qui surécrivent `proba_long = dip_quality_score`).

Le tiebreak ne change donc **que l'ordre** de sélection à l'intérieur d'un décile ML, jamais le pool de candidats ni l'exposition.

### 2.4 Câblage dans la cascade

- `apply_cascade_to_predictions` : si `dip_quality_policy == "tiebreak"` et map de scores fournie → appel de `_apply_dip_quality_tiebreak` puis réassignation `proba_long` pour les candidats scorés (même mécanisme que `rank`).
- `cascade_select` : filtre DIP via `filter_day_candidates`, puis sélection `top_pct=0.10, min_prob=0.55`, horizon `global_rank_10`.

---

## 3. Implémentation déjà réalisée

### 3.1 Code du moteur (intégré, non jetable)

| Fichier | Contenu |
|---|---|
| `modelFactory/predictor.py` | `_apply_dip_quality_policy` (policies `none/rank/top50/top25/tiebreak`), `_apply_dip_quality_tiebreak` (règle FROZEN), câblage dans `apply_cascade_to_predictions`, `cascade_select` (filtre DIP) |
| `backtesting/cli/_impl.py` | Flags CLI : `--dip-quality-policy` (choix `none/rank/top50/top25/tiebreak`), `--dip-quality-path` (lecture CSV `signal_date, symbol, dip_quality_score`, clés `(str(signal_date.date()), symbol.upper())`) |

⚠️ **Piège connu :** le `report.json` (summary/equity) vient du pipeline legacy `closed_trades_df` qui **ne consomme pas** la policy dip_quality → **toujours utiliser `trades.csv`** (pipeline phase3→7) pour les comparaisons recherche.

### 3.2 Scripts de recherche (temporaires, `scripts/`)

| Script | Rôle |
|---|---|
| `scripts/_tie2026_scores_v2.py` | **Générateur de scores PIT 2026** (cache parquet, incrémental) → `tiebreaker_2026_scores.csv` + audit PIT |
| `scripts/_tie2026_analysis.py` | **Analyse T0 vs T1** (métriques, substitutions, mensuel, contrôle « plus de trades », hash, critères GO) |

### 3.3 Livrables OOS 2026 (`artifacts/dip_quality_static/tiebreaker_2026_*`)

- `tiebreaker_2026_config.json` — config gelée (FROZEN)
- `tiebreaker_2026_scores.csv` + `tiebreaker_2026_score_pit_audit.csv` — scores PIT + audit
- `tiebreaker_2026_substitutions.csv` + `tiebreaker_2026_substitution_detail.csv` — détail substitutions (ranks + dq)
- `tiebreaker_2026_monthly.csv` — analyse mensuelle
- `tiebreaker_2026_metrics.csv` — métriques T0/T1
- `tiebreaker_2026_attribution.csv` — attribution des substitutions
- `tiebreaker_2026_report.md` — rapport OOS détaillé

---

## 4. Tests

### 4.1 Scores PIT 2026 — validation

- 1 282 scores, **96 dates**, 101 symboles, range **2026-01-02 → 2026-05-29**
- **Audit PIT :** `max_label_available_date < signal_date` pour **tous** les J (assertion OK) — aucun label futur utilisé
- Train = événements DIP avec `label_avail < J` (label_avail = signal_date + 20 jours ouvrés) et `future_return_H20` non-NaN

### 4.2 In-sample 2023–2025 (T0 baseline vs T1 tiebreak) — **GO**

Run : `artifacts/backtesting/q_tie` (T1). Résultats documentés :

| Métrique | T0 | T1 |
|---|---|---|
| PnL | 12 291 | **13 144** |
| Profit factor | 1.26 | **1.30** |
| Sharpe | 1.41 | **1.55** |
| MaxDD | -58.6 % | **-51.2 %** |
| Trades | 3 692 | 3 864 |
| **Substitution nette** | — | **+576** |

⚠️ Caveats : T1 trade **plus** (3 864 vs 3 692) et c'est **in-sample** → l'amélioration pourrait venir du volume, d'où le besoin d'un test OOS.

### 4.3 OOS 2026 (T0 vs T1, fenêtre 2026-01-01 → 2026-05-29, 103 sessions) — **INCONCLUSIVE_LOW_SAMPLE**

Métriques depuis `trades.csv` :

| Métrique | T0 | T1 | Δ |
|---|---|---|---|
| Trades (total) | 696 | 696 | 0 |
| Clôturés / Ouverts | 683 / 13 | 683 / 13 | 0 / 0 |
| **Net PnL** | 584.24 | **606.01** | **+21.77** |
| Total return | +14.61 % | +15.15 % | +0.54 pp |
| **Sharpe** | 0.898 | **0.928** | +0.029 |
| Sortino | 1.613 | **1.729** | +0.116 |
| **Profit factor** | 1.095 | **1.099** | +0.004 |
| **MaxDD** | -30.09 % | **-29.03 %** | +1.06 pp |
| Win rate | 44.51 % | 44.51 % | 0 |
| Avg / median trade | 0.86 / -5.09 | 0.89 / -5.04 | +0.03 / +0.05 |
| Worst day / 5 jours | -300.5 / -788.7 | -300.5 / **-743.8** | 0 / +44.9 |
| Coûts | 240 045 | 240 138 | +93 |

**Substitutions :** 18 (9 ajoutées / 9 retirées), **2,6 % des trades** · PnL ajoutés **+6**, retirés **-16** → **marginal +22**.

**Vérification du mécanisme (9 paires, `tiebreaker_2026_substitution_detail.csv`) :** dans chaque paire, à **même date / même rank / même score ML** (donc même bucket décile), le symbole ajouté (T1) a un **`dip_quality_score` supérieur** au retiré (T0). **7/9 paires meilleures en T1**, 2 pires (dont -45.8 en février).

**Analyse mensuelle** (`tiebreaker_2026_monthly.csv`) :

| Mois | Trades T0/T1 | PnL T0 | PnL T1 | Subs | Marginal |
|---|---|---|---|---|---|
| 2026-01 | 116/116 | -684.61 | -666.85 | 4 | +17.75 |
| 2026-02 | 153/153 | +455.58 | +438.18 | 4 | **-17.40** |
| 2026-03 | 178/178 | -500.72 | -480.99 | 8 | +19.73 |
| 2026-04 | 99/99 | +780.17 | +781.85 | 2 | +1.68 |
| 2026-05 | 137/137 | +533.82 | +533.82 | 0 | 0 |

L'amélioration est **répartie** (janvier, mars, avril) avec un mois négatif (février) — pas un épisode exceptionnel unique, mais de **faible ampleur** et réparti inégalement.

**Contrôle « plus de trades » (le GO ne doit pas venir d'un risque accru) :**

| Indicateur | T0 | T1 |
|---|---|---|
| Entrées / jour | 6.50 | 6.50 |
| Notional brut | 244 187 | 244 280 (+0.04 %) |
| Exposition moyenne | 58.14 % | 58.16 % |
| Exposition max | 103.87 % | 103.87 % |
| Turnover | 6104.7 % | 6107.0 % |
| Nb trades | 696 | 696 |

**Propre :** nombre de trades, notional et exposition quasi identiques → l'amélioration (+21.8) vient **exclusivement de la qualité des substitutions** (+22), pas d'un risque/volume supplémentaire.

**Hash / parité :** `md5(trades.csv)` T0 ≠ T1 (attendu : substitutions) ; pipeline strictement identique (A/B contrôlé) ; **aucune anomalie de leakage** (PIT OK, scores lag0 uniquement).

---

## 5. Critères GO pré-enregistrés — verdict

| Critère | Valeur OOS 2026 | Résultat |
|---|---|---|
| marginal substitution PnL > 0 | +22 | ✅ |
| T1 PF ≥ T0 PF | 1.099 ≥ 1.095 | ✅ |
| T1 Sharpe ≥ T0 Sharpe | 0.928 ≥ 0.898 | ✅ |
| T1 MaxDD pas matériellement pire | -29.03 % vs -30.09 % | ✅ |
| Performance nette T1 ≥ T0 | +606.0 ≥ +584.2 | ✅ |
| Aucune anomalie parité/leakage | A/B contrôlé, PIT OK | ✅ |

**Tous les critères numériques passent.** Mais le protocole pré-enregistré impose **`INCONCLUSIVE_LOW_SAMPLE`** si better avec **très peu de substitutions** :

- **18 substitutions seulement (2,6 %), 9 paires**, marginal **+22 $** → échantillon **trop faible** pour un GO confiant ;
- 2/9 paires négatives (dont -45.8 en février) ; effet petit et inégal ;
- **Limite macro 2026 :** `stock_macro_indicators_daily.vix` NULL pour toutes les 2026 lignes (dernier point 2025-12-31 ; fallback EODHD 401) → `macro_data_quality=missing` sur 102/102 séances, régime toujours `normal`. T0/T1 affectés **identiquement** (A/B valide), scores dip_quality **non affectés** (F_FULL sans vix, `ten_y` dispo), mais environnement absolu **pas pleinement prod-parity**.

### Verdict : **INCONCLUSIVE_LOW_SAMPLE**

Le tiebreak **fonctionne mécaniquement comme prévu** (sélection systématique du candidat de plus haut `dip_quality_score` dans le bucket), **améliore toutes les métriques directionnelles** (net, Sharpe, Sortino, PF, MaxDD) **sans plus de risque**, et **aucune anomalie de leakage/parité** n'est détectée. Mais l'échantillon OOS est trop faible et le gap VIX 2026 limite la représentativité absolue.

---

## 6. Intégration — état actuel et à faire

### 6.1 Déjà intégré (code réel, pas jetable)

| Composant | État |
|---|---|
| Moteur de sélection (`predictor.py`) | ✅ policy `tiebreak` implémentée et câblée |
| Backtest CLI (`backtesting/cli/_impl.py`) | ✅ `--dip-quality-policy tiebreak` + `--dip-quality-path` |

Lancer un backtest tiebreak (CLI) :
```
python run.py --mode backtest --start .. --end .. \
  --dip-quality-policy tiebreak \
  --dip-quality-path artifacts/dip_quality_static/tiebreaker_2026_scores.csv
```

### 6.2 Pas intégré (à faire si décision d'aller plus loin)

| Composant | État | Travail à faire |
|---|---|---|
| Page IHM backtest | ❌ aucun champ dip-quality | Ajouter un sélecteur `--dip-quality-policy` + champ `--dip-quality-path` dans `ihm/pages/backtesting/__init__.py` et `ihm/services/backtesting_runner.py` (même pattern que `oracle_batch_id`) |
| Génération live des scores | ❌ scripts recherche uniquement | Intégrer un générateur de scores dip_quality dans le pipeline ML predict (production des scores à J avec features ≤ J) — **condition requise** pour tout usage live |
| Production / live (`run_execution.py`, `pipeline_runner.py`, `execution_engine/`) | ❌ aucun chemin live | Câbler la policy dans le replay/sélection live **uniquement après un verdict plus solide** |

### 6.3 Prérequis avant activation en production

1. **Backfiller le VIX 2026** dans `stock_macro_indicators_daily` (dernier point 2025-12-31), puis relancer T0/T1 2026 pour un environnement pleinement prod-parity (régime `capital_preservation` actif comme en prod).
2. **Élargir l'échantillon de substitutions** : étendre la fenêtre OOS (mi-2026 dès que bars/labels dispo) ou agréger avec le test in-sample 2023-2025 (marginal +576, 172 substitutions) pour une décision de production.
3. En attendant : **ne pas activer le tiebreak en production** ; le garder en option de recherche (`--dip-quality-policy tiebreak`) avec la config gelée.

---

## 7. Références & fichiers

**Code moteur :**
- `modelFactory/predictor.py` → `_apply_dip_quality_policy`, `_apply_dip_quality_tiebreak`, `apply_cascade_to_predictions`
- `backtesting/cli/_impl.py` → flags `--dip-quality-policy` / `--dip-quality-path`

**Modèle / données (FROZEN) :**
- `modelFactory/dip_research/dip_quality_static_model.py` (M2, F_FULL)
- `modelFactory/dip_research/dip_temporal_pattern_feasibility.py` (panel/features)
- `modelFactory/dip_research/dip_context_pattern_analysis.py` (événements DIP, batch ef2cd0)

**Recherche OOS 2026 :**
- `scripts/_tie2026_scores_v2.py`, `scripts/_tie2026_analysis.py`
- `artifacts/dip_quality_static/tiebreaker_2026_*` (7+ livrables)

**Runs backtest :**
- In-sample : `artifacts/backtesting/q_tie`
- OOS 2026 : `artifacts/backtesting/oos2026_t0` (baseline) / `oos2026_t1` (tiebreak)

**Mémoire repo :**
- `/memories/repo/tiebreaker_oos2026_verdict_2026-08-28.md`
- `/memories/repo/dip_quality_backtest_q0_q4_verdict_2026-08-28.md`

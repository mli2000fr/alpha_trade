# Calibration Oracle Extreme — `proba_extreme`

> Statut : implémenté en option (`oracle.calibration` + `--oracle-calibration`).
> Date : 2026-08-26.

Ce document explique **pourquoi** recalibrer `proba_extreme` (Oracle Extreme / O0),
**ce que ça change**, et la différence entre les méthodes `rank` et `isotonic`.

---

## 1. Le problème

`proba_extreme` prédit la probabilité d'un **mouvement extrême** (top/bottom 10 % du
rendement futur, cible `oracle_extreme10`). ⚠️ Sémantique : `proba_extreme ≠ P(LONG)`.

Le modèle **classe très bien mais calibre mal en valeur absolue**. Sur le batch
`model-factory-20260826083755-9822e0` (run `oracle-wf-20260826111255`, OOS 2022-2024) :

| Décile de `proba_extreme` | P prédite (brute) | Taux réalisé | Écart |
|---|---|---|---|
| D1 (proba la plus basse) | 23.1 % | 6.2 % | surestimation massive |
| D2 | 28.0 % | 7.5 % | surestimation |
| D5 | 42.3 % | 13.5 % | surestimation |
| D10 (proba la plus haute) | 77.5 % | 45.3 % | surestimation massive |

**Lecture** : le modèle **ordonne bien** (AUC 0.7175, monotonie parfaite, lift 2.33×)
mais une proba brute de 77 % ne veut en réalité dire que **~45 %** de chance d'extrême.

Le recalibrage transforme `proba_extreme` en une proba **fiable en valeur absolue** :
après recalibrage, « P = 0.45 » veut vraiment dire ~45 % de chance d'extrême.

---

## 2. À quoi sert le recalibrage

Le recalibrage ne change **pas le classement** (ordre préservé → AUC/lift inchangés).
Il ne sert que si on **consomme la valeur absolue** de la proba :

1. **Sizing pondéré par conviction** — une proba surévaluée → risque mal dimensionné.
2. **Seuils absolus** (« garder P(extreme) > 0.7 ») — une proba surévaluée laisse passer
   des trades que le seuil réel n'aurait pas dû retenir.
3. **Combinaison de signaux** — `modelFactory/oracle/combine.py` combine déjà
   `P(extreme)` avec `global_rank_20` (score `α·rank + (1−α)·P`) : des probas bien
   calibrées se combinent mieux et rendent α interprétable.
4. **Interprétation opérateur** — une proba fiable est exploitable telle quelle.

---

## 3. Les méthodes

### `none` / `identity`
Probas brutes, inchangées. Comportement historique.

### `rank` — percentile intra-jour (relatif)
```python
proba_calibrée = proba.groupby("date").rank(pct=True)   # 0..1 par jour
```
- Par date, les symboles sont classés par `proba_extreme` et convertis en **percentile** :
  le plus haut du jour → 1.0, le plus bas → ~0.
- **Aucun fit, aucune cible, aucune fuite** — déterministe.
- **Perd l'échelle absolue** : une proba de 0.5 peut être classée 1.0 un jour (faible
  conviction générale) et 0.3 un autre jour. La valeur dépend du jour, pas de la proba.

### `isotonic` — proba calibrée absolue (PAV)
```python
# fit : mapping monotone proba → taux réalisé (oracle_extreme10), folds 2022-2024
x_sorted, fitted = isotonic_regression(x_fit, y_fit)
# apply : interpolation sur toutes les lignes
proba_calibrée = np.interp(proba, x_sorted, fitted)
```
- Fitte une **fonction monotone non-décroissante** `proba → fréquence d'extrême réalisée`
  (Pool Adjacent Violators, implémenté dans `modelFactory/oracle/combine.py`).
- **Conserve l'échelle absolue** : « P = 0.45 » veut dire ~45 % quel que soit le jour.
- Nécessite la cible `oracle_extreme10` + un **set de fit séparé** (folds de sélection
  2022-2024, jamais les folds OOS finaux → discipline anti-fuite, cf. S5).
- Sur les données réelles du batch 9822e0 :

  | Décile | Taux réalisé | P prédite après isotonic |
  |---|---|---|
  | D1 | 0.063 | 0.062 |
  | D10 | 0.452 | 0.453 |

  → prédit ≈ réalisé sur **chaque** décile, en **0.08 s** (grâce au binning, voir §5).

### `platt` (mention, per-symbol)
Régression logistique sur les log-odds (sigmoid) : 2 paramètres, lisse, monotone, robuste
sur petits échantillons. Utilisé pour les modèles **per-symbol**
(`modelFactory/calibration.py`). Non branché pour l'Oracle (voir §5).

---

## 4. Différence `rank` vs `isotonic`

| | **rank** | **isotonic** |
|---|---|---|
| Sémantique du résultat | percentile **relatif** du jour | **vraie proba** (≈ fréquence réalisée) |
| Même proba = même valeur d'un jour à l'autre ? | ❌ non (varie par jour) | ✅ oui (mapping global) |
| Nécessite la cible `oracle_extreme10` | non | oui (fit) |
| Nécessite un set de fit séparé | non | oui (2022-2024) |
| Risque de fuite | aucun | possible si mal fité |
| Effet sur le **classement** | préserve l'ordre du jour | préserve l'ordre global (Spearman ≈ 0.999 vs brute) |
| Redondant avec la cascade ? | **oui** (la cascade fait déjà `rank(pct=True)`) | non |

**En résumé** : `rank` = classement relatif du jour (redondant avec la cascade),
`isotonic` = vraie probabilité calibrée (change la valeur absolue, pas l'ordre).

---

## 5. Implémentation

- **Config** (`config.yaml`) :
  ```yaml
  oracle:
    calibration: none      # none | rank | isotonic
  ```
- **CLI** (`python -m backtesting run --help`) :
  `--oracle-calibration {none,rank,isotonic}` (prioritaire sur la config).
- **Code** : `modelFactory/oracle/combine.py::apply_oracle_calibration(oos_df, method)`,
  appliquée dans `backtesting/cli/_impl.py` au chargement du parquet OOS, avant la
  construction de `oracle_rank_map`.
- **Isotonic efficace** : le PAV naïf est O(n²) (`np.delete` en boucle) — impraticable
  sur ~200k lignes. On **bine** d'abord le set de fit en ~1000 bins quantiles
  (moyenne proba + taux réalisé par bin), puis PAV sur les bins, puis interpolation.
  Résultat : ~0.08 s au lieu de plusieurs minutes.

> ⚠️ **Note fuite** : le fit isotonique ne doit **jamais** se faire sur les folds OOS
> finaux évalués. Discipline S5 : fit sur 2022-2024, évaluation sur 2025-2026.

---

## 6. Impact sur le pipeline actuel

- La cascade `extreme_gate` trie par **percentile intra-date** de `proba_extreme`
  (`pd.Series(...).rank(pct=True)`) → la calibration (monotone) **ne change pas la
  sélection**.
- La calibration **fiabilise la valeur absolue** de `proba_extreme` pour tout
  consommateur en aval (combinaison de signaux, sizing pondéré, seuils absolus).
- Les runs OOS existants contiennent déjà `oracle_extreme10` → `isotonic` fonctionne
  immédiatement, sans réentraînement.

---

## Références

- `doc/oracle_extreme.md` — architecture et sémantique de l'Oracle Extreme.
- `modelFactory/oracle/combine.py` — combinaison + calibration (S5).
- `modelFactory/oracle/extreme_gate.py` — gate Extreme et `build_oracle_rank_map`.
- `ihm/pages/ml_diagnostics.py` — bloc « Oracle Extreme — Qualité du modèle (OOS) ».

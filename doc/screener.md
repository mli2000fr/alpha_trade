# Screener — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `screener/` et les commandes utiles pour :

- calculer les scores quantitatifs de base sur l'univers actions,
- filtrer la liquidité et la force relative,
- alimenter `stock_scores` avant le passage dans `selector`,
- exécuter le screener en mode live ou point-in-time.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `screener/__init__.py` | Exporte les primitives du module |
| `screener/stock_screener.py` | Point d'entrée principal et orchestration parallèle |
| `screener/pipeline.py` | Calcul des scores à partir des prix, séparation passe récente / passe historique |
| `screener/db_io.py` | Chargement chunks, benchmark, loaders optimisés récents / historiques, upsert `stock_scores` |
| `screener/models.py` | `ScreenerConfig` |

---

## 2. Prérequis

### 2.1 Tables et données requises

#### Obligatoires

- `stock_bars_daily`
- `stock_scores`

#### Recommandées

- `stock_metadata`
- présence du benchmark `SPY` dans `stock_bars_daily`

### 2.2 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

### 2.3 Comportement point-in-time

`run_screener()` accepte une date `as_of_date` côté code pour un usage backtest / backfill.

Le point d'entrée CLI expose désormais `--trade-date YYYY-MM-DD` :

- cette date devient la borne de lecture `as_of_date` ;
- elle est aussi utilisée comme `snapshot_date` pour l'archivage PIT ;
- en l'absence d'argument, le mode live courant reste le défaut.

---

## 3. Commandes utiles

### Lancement standard

```powershell
python -m screener.stock_screener
```

### Taille de chunk personnalisée

```powershell
python -m screener.stock_screener --chunk-size 500
```

### Nombre de workers personnalisé

```powershell
python -m screener.stock_screener --max-workers 8
```

### Benchmark personnalisé

```powershell
python -m screener.stock_screener --benchmark SPY
```

### Force relative minimale personnalisée

```powershell
python -m screener.stock_screener --min-relative-strength-index 100
```

### Fenêtre de range historique personnalisée

```powershell
python -m screener.stock_screener --historical-range-lookback-days 504 --min-historical-range-score 70
```

### Fenêtre passe 1 personnalisée

```powershell
python -m screener.stock_screener --first-pass-window-days 400
```

### Run PIT cohérent à une date métier donnée

```powershell
python -m screener.stock_screener --trade-date 2026-04-17
```

### Désactiver le mode 2 passes

```powershell
python -m screener.stock_screener --disable-two-pass-loading
```

### Correspondance avec l'IHM

Depuis `ihm/pages/pipeline.py`, l'étape `3. stock_screener` du workflow quotidien 1→14 lance bien :

```powershell
python -m screener.stock_screener ...
```

L'IHM expose désormais les options CLI réellement supportées par ce point d'entrée :

- `chunk-size`
- `max-workers`
- `benchmark`
- `liquidity-threshold-usd`
- `min-relative-strength-index`
- `historical-range-lookback-days`
- `min-historical-range-score`
- `first-pass-window-days`
- activation / désactivation du chargement en 2 passes

Point important :

- `0` sur `max workers` dans l'IHM signifie **auto** (`os.cpu_count()`) ;
- le mode **point-in-time** via `as_of_date` reste un usage **code/backtesting**, pas une option du launcher Pipeline live.

---

## 4. Ce que fait le module

### 4.1 Chargement distribué

`stock_screener.py` :

1. résout le nombre de workers ;
2. charge le rendement 6 mois du benchmark ;
3. parcourt l'univers éligible (`stock_metadata` actif/tradable/us_equity + historique exploitable) par chunks ;
4. exécute les calculs en `ProcessPoolExecutor` ;
5. applique une **passe 1 récente** (historique minimum, prix minimum, liquidité, force relative) ;
6. applique une **passe 2 historique agrégée** (lecture `MIN(low)` / `MAX(high)` seulement pour les survivants) ;
7. concatène les résultats ;
8. remplace `stock_scores` **uniquement si le run est complet et non vide**.

Politique de persistance opérateur :

- **run complet et non vide** → remplacement de `stock_scores` + archivage `stock_scores_history` ;
- **run vide** → conservation explicite du snapshot précédent ;
- **run partiel (`chunk_failures > 0`)** → conservation explicite du snapshot précédent.

### 4.2 Scores calculés

`compute_scores_from_prices()` calcule notamment :

- `liquidity_val`
- `relative_strength_index`
- `historical_range_score`
- `total_score`

Le `total_score` est désormais un **score normalisé cross-sectionnel** (0 → 100) calculé comme combinaison pondérée de :

- percentile de liquidité,
- percentile de force relative,
- percentile de position dans le range historique.

Cela évite qu'un facteur exprimé sur une échelle différente domine artificiellement le ranking final.

Par défaut, le CLI live utilise désormais la baseline stricte `STRICT_SWING_CASH_FILTERS` :

- prix minimal : `10 USD`
- liquidité minimale : `30 000 000 USD`
- force relative minimale : `100`

Les poids restent plus orientés swing cash :

- liquidité : `15%`
- force relative : `55%`
- position dans le range : `30%`

### 4.2 bis Performance / volumétrie

Le screener charge désormais les données en **2 passes** :

1. une fenêtre récente bornée (`first_pass_window_days`) pour filtrer rapidement l'univers ;
2. un chargement historique réduit à des **agrégats** par symbole pour calculer le range.

Ce design réduit fortement le coût lorsque l'univers contient plusieurs années de barres journalières par symbole.

### 4.3 Filtres principaux

Le screener élimine notamment les symboles qui ne respectent pas :

1. un seuil minimal de liquidité ;
2. un historique minimal suffisant (`min_history_days`, 252 jours par défaut) ;
3. un prix de clôture minimal (`min_close_price`, 10 USD par défaut en CLI live strict) ;
4. une force relative minimale vs benchmark (`min_relative_strength_index`, 100 par défaut) ;
5. une proximité suffisante des highs récents via un range borné (`historical_range_lookback_days`, 504 jours par défaut ; `min_historical_range_score`, 70 par défaut) ;
6. une référence benchmark exploitable.

### 4.4 Colonnes écrites

Le snapshot final alimente `stock_scores` avec des colonnes du type :

- `symbol`
- `liquidity_val`
- `relative_strength_index`
- `historical_range_score`
- `total_score`
- `last_updated_score`
- `last_updated_scan`

Le flag `is_candidate` est initialisé à 0 à ce stade ; la sélection finale est faite ensuite dans `selector`.

---

## 5. Pourquoi le screener peut produire 0 score

### Causes probables

1. `stock_bars_daily` vide ou incomplète ;
2. benchmark `SPY` absent ;
3. seuil de liquidité trop élevé ;
4. historique insuffisant sur la plupart des symboles ;
5. données post-sanitizer non encore disponibles.

Le code loggue explicitement un message critique si aucun score n'est produit.

Le point d'entrée CLI émet aussi un `run_summary` structuré sur stdout avec le préfixe :

- `::alpha_trade_run_summary::`

Champs notables :

- `targeted_symbols`
- `chunks_total`
- `chunk_failures`
- `chunk_failure_ratio`
- `chunk_error_samples`
- `recent_rows_loaded`
- `range_rows_loaded`
- `symbols_pass_history`
- `symbols_pass_liquidity`
- `symbols_pass_relative_strength`
- `symbols_final`
- `rows_avoided_estimate`
- `benchmark_load_seconds`
- `pass1_seconds`
- `pass2_seconds`
- `upsert_seconds`
- `persistence_status`
- `persisted_rows`
- `duration_seconds`

`chunk_error_samples` est volontairement **borné** : il s'agit d'un petit échantillon des chunks en échec (taille du chunk, quelques symboles, message d'erreur) pour accélérer le diagnostic opérateur sans gonfler excessivement le `run_summary`.

Ces résumés sont consommés côté IHM pour :

- la page `Pipeline` (run individuel + historique) ;
- la page `Overview` (résumés pipeline récents) ;
- la page `Screening` (contexte pipeline & qualité amont).

Pour `stock_screener`, l'IHM humanise aussi désormais `persistence_status` dans
les captions / détails :

- `replaced_scores_full_run` → `snapshot remplacé`
- `preserved_previous_scores_empty_run` → `snapshot préservé (run vide)`
- `preserved_previous_scores_partial_run` → `snapshot préservé (run partiel)`

En cas de partial run, utiliser le runbook opérateur :
[`doc/runbook_24_7.md`](runbook_24_7.md).

---

## 6. Vérifications utiles

### Vérifier les derniers scores écrits

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, liquidity_val, relative_strength_index, historical_range_score, total_score FROM stock_scores ORDER BY total_score DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier la présence de SPY dans `stock_bars_daily`

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    row = conn.execute(text("SELECT COUNT(*) AS n, MIN(date) AS dmin, MAX(date) AS dmax FROM stock_bars_daily WHERE symbol = \"SPY\" ")).mappings().one();
    print(dict(row))'
```

---

## 7. Tests

### Tests ciblés screener

```powershell
python -m pytest tests/test_screener_pipeline.py tests/test_screener_stock_screener.py tests/test_screener_db_io.py tests/test_screener_models.py tests/test_stock_screener.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. importer les bars daily avec le provider actif (`eodhd` nominal, `alpaca` rétrocompat) ;
2. exécuter le sanitizer ;
3. lancer le screener ;
4. vérifier `stock_scores` avant de lancer `selector`.

### Séquence recommandée

```powershell
python -m dataIntegrityEngine.import_eodhd_bar --write   # nominal si bars_provider=eodhd
# python -m dataIntegrityEngine.import_alpaca_bar        # rétrocompat uniquement si bars_provider=alpaca
python -m dataIntegrityEngine.data_sanitizer_daily
python -m screener.stock_screener --chunk-size 500 --max-workers 8
```

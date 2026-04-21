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
| `screener/pipeline.py` | Calcul des scores à partir des prix |
| `screener/db_io.py` | Chargement chunks, benchmark, upsert `stock_scores` |
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

Le point d'entrée CLI standard fonctionne, lui, en mode courant sans argument PIT exposé.

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

---

## 4. Ce que fait le module

### 4.1 Chargement distribué

`stock_screener.py` :

1. résout le nombre de workers ;
2. charge le rendement 6 mois du benchmark ;
3. parcourt l'univers par chunks ;
4. exécute les calculs en `ProcessPoolExecutor` ;
5. concatène les résultats ;
6. écrit un snapshot dans `stock_scores`.

### 4.2 Scores calculés

`compute_scores_from_prices()` calcule notamment :

- `liquidity_val`
- `relative_strength_index`
- `historical_range_score`
- `total_score`

### 4.3 Filtres principaux

Le screener élimine notamment les symboles qui ne respectent pas :

1. un seuil minimal de liquidité ;
2. une fenêtre de données suffisante ;
3. une référence benchmark exploitable.

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

1. importer les bars Alpaca ;
2. exécuter le sanitizer ;
3. lancer le screener ;
4. vérifier `stock_scores` avant de lancer `selector`.

### Séquence recommandée

```powershell
python -m dataIntegrityEngine.import_alpaca_bar
python -m dataIntegrityEngine.data_sanitizer_daily
python -m screener.stock_screener --chunk-size 500 --max-workers 8
```

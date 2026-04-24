# Data Integrity Engine — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `dataIntegrityEngine/` et les commandes utiles pour :

- importer l'univers d'actifs et les barres Alpaca,
- nettoyer et aligner les données daily,
- enrichir les secteurs depuis Finnhub,
- préparer les tables de marché consommées par le reste du pipeline.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `dataIntegrityEngine/__init__.py` | Package Python |
| `dataIntegrityEngine/import_alpaca_assets.py` | Import des actifs Alpaca vers `stock_metadata` |
| `dataIntegrityEngine/import_alpaca_bar.py` | Import des barres OHLCV Alpaca vers `stock_bars` |
| `dataIntegrityEngine/data_sanitizer_daily.py` | Nettoyage, alignement calendrier et anomalies sur les daily |
| `dataIntegrityEngine/update_sector.py` | Enrichissement `stock_metadata.sector` via Finnhub |
| `dataIntegrityEngine/sync_latest_quotes.py` | Snapshot des dernières quotes Alpaca vers `stock_quote_snapshots` |
| `dataIntegrityEngine/sync_earnings_calendar.py` | Synchronisation du calendrier earnings Finnhub vers `stock_earnings_calendar` |

---

## 2. Prérequis

### 2.1 Tables et données requises

#### Pour `import_alpaca_assets`

- `stock_metadata`

#### Pour `import_alpaca_bar`

- `stock_metadata`
- `stock_bars`

#### Pour `data_sanitizer_daily`

- `stock_bars`
- `stock_bars_daily`
- `cleaning_audit_latest`
- `cleaning_audit_runs`
- `stock_scores`
- `stock_metadata`

#### Pour `update_sector`

- `stock_metadata`
- token Finnhub

### 2.2 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
$env:ALPACA_API_KEY = "PK..."
$env:ALPACA_SECRET_KEY = "..."
$env:FINNHUB_API_KEY = "..."
```

---

## 3. Commandes utiles

### Import initial des actifs

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
```

### Import des barres daily Alpaca

```powershell
python -m dataIntegrityEngine.import_alpaca_bar
```

### Nettoyage et alignement daily

```powershell
python -m dataIntegrityEngine.data_sanitizer_daily
```

### Enrichissement secteur

```powershell
python -m dataIntegrityEngine.update_sector
```

### Enrichissement secteur borné

```powershell
python -m dataIntegrityEngine.update_sector --limit 50 --sleep-seconds 1.1 --log-every 10
```

### Snapshot des latest quotes

```powershell
python -m dataIntegrityEngine.sync_latest_quotes
```

### Synchronisation du calendrier earnings

```powershell
python -m dataIntegrityEngine.sync_earnings_calendar
```

---

## 4. Ce que fait le module

### 4.1 Import des actifs

`import_alpaca_assets.py` :

1. récupère les actifs Alpaca ;
2. upsert dans `stock_metadata` ;
3. prépare l'univers tradable.

### 4.2 Import des bars

`import_alpaca_bar.py` :

1. récupère les symboles actifs/tradables ;
2. détecte la dernière barre connue par symbole ;
3. appelle Alpaca avec `adjustment="split"` ;
4. valide strictement les barres OHLCV avant insertion ;
5. upsert les barres valides dans `stock_bars` ;
6. marque `bars_available=False` uniquement si l'absence d'historique est confirmée par Alpaca.

### 4.3 Sanitizeur daily

`DataSanitizer` :

1. charge les bars 1D brutes ;
2. reconstruit un calendrier daily à partir de `SPY` ;
3. forward-fill les jours manquants ;
4. calcule `daily_return` et autres features techniques ;
5. détecte des anomalies ;
6. upsert dans `stock_bars_daily` ;
7. met à jour le snapshot courant `cleaning_audit_latest` ;
8. historise chaque exécution dans `cleaning_audit_runs`.

### 4.4 Gestion automatique de SPY

Si `SPY` est absent de `stock_bars`, le sanitizeur peut déclencher un import ciblé pour reconstituer le calendrier de référence.

### 4.5 Enrichissement secteur

`update_sector.py` :

1. charge les symboles sans secteur ;
2. appelle Finnhub ;
3. renseigne `stock_metadata.sector` ;
4. journalise `updated`, `skipped`, `failed`.

### 4.6 Snapshot latest quotes

`sync_latest_quotes.py` :

1. charge les symboles actifs/tradables ;
2. appelle les latest quotes Alpaca par batch ;
3. calcule `spread_bps` à partir du bid/ask ;
4. upsert dans `stock_quote_snapshots`.

### 4.7 Calendrier earnings

`sync_earnings_calendar.py` :

1. charge les symboles actifs/tradables ;
2. interroge Finnhub sur une fenêtre bornée ;
3. normalise `earnings_date` et métadonnées associées ;
4. upsert dans `stock_earnings_calendar`.

---

## 5. Pourquoi le module peut échouer ou produire peu de données

### 5.1 Import Alpaca incomplet

Causes probables :

1. credentials Alpaca absents ;
2. rate limit ou timeout ;
3. symbole sans bars ;
4. données invalides sur certaines lignes.

### 5.2 Sanitizeur incomplet

Causes probables :

1. `stock_bars` encore vide ;
2. `SPY` absent ;
3. schéma SQL incomplet ;
4. anomalies nombreuses ou historiques très courts.

### 5.3 Secteurs manquants persistants

Causes probables :

1. token Finnhub absent ;
2. Finnhub ne retourne pas de secteur ;
3. symboles inactifs ou peu renseignés.

### 5.4 Quotes / earnings manquants

Causes probables :

1. étapes `sync_latest_quotes` / `sync_earnings_calendar` jamais lancées ;
2. credentials Alpaca ou Finnhub absents ;
3. couverture historique insuffisante pour un backfill PIT ancien ;
4. rate limit ou retour partiel des fournisseurs.

---

## 6. Vérifications utiles

### Vérifier `stock_metadata`

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    row = conn.execute(text("SELECT COUNT(*) AS n FROM stock_metadata")).mappings().one();
    print(dict(row))'
```

### Vérifier les bornes de `stock_bars_daily`

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    row = conn.execute(text("SELECT COUNT(*) AS n, MIN(date) AS dmin, MAX(date) AS dmax FROM stock_bars_daily")).mappings().one();
    print(dict(row))'
```

### Vérifier les audits de nettoyage en échec

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, status, last_sync_date, latest_run_at, error_message FROM cleaning_audit_latest WHERE status = \"failed\" ORDER BY latest_run_at DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

---

## 7. Tests

### Tests ciblés data integrity

```powershell
python -m pytest tests/test_import_alpaca_assets.py tests/test_import_alpaca_bar.py tests/test_data_sanitizer_daily.py tests/test_update_sector.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. importer les actifs ;
2. importer les bars ;
3. lancer le sanitizeur ;
4. enrichir les secteurs ;
5. lancer `screener` ;
6. synchroniser quotes et earnings ;
7. seulement ensuite lancer `selector` et la suite du pipeline.

### Séquence recommandée

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.import_alpaca_bar
python -m dataIntegrityEngine.data_sanitizer_daily
python -m dataIntegrityEngine.update_sector
python -m screener.stock_screener --chunk-size 500 --max-workers 8
python -m dataIntegrityEngine.sync_latest_quotes
python -m dataIntegrityEngine.sync_earnings_calendar
```

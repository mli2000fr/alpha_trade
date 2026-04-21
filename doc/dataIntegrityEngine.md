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
- `cleaning_audit_log`
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
3. appelle Alpaca avec `adjustment="all"` ;
4. upsert les barres dans `stock_bars` ;
5. marque `bars_available=False` si aucun historique n'est récupérable.

### 4.3 Sanitizeur daily

`DataSanitizer` :

1. charge les bars 1D brutes ;
2. reconstruit un calendrier daily à partir de `SPY` ;
3. forward-fill les jours manquants ;
4. calcule `daily_return` et autres features techniques ;
5. détecte des anomalies ;
6. upsert dans `stock_bars_daily` ;
7. met à jour `cleaning_audit_log`.

### 4.4 Gestion automatique de SPY

Si `SPY` est absent de `stock_bars`, le sanitizeur peut déclencher un import ciblé pour reconstituer le calendrier de référence.

### 4.5 Enrichissement secteur

`update_sector.py` :

1. charge les symboles sans secteur ;
2. appelle Finnhub ;
3. renseigne `stock_metadata.sector` ;
4. journalise `updated`, `skipped`, `failed`.

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
    rows = conn.execute(text("SELECT symbol, status, last_sync_date, updated_at FROM cleaning_audit_log WHERE status = \"failed\" ORDER BY updated_at DESC LIMIT 20")).mappings().all();
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
5. seulement ensuite lancer `screener` et la suite du pipeline.

### Séquence recommandée

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.import_alpaca_bar
python -m dataIntegrityEngine.data_sanitizer_daily
python -m dataIntegrityEngine.update_sector
```

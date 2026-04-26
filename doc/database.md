# Database — Guide d'usage

## Objectif

Ce document résume le rôle du module `database/` et les usages utiles pour :

- centraliser la connexion SQLAlchemy au schéma `alpha_trade`,
- exposer quelques helpers d'accès aux tables clés,
- supporter les pipelines d'ingestion, nettoyage et enrichissement,
- structurer les schémas SQL du projet par domaine métier.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `database/connection.py` | URL DB, engine SQLAlchemy, session factory |
| `database/assets.py` | Helpers sur `stock_metadata` et sync des actifs Alpaca |
| `database/bar_metadata.py` | Métadonnées timeframe et helpers historiques |
| `database/sanitizer_db_ops.py` | Opérations SQL pour le sanitizer daily |
| `database/sql/stock/` | Tables marché / scores / audit cleaning |
| `database/sql/news/` | Tables news / sentiment / checkpoints |
| `database/sql/ml/` | Tables registre ML, metrics, predictions |
| `database/sql/risk/` | Tables décisions de risque et cibles portefeuille |
| `database/sql/execution/` | Tables d'exécution et snapshots broker |
| `database/sql/corporate_actions/` | Tables corporate actions, applications, ledger cash |
| `database/sql/migration_add_account_id.sql` | Migration support multi-comptes |
| `database/sql/truncate_all_tables.sql` | Script utilitaire de purge |

---

## 2. Prérequis

### 2.1 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

### 2.2 Hypothèses du module

Par défaut, `database.connection` cible :

- host : `localhost`
- base : `alpha_trade`
- dialecte : `mysql+pymysql`
- charset : `utf8mb4`

### 2.3 Pool SQLAlchemy

Le moteur est créé avec une configuration adaptée au projet :

- `pool_pre_ping=True`
- `pool_recycle=3600`
- `pool_size=2`
- `max_overflow=3`

---

## 3. Usages utiles

### Obtenir l'URL de connexion

```powershell
python -c 'from database.connection import get_database_url; print(get_database_url())'
```

### Tester la création de l'engine

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; print(get_sqlalchemy_engine())'
```

### Lister les symboles actifs sans secteur

```powershell
python -c 'from database.assets import get_symbols_missing_sector; print(get_symbols_missing_sector(limit=10))'
```

### Synchroniser les actifs Alpaca via les helpers DB

```powershell
python -c 'from database.assets import sync_assets_from_alpaca; print(sync_assets_from_alpaca())'
```

---

## 4. Ce que fait le module

### 4.1 Connexion partagée

`connection.py` fournit :

- `get_database_url()`
- `get_sqlalchemy_engine()`
- `get_session_factory()`
- `SessionLocal()`

Ces éléments sont utilisés par presque tous les modules du projet.

### 4.2 Helpers `assets.py`

Le fichier `assets.py` couvre principalement :

- la réflexion de `stock_metadata`,
- le chargement des symboles sans secteur,
- la mise à jour `sector`,
- l'upsert des actifs Alpaca,
- le marquage `bars_available=False`.

### 4.3 Helpers `bar_metadata.py`

`bar_metadata.py` formalise notamment :

- l'énumération `TimeFrame`,
- la conversion API ↔ valeur DB,
- quelques helpers historiques sur `stock_bars`.

### 4.4 Helpers `sanitizer_db_ops.py`

Ce fichier encapsule la plomberie SQL du sanitizeur :

- chargement des bars bruts,
- chargement des audits,
- récupération des bornes de dates,
- upsert dans `stock_bars_daily`,
- écriture dans `cleaning_audit_latest` (snapshot courant),
- écriture append-only dans `cleaning_audit_runs` (historique des runs).

---

## 5. Pourquoi la couche database peut échouer

### 5.1 Variables d'environnement absentes

`get_database_url()` lève une erreur si `LOGIN_DB` ou `PASSWORD_DB` ne sont pas définis.

### 5.2 Schéma incomplet

Causes fréquentes :

1. certaines tables SQL non créées ;
2. migrations non appliquées ;
3. colonnes attendues absentes, par exemple `stock_metadata.sector` ou `account_id` sur les tables multi-comptes.

### 5.3 Contexte MySQL non conforme

Causes probables :

1. mauvaise base ;
2. mauvais host ;
3. droits SQL insuffisants ;
4. serveur indisponible.

---

## 6. Vérifications utiles

### Vérifier quelques tables clés

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
queries = [
    "SELECT COUNT(*) AS n FROM stock_metadata",
    "SELECT COUNT(*) AS n FROM stock_bars_daily",
    "SELECT COUNT(*) AS n FROM stock_scores"
]
with engine.connect() as conn:
    for q in queries:
        print(dict(conn.execute(text(q)).mappings().one()))'
```

### Vérifier les dossiers SQL disponibles

```powershell
Get-ChildItem "C:\Users\PC MLI\PycharmProjects\alpha_trade\database\sql"
```

---

## 7. Tests

### Tests ciblés database

```powershell
python -m pytest tests/test_connection.py tests/test_assets.py tests/test_sanitizer_db_ops.py tests/test_tables.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. valider les variables DB ;
2. créer / migrer les tables SQL ;
3. vérifier `stock_metadata`, `stock_bars_daily` et `stock_scores` ;
4. seulement ensuite exécuter les modules métier.

### Séquence recommandée

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; print(get_sqlalchemy_engine())'
Get-ChildItem "C:\Users\PC MLI\PycharmProjects\alpha_trade\database\sql"
```

---

## 9. Migrations Alembic

> Phase 1 du refactor (`prompt/refactor/plan.md`) — Alembic devient progressivement
> la **source de vérité** du schéma SQL ; les fichiers `database/sql/*.sql` restent
> utiles pour les installations *from scratch* mais doivent être maintenus en
> miroir des migrations.

### Lancer une migration

```powershell
$env:LOGIN_DB = "..."; $env:PASSWORD_DB = "..."
alembic upgrade head
```

### Ajouter une nouvelle migration

1. Choisir un identifiant `NNNN_short_description` cohérent avec la dernière
   révision listée dans `alembic/versions/`.
2. Créer le fichier `alembic/versions/NNNN_<slug>.py` avec :

   ```python
   from alembic import op
   import sqlalchemy as sa

   revision = "NNNN_short_description"
   down_revision = "<previous_revision_id>"
   branch_labels = None
   depends_on = None

   def upgrade() -> None:
       # idempotent : utiliser inspect() pour vérifier l'existence
       ...

   def downgrade() -> None:
       ...
   ```

3. Mettre à jour le fichier `database/sql/<domain>/<table>.sql` correspondant
   pour qu'une installation *from scratch* obtienne le même schéma.
4. Ajouter / mettre à jour les tests d'intégration (`tests/test_database_*.py`).
5. Lancer `alembic upgrade head` puis `pytest -q --no-cov`.

### Politique de prix (Phase 1)

La convention canonique du projet est `data_adjustment = 'split'`
(les splits sont neutralisés, les dividendes sont comptabilisés via le ledger
`portfolio_cash_ledger`). La contrainte SQL `chk_bars_adj` /  `chk_daily_adj`
matérialise cette règle sur `stock_bars` / `stock_bars_daily`.

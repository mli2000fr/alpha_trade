# Audit — `database`

> Périmètre : `database/connection.py`, `database/assets.py`, `database/bar_metadata.py`,
> `database/sanitizer_db_ops.py`, `database/selector_reference.py`, `database/stock_scores.py`,
> `database/run_business_summaries.py`, `database/sql/**`, `alembic/`.
> Sources : `doc/database.md`, `pyproject.toml`, README, code listé.

---

## 1. Résumé exécutif

Le module `database/` est la **couche de persistance unique** du projet : MySQL via
SQLAlchemy Core + pymysql, organisée par domaines (`stock/`, `news/`, `ml/`, `risk/`,
`execution/`, `corporate_actions/`). Pool 2+3 connexions, `pre_ping`, recycle 1 h.
Migrations Alembic présentes mais limitées à `0002_add_account_id`.

État global : **fondations correctes mais infrastructure basse** par rapport au reste
du projet. Pas d'ORM, pas de metadata reflective formelle, des helpers SQL inline dans
chaque module métier. La cohérence transactionnelle est laissée à la responsabilité de
chaque appelant. Pas de gestion de schéma centralisée (le DDL vit dans `sql/` à plat,
le bootstrap se fait via `all_tables.py`).

Principaux risques :

1. **Pas de versioning de schéma effectif** : Alembic est présent mais n'a qu'une seule
   migration de production (`0002`). Le schéma réel est dans `sql/*.sql` et n'est pas
   joué par Alembic. **Risque critique** : pas de garantie que l'env d'un dev / prod est
   à jour.
2. **Secrets DB en clair dans `config.yaml`** (`user: user`, `password: pass`) — c'est
   pire que les variables d'env, parce qu'on risque le commit accidentel.
3. **Pas de TLS DB par défaut** (mentionné dans `DOC_TECHNIQUE.md` §6) ; en prod live,
   secrets traversent le réseau en clair.
4. **Pool très petit** (`pool_size=2, max_overflow=3`) — borné à 5 connexions. Le
   `screener` utilise un `ProcessPoolExecutor` avec `max_workers` souvent 8 → chaque
   worker recrée son propre engine, ce qui marche par accident plutôt que par design.
5. **Pas de contrainte `CHECK` ou ENUM stricte** sur les états critiques
   (`history_status`, `execution_runs.status`, `risk_decisions.decision`) — risque de
   valeurs orphelines.
6. **Helpers d'accès dispersés** : `database/assets.py`, `database/sanitizer_db_ops.py`,
   `database/selector_reference.py`, `database/stock_scores.py`, plus chaque module a son
   propre `db_io.py` (`screener/db_io.py`, `event_sentiment/db_io.py`, etc.). Pas de
   "façade" unique → la connaissance du schéma est diluée.

Priorités immédiates :
- Faire en sorte qu'Alembic soit la **seule source de vérité du schéma** (jouer
  rétroactivement les `.sql` existants en migrations).
- Sortir les secrets de `config.yaml` (placeholders `${VAR}` partout).
- Activer SSL DB côté connection si la cible est distante.

---

## 2. Constat détaillé par composant

### 2.1 `connection.py` — engine et session

| Item | Détail |
|---|---|
| Constat | Pool `2+3`, `pool_pre_ping`, `pool_recycle=3600`, charset `utf8mb4`. Lecture des credentials depuis `LOGIN_DB`/`PASSWORD_DB`. |
| Risque | **Performance / scalabilité** : pool minuscule. Un workflow IHM qui lance plusieurs steps en parallèle, ou un `ProcessPoolExecutor` du screener avec 8 workers, contourne le pool en créant N engines distincts (un par process) → comportement non maîtrisé. |
| Risque 2 | Pas de paramètre TLS / `ssl_disabled=False`. En localhost OK, en prod live (RDS, etc.) c'est un trou. |
| Risque 3 | `get_database_url()` lève si `LOGIN_DB`/`PASSWORD_DB` manquent — pas d'option de fallback `config.yaml.database.user`, alors que `config.yaml` a déjà ce bloc → incohérence. |
| Recommandation | (a) Externaliser `pool_size` / `max_overflow` via env (`DB_POOL_SIZE`) ; (b) ajouter une option `DB_SSL_CA_PATH` qui injecte `connect_args={"ssl": {...}}` ; (c) lire d'abord `config.yaml.database`, fallback `LOGIN_DB`/`PASSWORD_DB` pour homogénéiser ; (d) ajouter un test qui vérifie que `pool_pre_ping` est bien activé. |

### 2.2 `assets.py` — helpers `stock_metadata`

| Constat | Centralise `build_eligible_stock_metadata_filters()` ; piloté par `history_status`. Bien testé. |
| Risque | **Maintenabilité** : la logique d'éligibilité est dupliquée implicitement dans `screener/db_io.py` (préselection SQL) et dans `selector/alpha_scanner.py`. Tout changement d'éligibilité doit être appliqué partout. |
| Recommandation | Extraire dans `core/eligibility.py` une fonction unique consommée par les trois appelants. |

### 2.3 `bar_metadata.py` — `TimeFrame`

| Constat | Enum strict, validation au niveau `dataIntegrityEngine`. Migré vers `sqlalchemy.text()` (cf dette technique DOC_TECHNIQUE). |
| Recommandation | Ajouter `__slots__` ou figer la liste `SUPPORTED_DATA_INTEGRITY_TIMEFRAMES` au niveau type Literal pour éviter l'erreur runtime. |

### 2.4 `sanitizer_db_ops.py`

| Constat | Encapsule l'I/O sanitizer. Couplé à `stock_bars_daily`, `cleaning_audit_*`, `stock_scores`. |
| Risque | **Cohérence transactionnelle** : `commit_every=50` réalise un commit batch ; en cas de crash entre deux commits, on a un état partiel sans trace claire. |
| Recommandation | Ajouter un champ `run_id` sur `cleaning_audit_runs` pour pouvoir rollback logique ou identifier les batchs partiels. |

### 2.5 `sql/` — bundle DDL

| Constat | Organisé par domaine (`stock/`, `news/`, `ml/`, `risk/`, `execution/`, `corporate_actions/`), avec `migration_add_account_id.sql` et `truncate_all_tables.sql`. Bootstrap via `all_tables.py`. |
| Risque critique | **Pas de versioning** : ces fichiers évoluent au fil du temps sans diff Alembic. Un environnement créé il y a 6 mois et un environnement créé aujourd'hui n'ont pas le même schéma sans intervention manuelle. |
| Risque 2 | Les fichiers `execution_orders.sql` et `execution_fills.sql` sont obsolètes (cutover canonique) — ils existent toujours dans le repo mais ne sont plus utilisés. Source de confusion. |
| Recommandation | (a) Convertir l'intégralité de `sql/*.sql` en migrations Alembic baseline `0001_initial_schema.py` (script Python qui exécute les `.sql` actuels) ; (b) supprimer ou archiver `execution_orders.sql`/`execution_fills.sql` ; (c) ajouter une CI qui contrôle qu'`alembic upgrade head` produit le même schéma que la concaténation des `.sql`. |

### 2.6 `alembic/`

| Constat | `alembic.ini` + `alembic/env.py` + `alembic/versions/` (1 migration : ajout `account_id`). |
| Risque | Présence d'Alembic donne l'illusion d'un versioning, mais 95 % du schéma reste hors Alembic. |
| Recommandation | Voir 2.5. |

### 2.7 Tables critiques — vue d'ensemble

- **Cohérence** : aucune contrainte `CHECK` répertoriée dans la doc, alors que MySQL 8 les supporte. Beaucoup de colonnes de statut sont des `VARCHAR` libres (`history_status`, `status`, `decision`, `event_type`).
- **Indexation** : pas mentionnée dans la doc. À vérifier sur le code SQL — typiquement
  les requêtes du selector et de l'execution_engine font des `WHERE symbol = ? AND
  trade_date = ?` qui demandent un index composite.
- **`account_id`** : ajouté sur les tables impactées via la migration 0002. Pas de FK
  vers une table de référence des comptes (acceptable car la source de vérité est
  `config.yaml` / env).

---

## 3. Risques prioritaires

### Critique
- **Schéma non versionné Alembic** → divergences silencieuses entre environnements.
- **Secrets DB en clair dans `config.yaml`** committé.

### Élevé
- Pool DB très petit (`2+3`) face au parallélisme du screener / ML / IHM.
- Pas de TLS DB par défaut.
- Pas de contraintes SQL strictes sur les enums métier.

### Modéré
- Helpers d'accès dispersés → connaissance du schéma diluée.
- Fichiers `sql/` obsolètes encore présents (execution legacy).
- `commit_every=50` du sanitizer sans `run_id` traçable.

### Faible
- Incohérence : `config.yaml` contient un bloc `database` non lu.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

Le module n'ingère pas directement Alpaca. Impact indirect :

- volumétrie `stock_bars_daily` cohérente avec ce que IEX renvoie (sous-évalué) ;
- la table `stock_quote_snapshots` est *l'épicentre* des biais IEX (cf. audit
  `dataIntegrityEngine`).

Côté schéma, **rien ne distingue** une donnée IEX d'une donnée consolidée. Si une
seconde source venait croiser (Stooq, Yahoo), il faudrait :
- ajouter `data_source VARCHAR(16)` sur `stock_bars_daily` et/ou `stock_quote_snapshots` ;
- ajouter `data_provenance ENUM('alpaca_iex', 'stooq', 'yahoo', 'consolidated')`.

À envisager **dès la réinitialisation prévue** de la base.

---

## 5. Choix recommandé `split_adjusted` vs `all`

Position côté DB : **conserver `split_adjusted`** + matérialiser ce choix dans le schéma :

```sql
ALTER TABLE stock_bars_daily
  ADD CONSTRAINT chk_data_adjustment CHECK (data_adjustment = 'split');
ALTER TABLE stock_bars
  ADD COLUMN data_adjustment VARCHAR(16) NOT NULL DEFAULT 'split';
ALTER TABLE stock_bars
  ADD CONSTRAINT chk_bars_data_adjustment CHECK (data_adjustment = 'split');
```

Cela rend impossible (sans modification explicite et testée) de mélanger des séries
dans la base.

---

## 6. Quick wins

1. **Sortir `user`/`password` clairs de `config.yaml`** : remplacer par
   `${LOGIN_DB}` / `${PASSWORD_DB}`.
2. **Augmenter le pool** via env : `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10`.
3. **Ajouter `CHECK` SQL** sur les énums critiques (statuts execution, history_status).
4. **Supprimer / archiver** `execution_orders.sql`, `execution_fills.sql`.
5. **Ajouter un `data_source VARCHAR` sur `stock_bars_daily`** (préparation cross-source).
6. **Centraliser `build_eligible_stock_metadata_filters`** dans `core/`.
7. **Ajouter `chk_data_adjustment`** côté DDL.
8. **Tester le `pool_pre_ping`** (test unitaire sur l'engine).

## 7. Recommandations structurelles

1. **Faire d'Alembic la source de vérité** :
   - migration baseline `0001_initial_schema` qui matérialise le schéma actuel ;
   - cycle CI obligatoire `alembic upgrade head` avant les tests ;
   - documenter dans `README.md` que le bootstrap se fait via Alembic, pas via `all_tables.py`.
2. **Activer TLS DB** côté connexion (`ssl_ca`, `ssl_verify_cert`).
3. **Refactor "façade"** : créer `database/repositories/` avec `BarsRepository`,
   `ScoresRepository`, `ExecutionRepository`, `RiskRepository` — chaque module ne consomme
   plus le SQL en direct.
4. **Introduire un audit transactionnel** : table `db_audit_log(run_id, table_name,
   operation, row_count, started_at, finished_at, status)` alimentée par les helpers,
   utile pour debug post-mortem.
5. **Évaluer `mysql-connector-python`** avec C-extension comme alternative à `pymysql`
   pour les volumes du sanitizer (gain perf 2-3×).
6. **Profiler les requêtes critiques** : ajouter `EXPLAIN` automatique en mode `--debug`,
   et un test de non-régression sur les plans d'exécution des requêtes du selector.

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 4, 7 (faible risque, fort effet).
- Activation TLS DB en option.
- Documentation : "comment ajouter une migration".

### Moyen terme
- Migration baseline Alembic ; CI obligatoire `alembic upgrade head`.
- Refactor `core/eligibility.py`.
- Ajout `data_source` sur tables marché.
- Tests `testcontainers[mysql]` (déjà dans `requirements.txt`).

### Long terme
- Façade `repositories/` complète, chaque module métier devient agnostique du SQL.
- Audit transactionnel SQL.
- Évaluation perf `mysql-connector-python` ou même PostgreSQL si la volumétrie justifie.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- `tests/test_connection.py`, `test_assets.py`, `test_sanitizer_db_ops.py`, `test_tables.py`
  existent. **Manquent** :
  - tests d'intégration MySQL réel via `testcontainers` (jamais activés en CI à voir).
  - test de non-régression Alembic (`alembic upgrade head` puis `downgrade base` sans erreur).
  - test des plans d'exécution des requêtes critiques (selector / execution).

### Monitoring
- Pas de métrique exposée. Ajouter :
  - `db_pool_in_use` / `db_pool_overflow` dans les logs périodiques ;
  - durée moyenne des batchs sanitizer / screener (déjà partiel via `run_summary`).

### Documentation
- `doc/database.md` est correct mais minimal. **Manque** :
  - guide "ajouter une nouvelle table" (avec template Alembic).
  - documentation explicite de la stratégie de versioning (Alembic vs `sql/`).
  - mapping table ↔ module producteur ↔ modules consommateurs (matrice utile pour
    impact analysis).



---

## Statut Phase 2.2 (refactor) � termine

- database/repositories/ : facade typee (AssetsRepository, BarsRepository, QuotesRepository, RunSummariesRepository, ScoresRepository) corrige en Phase 2.2.
- Pool SQLAlchemy elargi (DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_RECYCLE_SECONDS via env) corrige en Phase 2.2.
- DB_SSL_CA_PATH (TLS optionnel via PyMySQL connect_args) corrige en Phase 2.2.
- testcontainers[mysql] ajoute a requirements-dev.txt (CI Phase 2.2).

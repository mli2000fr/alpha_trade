# Sprint 6 — Connecteur Tushare et staging brut CN

## 1. Statut au 21 septembre 2026

Le Sprint 6 est **implémenté et validé structurellement**, mais son gate final reste :

```text
READY_BLOCKED_TUSHARE_TOKEN
```

La base physique `alpha_trade_cn`, les migrations, le client Tushare, le stockage brut,
la reprise, les batchs, les tests et les audits sont opérationnels. Le smoke synthétique
réellement exécuté sur MySQL est `PASS`. En revanche, aucune donnée fournisseur n'a été
collectée parce que la variable `TUSHARE_TOKEN` n'est pas configurée. Les batchs CN restent
donc volontairement désactivés.

Ce statut n'est pas un échec technique. Il empêche simplement de déclarer un faux GO sans
avoir mesuré les droits réels du compte, les quotas, la pagination et la qualité des réponses.

## 2. Périmètre et règle de sécurité

Le Sprint 6 ne publie aucune donnée dans les tables canoniques. Son flux est strictement :

```text
Tushare API
   │
   ├── client HTTP, token, retry et quota
   │
   ├── preuve brute immuable par run/page
   │       tushare_raw_payloads
   │
   ├── adaptation typée et versionnée
   │       tushare_staging_rows
   │
   └── contrôles et lineage
           cn_ingestion_runs
           cn_staging_quality_metrics

                  ╳ aucune publication canonique au Sprint 6
```

La normalisation vers les instruments, séances et barres communes appartient au Sprint 7.

## 3. Isolation physique des bases

Le routage est déclaré dans `config/databases.yaml` :

| Alias | Base | Marchés autorisés | Variables dédiées |
|---|---|---|---|
| `us_primary` | `alpha_trade` | `US_EQ` | `DB_NAME`, `DB_HOST`, `LOGIN_DB`, `PASSWORD_DB` |
| `cn_primary` | `alpha_trade_cn` | `CN_A`, `CN_BJ` | `DB_NAME_CN`, `DB_HOST_CN`, `LOGIN_DB_CN`, `PASSWORD_DB_CN` |

Pour faciliter le démarrage local, les identifiants CN retombent sur `LOGIN_DB` et
`PASSWORD_DB` si leurs variantes `_CN` sont absentes. Le nom de base ne retombe jamais
silencieusement sur la base US.

`database/router.py` impose deux gardes :

1. le marché demandé doit appartenir à l'allowlist de la route ;
2. après connexion, `SELECT DATABASE()` doit correspondre exactement à la base attendue.

Un batch `CN_A` ne peut donc pas cibler `us_primary`, et inversement.

## 4. Migrations et schéma de staging

La Chine possède son historique Alembic indépendant :

```text
alembic_cn.ini
alembic_cn/env.py
alembic_cn/versions/0001_tushare_raw_staging.py
alembic_cn/versions/0002_tushare_raw_run_lineage.py
```

Révision appliquée : `0002_tushare_raw_run_lineage`.

Les SQL de référence sont conservés dans `database/sql/cn/`.

### `cn_ingestion_runs`

Une ligne par exécution : batch, marché, route, fournisseur, dates, statut, compteurs,
consommation de quota, erreur et détails JSON. C'est la source de vérité opérationnelle.

### `tushare_raw_payloads`

Une preuve brute par run, endpoint, requête et page. La clé d'unicité inclut `run_id` : deux
exécutions identiques gardent donc chacune la preuve de ce que le fournisseur a renvoyé.

Champs structurants :

- endpoint et hash de requête ;
- clé de page et hash de réponse ;
- statut HTTP et code fournisseur ;
- `observed_at`, `available_at`, `source_revision` ;
- payload JSON complet ;
- `run_id`.

Le token est remplacé par `***` dans la requête persistée.

### `tushare_staging_rows`

Vue ligne-à-ligne adaptée mais encore fournisseur-spécifique :

- symbole Tushare et clé métier ;
- date métier ;
- code marché, place et board ;
- prix, volume, montant, facteur d'ajustement et limites ;
- statut, dates de cotation/radiation et motif ;
- hash de payload et payload ligne ;
- timestamps PIT et référence vers la preuve brute.

La déduplication métier utilise endpoint + entité + date/révision + hash. Une réponse
strictement identique n'ajoute pas une nouvelle ligne métier. Une correction modifiant le
payload crée une nouvelle révision, sans écraser l'ancienne.

### `cn_staging_quality_metrics`

Résultats des contrôles de présence et de fraîcheur par endpoint. Ce batch ne collecte rien.

## 5. Endpoints P0 couverts

| Besoin | Endpoint Tushare | Batch |
|---|---|---|
| Titres cotés, délistés et en attente | `stock_basic` | `cn_master_calendar_sync` |
| Changements de nom et historique ST | `namechange` | `cn_master_calendar_sync` |
| Calendriers SSE, SZSE et BSE | `trade_cal` | `cn_master_calendar_sync` |
| OHLCV quotidien | `daily` | `cn_daily_market_data_sync` |
| Facteurs d'ajustement | `adj_factor` | `cn_daily_market_data_sync` |
| Benchmarks | `index_daily` | `cn_daily_market_data_sync` |
| Suspensions et reprises | `suspend_d` | `cn_status_limits_sync` |
| Limites de prix quotidiennes | `stk_limit` | `cn_status_limits_sync` |

`index_weight` est déjà décrit par le client pour permettre un futur historique de
constituants. Il n'est pas activé avant vérification des droits du compte. Une classification
sectorielle Tushare ne doit pas être déclarée disponible avant le smoke réel correspondant.

## 6. Symboles et marchés

Le parseur exige six chiffres suivis de `.SH`, `.SZ` ou `.BJ`. Les zéros initiaux sont
conservés. Les codes sont classés en Shanghai Main, Shenzhen Main, STAR, ChiNext ou Beijing.

Exemples du smoke contractuel :

```text
600000.SH  Shanghai Main
000001.SZ  Shenzhen Main
688001.SH  STAR
300750.SZ  ChiNext
430047.BJ  Beijing
```

Les cas ST, suspendu, délisté, IPO et corporate action sont décrits dans
`config/univers_cn/smoke_sprint6_cn.yaml`. Certains doivent être sélectionnés dynamiquement
sur la période du smoke afin d'éviter qu'un symbole historique devenu inadapté invalide le test.

## 7. Client, quota et retry

Le connecteur appelle directement `https://api.tushare.pro` avec `requests`. Le SDK Tushare
n'est pas une dépendance du cœur applicatif.

Le contrat comprend :

- token chargé uniquement depuis l'environnement ;
- empreinte SHA-256 courte pour le lineage, jamais le secret ;
- budget maximal par minute et par run ;
- retries bornés sur timeout, erreur réseau, HTTP 429 et HTTP 5xx ;
- erreur d'authentification bloquante et non retentée ;
- validation stricte de la forme `fields/items` ;
- pagination bornée ;
- page vide traitée comme fin normale.

Valeurs initiales de `batch_cn.yaml` : 180 appels/minute, 10 000 appels/run et pages de
5 000 lignes. Ce sont des garde-fous applicatifs, pas une affirmation sur les droits du futur
abonnement. Les valeurs devront être recalées après le smoke réel.

## 8. Reprise et idempotence

Chaque job conserve un état atomique sous `artifacts/cn/tushare/state/`. La clé de reprise
inclut :

- endpoint ;
- variante d'appel ;
- date de début ;
- date de fin ;
- offset courant ;
- statut.

Ainsi, relancer exactement le même scope saute les variantes terminées ; étendre la date de
fin crée un scope distinct et collecte les nouvelles dates. L'écriture passe par un fichier
temporaire remplacé atomiquement.

Le smoke MySQL a prouvé le scénario suivant :

| Run | Close reçu | Preuve brute | Ligne métier persistée |
|---|---:|---:|---:|
| 1 | 10,60 | 1 | 1 |
| 2 | 10,60 identique | 1 | 0 |
| 3 | 10,70 corrigé | 1 | 1 |

Résultat : 3 preuves de réception, 2 versions métier, aucune ligne canonique.

## 9. Batchs et planification

Les cinq jobs sont dans `batch_cn.yaml` et sont **désactivés par défaut** :

1. `cn_master_calendar_sync` ;
2. `cn_daily_market_data_sync` ;
3. `cn_status_limits_sync` ;
4. `cn_historical_backfill` ;
5. `cn_staging_quality_daily`.

Le lanceur CN réutilise le mécanisme commun de logs, compteurs, fenêtre cachée et
notifications mail/Telegram. Les compteurs partiels sont conservés même si une page ultérieure
échoue.

Les wrappers Windows sont :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\cn_ingestion_launcher.ps1 -BatchName cn_master_calendar_sync -Force
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_cn_ingestion_task.ps1 -BatchName cn_master_calendar_sync
```

`-Force` autorise un smoke manuel mais ne contourne jamais `canonical_writes_enabled=false`.

## 10. Bootstrap et audit

Création et migration :

```powershell
python -m service.tushare.bootstrap_database --create --upgrade --audit
```

Smoke synthétique idempotence/correction :

```powershell
python scripts/smoke_sprint6_cn.py
```

Audit du gate :

```powershell
python scripts/audit_sprint6_cn.py
```

Les preuves sont écrites sous :

```text
artifacts/audits/market_integration/sprint_06/
```

## 11. Procédure de déblocage avec un token

1. Définir `TUSHARE_TOKEN` dans l'environnement utilisateur ou machine.
2. Ouvrir un nouveau terminal afin que la variable soit chargée.
3. Ne pas activer les tâches planifiées.
4. Lancer les smokes réels avec une période courte :

```powershell
python -u -m dataIntegrityEngine.cn_ingestion --job cn_master_calendar_sync --force --start-date 2026-09-01 --end-date 2026-09-21
python -u -m dataIntegrityEngine.cn_ingestion --job cn_daily_market_data_sync --force --start-date 2026-09-14 --end-date 2026-09-21
python -u -m dataIntegrityEngine.cn_ingestion --job cn_status_limits_sync --force --start-date 2026-09-14 --end-date 2026-09-21
```

5. Contrôler les compteurs, payloads et catégories du smoke.
6. Mesurer les appels et les droits endpoint par endpoint.
7. Enregistrer la revue dans `real_provider_smoke.json` avec `status: PASS` uniquement si tous
   les cas obligatoires sont vérifiés.
8. Relancer `scripts/audit_sprint6_cn.py`.
9. Activer ensuite, et seulement ensuite, les jobs acceptés dans `batch_cn.yaml`.

Ne pas lancer le backfill 2010–présent avant cette mesure : il pourrait consommer inutilement
le quota ou échouer sur un endpoint non autorisé.

## 12. Tests et preuves

La suite dédiée couvre :

- routage et refus cross-market ;
- token absent et token invalide ;
- quota et HTTP 429/5xx ;
- schéma fournisseur malformé ;
- page vide et reprise inter-run ;
- symboles, zéros initiaux, boards et caractères chinois ;
- dates et décimaux ;
- hash canonique stable ;
- migration et interdiction des tables canoniques ;
- configuration sûre par défaut ;
- launchers Windows et notifications ;
- conservation des compteurs partiels en échec.

Le résultat structurel actuel est :

```text
base alpha_trade_cn             PASS
révision Alembic 0002           PASS
tables attendues                4/4
tables canoniques interdites    0
écritures canoniques            0
smoke synthétique MySQL         PASS
smoke fournisseur réel          BLOQUÉ — token absent
```

## 13. Hors périmètre volontaire

Le Sprint 6 ne réalise pas :

- la résolution Tushare → `instrument_id` canonique ;
- la publication des séances ou barres ;
- l'ajustement de prix utilisable en backtest ;
- les features, labels, modèles ou prédictions CN ;
- le paper/live ;
- l'activation automatique de batchs non validés.

Ces responsabilités commencent au Sprint 7. Cette séparation garantit qu'une erreur de
mapping fournisseur ne contamine pas les datasets ou les modèles.

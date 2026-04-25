# Data Integrity Engine — documentation détaillée de reprise

## 1. Objet de ce document

Ce document décrit **en détail** le module `dataIntegrityEngine/` tel qu’il existe aujourd’hui dans le code.

Il est rédigé pour une personne qui reprend l’application et qui doit pouvoir, sans contexte oral préalable :

- comprendre le rôle exact du module dans la chaîne globale ;
- identifier les scripts à lancer et dans quel ordre ;
- savoir quelles tables SQL sont lues / écrites ;
- comprendre les invariants métier retenus ;
- diagnostiquer rapidement un run incomplet ou dégradé ;
- localiser les principaux points de maintenance et les limites connues.

> **Source de vérité** : pour ce module, la vérité fonctionnelle est le **code courant** (`dataIntegrityEngine/`, `database/`, `service/`) et les **schémas SQL actuels** dans `database/sql/`.
> Cette documentation résume cette implémentation actuelle ; elle ne doit pas être lue comme une promesse de rétrocompatibilité avec d’anciens schémas ou d’anciens lots de données.

---

## 2. Position du module dans l’architecture globale

`dataIntegrityEngine/` est la **porte d’entrée de la donnée marché exploitable** par le reste de la plateforme.

Son rôle n’est pas de produire directement des signaux de trading, mais de fournir un **socle de données propre, traçable et exploitable** pour les modules aval :

- `screener/`
- `selector/`
- `event_sentiment/`
- `risk_management/`
- `execution_engine/`
- `ihm/`

En pratique, il couvre 6 familles de tâches :

1. **importer l’univers d’actifs** depuis Alpaca ;
2. **importer l’historique de bars** daily depuis Alpaca ;
3. **nettoyer / aligner / auditer** ces bars daily ;
4. **enrichir les métadonnées fondamentales minimales** (secteur, market cap) via Finnhub ;
5. **capturer des snapshots de quotes** bid/ask ;
6. **alimenter un calendrier earnings** exploitable par les filtres aval.

Le module sert donc de **couche d’ingestion + préparation + audit**.

---

## 3. Périmètre exact du package

### 3.1 Fichiers du package

| Fichier | Rôle opérationnel |
|---|---|
| `dataIntegrityEngine/import_alpaca_assets.py` | Charge les actifs Alpaca et alimente `stock_metadata` |
| `dataIntegrityEngine/import_alpaca_bar.py` | Importe les bars OHLCV Alpaca vers `stock_bars` |
| `dataIntegrityEngine/data_sanitizer_daily.py` | Nettoie / aligne / audite les séries daily et remplit `stock_bars_daily` |
| `dataIntegrityEngine/update_sector.py` | Enrichit `stock_metadata` avec `sector` et `market_cap` via Finnhub |
| `dataIntegrityEngine/sync_latest_quotes.py` | Alimente `stock_quote_snapshots` avec les latest quotes Alpaca |
| `dataIntegrityEngine/sync_earnings_calendar.py` | Alimente `stock_earnings_calendar` via Finnhub |

### 3.2 Dépendances directes importantes

| Zone | Fichiers clés | Rôle |
|---|---|---|
| DB / SQLAlchemy | `database/connection.py` | Connexion MySQL |
| Univers d’actifs | `database/assets.py` | Filtres d’éligibilité, upserts `stock_metadata`, états `history_status` |
| Sanitizeur | `database/sanitizer_db_ops.py` | Lecture / écriture des audits et de `stock_bars_daily` |
| Références selector | `database/selector_reference.py` | Upserts quotes et earnings |
| Métadonnées timeframe | `database/bar_metadata.py` | Enum `TimeFrame`, validation du périmètre daily |
| Provider Alpaca | `service/alpaca/clientAlpaca.py` | Assets, bars, latest quotes |
| Provider Finnhub | `service/finnhub/clientFinnhub.py` | Profils société, earnings calendar |
| Logging | `common/utils.py` | Configuration des logs, date de marché |

---

## 4. Vision d’ensemble des flux

## 4.1 Flux nominal simplifié

```text
Alpaca assets
    -> stock_metadata
        -> univers éligible downstream

Alpaca bars (1D, adjustment=split)
    -> stock_bars
        -> DataSanitizer
            -> stock_bars_daily
            -> cleaning_audit_latest
            -> cleaning_audit_runs
            -> stock_scores (champs audit)

Finnhub profile
    -> stock_metadata.sector / market_cap

Alpaca latest quotes
    -> stock_quote_snapshots

Finnhub earnings calendar
    -> stock_earnings_calendar
```

## 4.2 Ordre logique recommandé

### Bootstrap d’un environnement neuf

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.import_alpaca_bar
python -m dataIntegrityEngine.data_sanitizer_daily
python -m dataIntegrityEngine.update_sector
python -m dataIntegrityEngine.sync_latest_quotes
python -m dataIntegrityEngine.sync_earnings_calendar
```

### Séquence quotidienne recommandée avant le reste du pipeline

```powershell
python -m dataIntegrityEngine.import_alpaca_bar
python -m dataIntegrityEngine.data_sanitizer_daily
python -m dataIntegrityEngine.update_sector --limit 50 --sleep-seconds 1.1 --log-every 10
python -m screener.stock_screener --chunk-size 500 --max-workers 8
python -m dataIntegrityEngine.sync_latest_quotes
python -m dataIntegrityEngine.sync_earnings_calendar
```

Puis seulement ensuite :

```powershell
python -m selector.alpha_scanner
```

### Correspondance avec l'IHM

Depuis `ihm/pages/pipeline.py`, l'orchestration opérateur est volontairement séparée en deux blocs :

- **steps auxiliaires Data Integrity hors workflow** :
  - `B1. import_alpaca_assets`
  - `B2. update_sector`
- **workflow quotidien 1→14** :
  - `1. import_alpaca_bar`
  - `2. data_sanitizer_daily`
  - `3. stock_screener`
  - `4. sync_latest_quotes`
  - `5. sync_earnings_calendar`
  - `6. alpha_scanner`
  - puis les étapes aval sentiment / ML / risk / execution / corporate actions.

Autrement dit :

- `import_alpaca_assets` et `update_sector` restent des opérations de **bootstrap / maintenance** côté IHM ;
- `sync_latest_quotes` et `sync_earnings_calendar` font bien partie du **workflow quotidien** exposé à l'opérateur ;
- la séquence CLI ci-dessus reste valable comme runbook manuel, mais elle ne doit pas être confondue avec l'ordre exact du workflow IHM 1→14.

---

## 5. Variables d’environnement et dépendances externes

## 5.1 Base de données

Le projet utilise MySQL via `database/connection.py`.

Variables minimales :

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

La base visée par défaut dans le code est `alpha_trade` sur `localhost`.

## 5.2 Alpaca

Les appels Alpaca utilisent le registre multi-comptes, avec rétrocompatibilité sur le compte par défaut.

Variables minimales usuelles :

```powershell
$env:ALPACA_API_KEY = "PK..."
$env:ALPACA_SECRET_KEY = "..."
```

**Point important pour la reprise** :
- la couche `service.alpaca.clientAlpaca` sait gérer un `account_id` ;
- mais les scripts `dataIntegrityEngine` exposent aujourd’hui très peu ce paramètre en CLI ;
- en pratique, ces scripts tournent surtout sur le **compte par défaut**.

## 5.3 Finnhub

Variables reconnues :

```powershell
$env:FINNHUB_API_KEY = "..."
```

Compatibilité historique également acceptée côté client Finnhub :

```powershell
$env:CLE_FINNHUB = "..."
```

**Comportement notable** :
- timeout géré avec retry/backoff ;
- rate limit Finnhub géré avec pause et retries ;
- `MIN_REQUEST_INTERVAL_SECONDS = 1.1` sert de base de throttling côté projet.

---

## 6. Tables SQL du périmètre

## 6.1 `stock_metadata`

**Rôle** : univers d’actifs de référence.

Colonnes importantes :
- `symbol` (PK)
- `id_alpaca`
- `company_name`
- `exchange`
- `asset_class`
- `status`
- `tradable`
- `bars_available`
- `history_status`
- `sector`
- `market_cap`
- `last_updated`

### Sémantique métier critique

`history_status` peut prendre notamment les valeurs :
- `pending`
- `ready`
- `no_history`
- `provider_error`
- `suspended_or_stale`
- `excluded_by_policy`

### Impact downstream

Le helper `build_eligible_stock_metadata_filters(...)` dans `database/assets.py` considère éligible un symbole si, quand les colonnes existent :

- `status = active`
- `tradable = true`
- `bars_available = true`
- `asset_class = us_equity`
- `history_status` est vide / null / `pending` / `ready`

**Conséquence très importante** :
un symbole marqué :
- `no_history`
- `provider_error`
- `suspended_or_stale`

sort de l’univers éligible consommé par plusieurs scripts aval.

---

## 6.2 `stock_bars`

**Rôle** : stockage brut-ish des bars Alpaca importés.

Colonnes clés :
- `symbol`
- `timeframe`
- `timestamp`
- `open_price`
- `high_price`
- `low_price`
- `close_price`
- `volume`
- `trade_count`
- `vwa_price`
- `ingested_at`

Clé d’unicité logique :
- `(symbol, timeframe, timestamp)`

### Convention de temps

Le timestamp est normalisé au fuseau **America/New_York** avant insertion.

### Convention de série de prix

Le projet choisit **`adjustment="split"`** côté Alpaca.

Cela signifie :
- les splits sont neutralisés ;
- les dividendes ne réécrivent pas l’historique de prix ;
- on conserve une série simple, cohérente avec le swing trading actions du projet.

Cette décision est cohérente avec le besoin métier exprimé dans le projet :
- pas de variantes multiples de prix dans ce module ;
- une série canonique simple pour tous les modules aval.

---

## 6.3 `stock_bars_daily`

**Rôle** : table daily propre, alignée, versionnée et consommable par le reste du pipeline.

Colonnes clés :
- `symbol`, `date` (PK)
- `open`, `high`, `low`, `close`, `volume`
- `adj_close`
- `vwap`
- `daily_return`
- `is_filled`
- `ingested_at`
- `data_adjustment`
- `last_updated`

### Invariants importants

- `adj_close = close` dans l’implémentation actuelle, car l’ingestion amont utilise déjà `adjustment="split"` ;
- `daily_return` est **la seule feature explicitement persistée** par le sanitizeur dans cette table ;
- `is_filled = 1` signale une journée reconstituée par forward-fill ;
- `data_adjustment` permet de tracer le mode d’ajustement de la série source.

---

## 6.4 `cleaning_audit_latest`

**Rôle** : snapshot courant par symbole du dernier état de nettoyage.

Colonnes clés :
- `symbol`
- `last_sync_date`
- `missing_days_count`
- `anomaly_count`
- `status`
- `error_message`
- `latest_run_at`

### Usage métier

Cette table répond à la question :
> “Quel est le dernier état connu du nettoyage daily pour ce symbole ?”

Elle est utilisée pour :
- l’incrémentalité du sanitizeur ;
- le diagnostic opérateur ;
- la synchronisation partielle avec `stock_scores`.

---

## 6.5 `cleaning_audit_runs`

**Rôle** : historique de tous les runs de nettoyage par symbole.

Colonnes clés :
- `id`
- `symbol`
- `last_sync_date`
- `missing_days_count`
- `anomaly_count`
- `status`
- `error_message`
- `created_at`

### Usage métier

Cette table répond à la question :
> “Qu’est-ce qu’il s’est passé run après run pour ce symbole ?”

Elle sert surtout à :
- l’historisation ;
- le diagnostic après incident ;
- la compréhension des symboles instables / dégradés.

---

## 6.6 `stock_scores`

Le module `dataIntegrityEngine` n’est **pas le producteur principal** de `stock_scores`, mais il met à jour certains champs d’audit :

- `anomaly_count`
- `missing_days_count`
- `sanitizer_status`
- `last_updated_audit`

### Point subtil et important

Le synchronizeur `sync_audit_to_stock_scores(...)` n’est appelé **que si de nouvelles barres ont été réellement traitées** (`was_processed=True`) ou en cas d’échec explicite.

Donc :
- si un symbole est simplement **skippé** faute de nouvelles données, on **préserve** les anciennes métriques d’audit dans `stock_scores` ;
- on évite ainsi d’écraser un état aval utile avec des zéros ou des nulls artificiels.

---

## 6.7 `stock_quote_snapshots`

**Rôle** : snapshot quotidien des quotes bid/ask.

Colonnes clés :
- `symbol`, `quote_date` (PK)
- `quote_timestamp`
- `bid_price`, `ask_price`
- `bid_size`, `ask_size`
- `spread_bps`
- `last_updated`

### Usage aval

Utilisée notamment par les filtres de spread / qualité de marché côté sélection.

---

## 6.8 `stock_earnings_calendar`

**Rôle** : calendrier earnings normalisé pour filtrage aval.

Colonnes clés :
- `symbol`, `earnings_date` (PK)
- `eps_estimate`
- `eps_actual`
- `revenue_estimate`
- `revenue_actual`
- `fiscal_period`
- `last_updated`

### Usage aval

Utilisée notamment pour le calcul / stockage de :
- `earnings_date`
- `days_to_earnings`
- `earnings_blackout`

dans les modules de scoring / sélection.

---

## 7. Scripts du module — détail opérationnel

## 7.1 `import_alpaca_assets.py`

### Objectif

Construire ou rafraîchir l’univers d’actifs de base dans `stock_metadata`.

### Code réel

Le script est volontairement très fin :
- `fetch_alpaca_assets()`
- `insert_assets_to_db(assets)`

### Effets en base

À l’insertion / upsert :
- `bars_available = True` par défaut ;
- `history_status = pending` si la colonne existe ;
- `market_cap = NULL` initialement.

### Ce que le script **ne fait pas**

Il ne :
- n’importe pas les bars ;
- n’enrichit pas le secteur ;
- ne filtre pas encore l’univers final selon la qualité historique ;
- n’expose pas de CLI détaillée.

### Commande

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
```

### Quand le lancer

- bootstrap initial ;
- rafraîchissement périodique de l’univers Alpaca ;
- après reset complet de la base.

### Résumé structuré

Le script émet désormais un résumé structuré sur stdout avec le préfixe :
- `::alpha_trade_run_summary::`

Champs notables :
- `run_id`
- `started_at`
- `finished_at`
- `duration_seconds`
- `assets_fetched`
- `rows_upserted`

---

## 7.2 `import_alpaca_bar.py`

### Objectif

Importer les bars Alpaca **daily uniquement** vers `stock_bars`, avec validation de qualité minimale et suivi d’état de disponibilité historique.

### Contrainte de périmètre

Le module `dataIntegrityEngine` supporte aujourd’hui **uniquement le timeframe daily**.

Cela est validé dans `database/bar_metadata.py` :
- `SUPPORTED_DATA_INTEGRITY_TIMEFRAMES = (TimeFrame.ONE_DAY,)`

Si on tente d’utiliser `30M`, `1H`, etc., une `ValueError` est levée.

### Fonction principale

- `import_alpaca_bars(time_frame: TimeFrame, symbols: Optional[list[str]] = None)`

### Flux détaillé

1. validation du timeframe ;
2. résolution de l’univers cible :
   - symboles passés explicitement,
   - ou univers complet via `get_active_tradable_symbols(...)` ;
3. pour chaque symbole :
   - recherche de la dernière barre connue ;
   - si déjà à jour sur la dernière date de marché : skip ;
   - sinon appel Alpaca incrémental ;
4. validation et sanitation des bars ;
5. upsert MySQL dans `stock_bars` ;
6. mise à jour de `history_status` selon le cas.

### Validation des bars

Les règles dans `_build_bar_records(...)` / `_validate_bar_business_rules(...)` rejettent notamment :
- timestamp absent ;
- prix non numériques / non finis ;
- prix hors plage raisonnable pour `DECIMAL(20,8)` ;
- OHLC incohérents ;
- volume négatif ;
- `trade_count` invalide ;
- `vwap` non positif.

### États métier produits

#### Cas 1 — succès avec nouvelles barres
- insert / upsert en base ;
- `history_status = ready`

#### Cas 2 — aucun historique confirmé par Alpaca pour un symbole absent de `stock_bars`
- `bars_available = false`
- `history_status = no_history`

#### Cas 3 — incident provider / réseau / timeout Alpaca
- `history_status = provider_error`
- **on ne bascule pas** `bars_available` à `false`

#### Cas 4 — historique existant mais trop ancien
- `history_status = suspended_or_stale`

### Staleness

Le stale check utilise en priorité le **gap en jours de bourse**, pas seulement le gap calendaire.

Seuils actuels :
- `MAX_STALENESS_CALENDAR_DAYS = 7`
- `MAX_STALENESS_TRADING_DAYS = 5`

### Choix de série de prix

Le script utilise `adjustment="split"` via le client Alpaca.

C’est la **série canonique du projet** pour le swing trading actions.

### Résumé structuré

Le script émet un résumé structuré sur stdout avec préfixe :
- `::alpha_trade_run_summary::`

Champs notables :
- `targeted_symbols`
- `existing_history_symbols`
- `first_import_symbols`
- `successful_symbols`
- `failed_symbols`
- `provider_error_symbols`
- `skipped_symbols`
- `up_to_date_symbols`
- `no_data_symbols`
- `stale_symbols`
- `inserted_bars`
- `history_status_counts`

### Commandes utiles

```powershell
python -m dataIntegrityEngine.import_alpaca_bar
```

Import ciblé depuis Python :

```powershell
python -c "from dataIntegrityEngine.import_alpaca_bar import import_alpaca_bars; from database.bar_metadata import TimeFrame; print(import_alpaca_bars(TimeFrame.ONE_DAY, symbols=['SPY','AAPL']))"
```

---

## 7.3 `data_sanitizer_daily.py`

### Objectif

Transformer `stock_bars` en série daily exploitable dans `stock_bars_daily`, avec :
- alignement sur calendrier de marché ;
- forward-fill contrôlé ;
- calcul de `daily_return` ;
- détection d’anomalies ;
- audit détaillé par symbole.

### Classe centrale

- `DataSanitizer`

### Tables utilisées

Lecture :
- `stock_bars`
- `stock_bars_daily`
- `cleaning_audit_latest`
- `stock_metadata`

Écriture :
- `stock_bars_daily`
- `cleaning_audit_latest`
- `cleaning_audit_runs`
- `stock_scores`

### Principes de conception

#### 1. Alignement sur calendrier SPY
Le calendrier de référence est reconstruit à partir de `SPY` en 1D.

#### 2. Auto-récupération SPY
Si `SPY` est absent de `stock_bars`, le sanitizeur déclenche automatiquement un import ciblé :
- `import_alpaca_bars(TimeFrame.ONE_DAY, symbols=['SPY'])`

#### 3. Rebuild glissant
Le sanitizeur ne recalcule pas strictement “depuis la dernière date”.
Il utilise un **lookback de reconstruction** :
- `REBUILD_LOOKBACK_CALENDAR_DAYS = 400`

Donc si `last_sync_date` existe, il repart environ 400 jours en arrière pour recalculer une fenêtre cohérente.

#### 4. Fill contrôlé
Les jours manquants sont forward-fill :
- `close` forward-filled ;
- `open/high/low/adj_close` remis à `close` si absents ;
- `volume = 0` pour les jours remplis ;
- `is_filled = True`

#### 5. Protection contre les séries trop dégradées
Le sanitizeur refuse une série si le nombre de jours remplis consécutifs dépasse :
- `MAX_CONSECUTIVE_FILLED_DAYS = 3`

Dans ce cas, il lève une `DataQualityError`.

#### 6. Features volontairement limitées
Le sanitizeur ne persiste explicitement que :
- `daily_return`

Il **ne persiste pas** d’autres features techniques comme volatilités, gaps, etc. ; elles sont laissées aux modules aval si nécessaire.

### Détection d’anomalies

La détection d’anomalies repose sur une logique Rolling MAD :
- fenêtre = `20`
- minimum observations = `5`
- anomalie si `abs_dev > 5 * MAD` et `|return| > 2%`

Constantes :
- `ROLLING_WINDOW_DAYS = 20`
- `ROLLING_MIN_PERIODS = 5`
- `ANOMALY_MAD_THRESHOLD = 5.0`
- `ANOMALY_RETURN_THRESHOLD = 0.02`

### Incrémentalité et commit

- `commit_every = 50` par défaut ;
- commit batch uniquement sur symboles réellement traités ;
- le résumé compte aussi `batch_commits`.

### Politique d’audit

Pour chaque symbole :
- insertion d’un enregistrement dans `cleaning_audit_runs` ;
- upsert du snapshot `cleaning_audit_latest`.

Si traitement réussi avec nouvelles données :
- mise à jour de `stock_scores` avec les compteurs d’audit.

Si le symbole est juste skippé faute de nouvelles données :
- **pas d’écrasement** de l’état antérieur de `stock_scores`.

Si échec :
- audit `failed` persisté ;
- `stock_scores` synchronisé avec l’échec ;
- `degraded_symbols` incrémenté si l’erreur est une `DataQualityError`.

### Résumé structuré

Le sanitizeur émet également un `run_summary` structuré sur stdout.

Champs notables :
- `targeted_symbols`
- `successful_symbols`
- `failed_symbols`
- `skipped_symbols`
- `degraded_symbols`
- `upserted_rows`
- `audit_rows_written`
- `batch_commits`
- `status_breakdown`
- `duration_seconds`

### Commande

```powershell
python -m dataIntegrityEngine.data_sanitizer_daily
```

### Quand soupçonner un problème

- `stock_bars` vide ou très partiel ;
- `SPY` absent ;
- séries avec grands trous ;
- trop de `failed` dans `cleaning_audit_latest` ;
- trop de `is_filled=1` dans `stock_bars_daily`.

---

## 7.4 `update_sector.py`

### Objectif

Enrichir `stock_metadata` via Finnhub.

Le nom historique du script parle de “sector”, mais l’implémentation actuelle met à jour :
- `sector`
- `market_cap`

### Fonction principale

- `update_missing_sectors(...)`

### Sélection des symboles

Le script appelle :
- `get_symbols_missing_fundamentals(...)`

Donc il cible les symboles éligibles dont :
- `sector` est vide / null,
- ou `market_cap` est null.

### Comportement

Pour chaque symbole :
- appel Finnhub profile ;
- lecture de `finnhubIndustry` ;
- lecture de `marketCapitalization` ;
- conversion de la market cap en USD (`* 1_000_000`) ;
- update SQL de `stock_metadata`.

### États fonctionnels du résumé

Le script renvoie un dictionnaire métier :
- `total`
- `updated`
- `skipped`
- `failed`

### Résumé structuré CLI

L'entrée CLI publie aussi un `run_summary` structuré standardisé sur stdout avec :
- `run_id`
- `started_at`
- `finished_at`
- `duration_seconds`
- `requested_limit`
- `sleep_seconds`
- `log_every`
- `total`
- `updated`
- `skipped`
- `failed`

### Commandes

```powershell
python -m dataIntegrityEngine.update_sector
```

Avec throttling explicite :

```powershell
python -m dataIntegrityEngine.update_sector --limit 50 --sleep-seconds 1.1 --log-every 10
```

### Remarques

- le nom du fichier est devenu un peu trompeur, car il met aussi à jour `market_cap` ;
- il existe encore des traces legacy (`get_symbols_missing_sector`) pour compatibilité tests/appelants.

---

## 7.5 `sync_latest_quotes.py`

### Objectif

Capturer un snapshot quotidien des latest quotes Alpaca pour les symboles éligibles.

### Sélection des symboles

Le script lit :
- `list_active_tradable_symbols()`

Cette liste est dérivée de `stock_metadata` via les filtres d’éligibilité.

### Comportement

- batch Alpaca (`DEFAULT_BATCH_SIZE = 200`) ;
- lecture bid / ask / tailles ;
- calcul de `spread_bps` ;
- upsert dans `stock_quote_snapshots`.

### Résumé

Le script retourne :
- `symbols`
- `rows_upserted`

### Résumé structuré CLI

- préfixe stdout : `::alpha_trade_run_summary::`
- `run_id`
- `started_at`
- `finished_at`
- `duration_seconds`
- `requested_limit`
- `batch_size`
- `symbols`
- `rows_upserted`

### Limites actuelles

- pas d’historique SQL dédié ;
- pas de paramètre `account_id` exposé en CLI ;
- snapshot par date, pas historisation intraday fine.

### Commandes

```powershell
python -m dataIntegrityEngine.sync_latest_quotes
python -m dataIntegrityEngine.sync_latest_quotes --limit 100 --batch-size 100
```

---

## 7.6 `sync_earnings_calendar.py`

### Objectif

Alimenter `stock_earnings_calendar` avec une fenêtre earnings normalisée Finnhub.

### Sélection des symboles

Même logique que `sync_latest_quotes` :
- univers éligible dérivé de `stock_metadata`.

### Fenêtre par défaut

- `from_date = aujourd’hui - 7 jours`
- `to_date = aujourd’hui + 30 jours`

### Comportement

- appel Finnhub multi-symboles ;
- normalisation des champs (`date` / `earningsDate`, EPS, revenus, quarter/fiscalPeriod) ;
- upsert dans `stock_earnings_calendar`.

### Résumé

Le script retourne :
- `symbols`
- `rows_upserted`

### Résumé structuré CLI

- préfixe stdout : `::alpha_trade_run_summary::`
- `run_id`
- `started_at`
- `finished_at`
- `duration_seconds`
- `from_date`
- `to_date`
- `requested_limit`
- `sleep_seconds`
- `symbols`
- `rows_upserted`

### Limites actuelles

- pas d’audit SQL dédié ;
- dépend fortement du throttling Finnhub.

### Commandes

```powershell
python -m dataIntegrityEngine.sync_earnings_calendar
python -m dataIntegrityEngine.sync_earnings_calendar --from-date 2026-01-01 --to-date 2026-02-15 --limit 100 --sleep-seconds 1.1
```

---

## 8. Choix de conception importants à connaître

## 8.1 Série canonique = `split`

Le projet a explicitement retenu une série de prix simple :
- **split-adjusted**,
- sans multiplier les variantes `raw` / `all` dans ce module.

C’est cohérent avec :
- un univers swing actions US ;
- le besoin de stabilité et de simplicité ;
- la volonté d’éviter la confusion entre séries concurrentes.

## 8.2 `adj_close = close`

Dans `stock_bars_daily`, `adj_close` est aujourd’hui **identique** à `close`.
Ce n’est pas une erreur : c’est une convention de compatibilité de schéma, puisque l’ajustement split a déjà été fait à l’ingestion.

## 8.3 SPY comme calendrier de marché

Le calendrier de trading quotidien est inféré depuis `SPY`.

Conséquence :
- si `SPY` manque, le sanitizeur ne peut pas aligner proprement les autres séries ;
- d’où l’auto-import ciblé de SPY.

## 8.4 Le sanitizeur est “incrémental avec reconstruction glissante”, pas purement append-only

Le projet préfère recalculer une fenêtre large (~400 jours) au lieu de ne traiter que le dernier jour.

Avantage :
- meilleure robustesse aux corrections tardives et aux trous.

Inconvénient :
- coût plus élevé qu’un append strict.

## 8.5 Les états `history_status` pilotent réellement l’univers aval

`history_status` n’est pas une simple information d’audit.
Il influence directement l’éligibilité des symboles dans plusieurs scripts.

C’est un point clé pour toute reprise :
**modifier ces états change concrètement le périmètre métier aval**.

---

## 9. Runbook opérateur / mainteneur

## 9.1 Bootstrap d’une base remise à zéro

Ordre recommandé :

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.import_alpaca_bar
python -m dataIntegrityEngine.data_sanitizer_daily
python -m dataIntegrityEngine.update_sector
python -m dataIntegrityEngine.sync_latest_quotes
python -m dataIntegrityEngine.sync_earnings_calendar
```

Contrôles immédiats :
- `stock_metadata` non vide ;
- `stock_bars` alimentée sur une profondeur crédible ;
- `stock_bars_daily` alimentée ;
- peu ou pas de `failed` dans `cleaning_audit_latest`.

## 9.2 Si `import_alpaca_bar` importe très peu de données

Vérifier :
- credentials Alpaca ;
- univers actif/tradable réel ;
- `history_status` / `bars_available` qui pourraient exclure beaucoup de symboles ;
- incidents provider (`provider_error_symbols`) ;
- symboles marqués `suspended_or_stale`.

## 9.3 Si le sanitizeur remplit trop de jours

Vérifier :
- profondeur réelle de `stock_bars` ;
- présence et qualité de `SPY` ;
- symboles en voie de suspension ou peu liquides ;
- trop grand nombre de séries avec `is_filled=1`.

## 9.4 Si secteurs / market cap restent vides

Vérifier :
- token Finnhub ;
- limitations provider ;
- symboles sans couverture Finnhub ;
- `sleep_seconds` trop agressif.

## 9.5 Si quotes / earnings sont trop pauvres

Vérifier :
- univers éligible réellement non vide ;
- symboles exclus par `history_status` ou `bars_available` ;
- credentials provider ;
- fenêtre de dates trop étroite côté earnings.

---

## 10. Commandes de diagnostic utiles

### Taille de l’univers metadata

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    print(dict(conn.execute(text('SELECT COUNT(*) AS n FROM stock_metadata')).mappings().one()))"
```

### Répartition des `history_status`

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text('SELECT history_status, COUNT(*) AS n FROM stock_metadata GROUP BY history_status ORDER BY n DESC')).mappings().all();
    print([dict(r) for r in rows])"
```

### Bornes de `stock_bars`

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    row = conn.execute(text('SELECT COUNT(*) AS n, MIN(timestamp) AS tmin, MAX(timestamp) AS tmax FROM stock_bars WHERE timeframe = \"1D\"')).mappings().one();
    print(dict(row))"
```

### Bornes de `stock_bars_daily`

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    row = conn.execute(text('SELECT COUNT(*) AS n, MIN(date) AS dmin, MAX(date) AS dmax FROM stock_bars_daily')).mappings().one();
    print(dict(row))"
```

### Audits de nettoyage en échec

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text('SELECT symbol, status, last_sync_date, latest_run_at, error_message FROM cleaning_audit_latest WHERE status = \"failed\" ORDER BY latest_run_at DESC LIMIT 20')).mappings().all();
    print([dict(r) for r in rows])"
```

### Symboles les plus remplis artificiellement

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text('SELECT symbol, SUM(is_filled) AS filled_days, COUNT(*) AS total_days FROM stock_bars_daily GROUP BY symbol ORDER BY filled_days DESC LIMIT 20')).mappings().all();
    print([dict(r) for r in rows])"
```

---

## 11. Tests utiles pour valider le module

### Batterie ciblée recommandée

```powershell
python -m pytest tests/test_import_alpaca_assets.py tests/test_import_alpaca_bar.py tests/test_data_sanitizer_daily.py tests/test_update_sector.py tests/test_data_integrity_run_summaries.py -q -o addopts=""
```

### Batterie de cohérence IHM / observabilité recommandée

```powershell
python -m pytest tests/test_ihm_pipeline_runner.py tests/test_pages_overview.py tests/test_pages_screening.py tests/test_ihm_process_registry.py -q -o addopts=""
```

### Ce que ces tests couvrent bien

- import ciblé ou complet des bars ;
- gestion des incidents Alpaca ;
- marquage `no_history` / `provider_error` / `suspended_or_stale` ;
- auto-récupération SPY ;
- forward-fill et garde-fous du sanitizeur ;
- sync audit vers `stock_scores` ;
- enrichissement fondamentaux Finnhub ;
- émission des `run_summary` structurés sur les principales entrées CLI Data Integrity ;
- exposition IHM des commandes/options backend pour `import_alpaca_assets`, `update_sector`, `sync_latest_quotes` et `sync_earnings_calendar`.

### Ce qu’ils couvrent moins

- volumétrie réelle sur de grands univers ;
- performance MySQL en prod ;
- cohérence full-run provider en production sur très gros univers ;
- persistance SQL uniforme des résumés de run sur tous les flux, au-delà de la capture stdout / IHM.

---

## 12. Limites connues et points de vigilance pour la reprise

## 12.1 Hétérogénéité des points d’entrée

Tous les scripts n’ont pas le même niveau de maturité :
- tous les principaux scripts CLI émettent désormais un `run_summary` stdout standardisé ;
- le niveau de détail reste toutefois variable selon le flux (`import_alpaca_bar.py` et `data_sanitizer_daily.py` sont les plus riches) ;
- `import_alpaca_assets.py`, `update_sector.py`, `sync_latest_quotes.py` et `sync_earnings_calendar.py` publient volontairement des résumés plus compacts, centrés sur le volume traité, les paramètres CLI saisis et la durée.

## 12.2 Multi-compte Alpaca peu exposé côté CLI dataIntegrityEngine

La couche provider le supporte partiellement, mais le package `dataIntegrityEngine` reste essentiellement pensé pour le compte par défaut.

## 12.3 Couplage fort à `stock_metadata`

Comme plusieurs scripts reconstruisent leur univers depuis `stock_metadata`, toute modification de :
- `bars_available`
- `history_status`
- `status`
- `tradable`
- `asset_class`

peut avoir un effet de bord large.

## 12.4 Le module prépare la donnée, mais ne la “réconcilie” pas totalement

Par exemple :
- pas de versioning multi-séries complet au-delà de `data_adjustment` ;
- pas de persistance uniforme de tous les résumés de run ;
- pas de couche unique d’orchestration propre au package.

---

## 13. Recommandations concrètes pour le mainteneur qui reprend

## 13.1 À surveiller en priorité

- la santé de `stock_metadata.history_status` ;
- la profondeur et fraîcheur de `stock_bars` ;
- le ratio de `is_filled` dans `stock_bars_daily` ;
- les échecs récents dans `cleaning_audit_latest` ;
- la couverture réelle de `sector` / `market_cap` / quotes / earnings.

## 13.2 Si vous devez modifier le module

Ordre de prudence recommandé :

1. ne pas casser la série canonique `split` sans décision explicite globale ;
2. préserver la sémantique des `history_status` ;
3. conserver les protections de qualité du sanitizeur ;
4. ajouter des tests avant d’élargir le périmètre timeframe ;
5. documenter toute évolution de schéma SQL en même temps que le code.

## 13.3 Améliorations probables à moyen terme

- enrichir et homogénéiser davantage le schéma des `run_summary` structurés entre scripts ;
- exposer proprement le multi-compte Alpaca dans les CLI ;
- ajouter une doc spécifique de dépannage “incident provider” ;
- enrichir les audits de quotes / earnings si ces flux deviennent critiques ;
- consolider le package sous un orchestrateur plus uniforme si le périmètre continue de grandir.

---

## 14. Résumé exécutif pour la reprise

Si une seule chose doit être retenue :

- `stock_metadata` définit l’univers exploitable ;
- `import_alpaca_bar.py` décide si un symbole a un historique exploitable ;
- `data_sanitizer_daily.py` transforme cet historique en série daily propre, auditée et consommable ;
- `update_sector.py`, `sync_latest_quotes.py` et `sync_earnings_calendar.py` enrichissent ensuite les métadonnées nécessaires aux filtres aval ;
- le projet repose sur une convention volontairement simple : **série daily split-adjusted, alignée sur SPY, auditée par symbole**.

C’est ce socle qui conditionne ensuite la qualité du screening, de la sélection, du risque et de l’exécution.

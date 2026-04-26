# Audit — `dataIntegrityEngine`

> Périmètre : `dataIntegrityEngine/` + dépendances directes (`database/assets.py`,
> `database/sanitizer_db_ops.py`, `database/bar_metadata.py`, `service/alpaca/clientAlpaca.py`,
> `service/finnhub/clientFinnhub.py`).
> Sources : `doc/dataIntegrityEngine.md`, code listé, tests `tests/test_*sanitizer*`, `tests/test_import_alpaca_*`,
> `tests/test_update_sector.py`, `tests/test_data_integrity_run_summaries.py`.

---

## 1. Résumé exécutif

`dataIntegrityEngine` est la **porte d'entrée des données de marché** : ingestion d'univers
Alpaca, ingestion des bars OHLCV daily, nettoyage / alignement / audit (`stock_bars_daily`),
enrichissement fondamental (Finnhub), snapshots de quotes et calendrier earnings.

État global : **module mature et bien documenté**, avec des invariants explicites
(série canonique `split-adjusted`, calendrier SPY de référence, `history_status` qui pilote
l'éligibilité). Bonne couverture d'audit (`cleaning_audit_latest`, `cleaning_audit_runs`),
résumés `::alpha_trade_run_summary::` standardisés, tests unitaires nombreux.

Principaux risques :

1. **Dépendance forte à un seul provider gratuit (Alpaca IEX)** : le volume / la liquidité
   ingérés sous-représentent fortement le marché réel (~2-3 % des flux). Tous les filtres
   downstream (`avg_dollar_volume_20d`, `liquidity_threshold`, `spread_bps`) en héritent
   sans correctif explicite documenté côté ingestion.
2. **`stock_quote_snapshots` est un point unique non historisé** : un seul snapshot par jour,
   pas d'audit dédié, pas de retry-friendly. Si la sync rate quelques minutes après l'ouverture,
   les spreads sont pollués par les premiers ticks IEX.
3. **`update_sector` cumule deux responsabilités** (`sector` + `market_cap`) sous un nom
   trompeur, sans rafraîchissement périodique programmé : market cap fige au premier appel.
4. **Multi-comptes pas exposé** côté CLI : tous les flux Data Integrity tournent sur le
   compte par défaut, ce qui est cohérent (données de marché partagées), mais demande
   à être documenté formellement.
5. **Pas de versioning fort de la série de prix** : `data_adjustment` existe sur
   `stock_bars_daily` mais aucune garantie qu'on ne mélange pas dans la même table des
   barres provenant de modes différents si on changeait un jour `adjustment="split"`.

Priorités immédiates : (i) durcir la collecte / l'audit de `stock_quote_snapshots`,
(ii) ajouter une seconde source de volume / liquidité (Yahoo / Stooq) en consolidation,
(iii) introduire une vraie passe `truncate + rebuild` documentée avec contraintes
`CHECK data_adjustment='split'` puisque la base sera réinitialisée.

---

## 2. Constat détaillé par composant

### 2.1 `import_alpaca_assets.py`

| Item | Détail |
|---|---|
| Constat | Script très fin : `fetch_alpaca_assets()` + `insert_assets_to_db()` ; pose `bars_available=True` et `history_status='pending'` à l'upsert. |
| Risque | **Cohérence des données** : un asset délisté côté Alpaca peut rester `tradable=1` longtemps si la sync n'est pas planifiée. Pas de marquage explicite des disparitions. |
| Impact | Univers avec des fantômes ; `stock_metadata` peut diverger de la réalité broker. |
| Criticité | Modéré |
| Recommandation | (a) Ajouter un mode `--mark-disappeared` qui passe à `status='inactive'` ou `tradable=0` les symboles absents du dernier fetch ; (b) horodater l'upsert (`metadata_synced_at`) pour piloter la fraîcheur. |

### 2.2 `import_alpaca_bar.py`

| Item | Détail |
|---|---|
| Constat | États bien modélisés (`pending`, `ready`, `no_history`, `provider_error`, `suspended_or_stale`) ; staleness combinée calendaire / trading days ; validation `_validate_bar_business_rules`. |
| Risque | **Fiabilité** : `provider_error` ne déclenche pas d'alerte agrégée — un opérateur peut passer à côté de N% du périmètre cassé un jour donné. |
| Risque 2 | **Cohérence** : choix `adjustment="split"` figé en dur. Aucune contrainte SQL ne garantit que toutes les lignes de `stock_bars` partagent ce mode. |
| Impact | Si quelqu'un modifie `adjustment` (test, branche), pollution silencieuse. |
| Criticité | Élevé |
| Recommandations | (a) Émettre un `WARNING` agrégé + ligne `run_summary` enrichie avec `provider_error_ratio` ; (b) ajouter une **colonne `data_adjustment` sur `stock_bars`** + `CHECK` ; (c) vérifier dans le résumé que `successful_symbols / targeted_symbols` reste au-dessus d'un seuil métier (par défaut 80 %), sinon exit code ≠ 0. |

### 2.3 `data_sanitizer_daily.py`

| Item | Détail |
|---|---|
| Constat | `REBUILD_LOOKBACK_CALENDAR_DAYS=400` + alignement SPY + forward-fill borné `MAX_CONSECUTIVE_FILLED_DAYS=3` + Rolling MAD (`ANOMALY_MAD_THRESHOLD=5.0`, `ANOMALY_RETURN_THRESHOLD=0.02`). |
| Force | Auto-import de SPY si absent — bonne robustesse. |
| Risque | **Cohérence des données** : SPY est le calendrier ; si SPY a un `provider_error` un jour, **toutes** les autres séries voient leur dernière séance "manquante". |
| Risque 2 | **Performance** : recalculer 400 jours par run, pour ~5000 symboles, peut devenir long. Pas de mesure publiée. |
| Risque 3 | Pas de détection de **gap volume** anormal (volume = 0 sur jour normalement liquide), uniquement les gaps prix. |
| Impact | Anomalies de volume IEX silencieuses → liquidité downstream sur-estimée. |
| Criticité | Élevé |
| Recommandation | (a) Substituer le calendrier SPY par `pandas_market_calendars.get_calendar("XNYS")` pour découpler du provider de prix ; (b) ajouter une règle d'anomalie volume (z-score volume vs médiane 60j) ; (c) instrumenter via `run_summary` un `wall_clock_per_symbol` pour suivre la dérive de perf. |

### 2.4 `update_sector.py`

| Item | Détail |
|---|---|
| Constat | Met à jour `sector` ET `market_cap` (nom trompeur), via Finnhub free tier ; throttling `MIN_REQUEST_INTERVAL_SECONDS=1.1`. |
| Risque | **Cohérence des données** : `market_cap` fige au premier passage ; pas de rafraîchissement périodique → un titre passe sous 2 Md$ sans qu'on le voie côté `STRICT_SWING_CASH_FILTERS`. |
| Risque 2 | **Maintenabilité** : pas de TTL ni de colonne `market_cap_refreshed_at`. |
| Impact | Filtre `market_cap >= 2e9` du selector basé sur une donnée potentiellement très obsolète. |
| Criticité | Élevé |
| Recommandation | (a) Renommer en `update_fundamentals.py` (ou créer un alias) ; (b) ajouter `market_cap_refreshed_at`, et un mode `--refresh-stale-days 30` qui revisite les symboles dont la donnée a > 30 jours ; (c) aligner le throttling sur le quota Finnhub réel (60/min en free) avec une prise en compte explicite des `429`. |

### 2.5 `sync_latest_quotes.py`

| Item | Détail |
|---|---|
| Constat | Snapshot quotidien par symbole, batch 200, calcule `spread_bps`. **Pas d'audit SQL dédié**. Pas d'historisation intraday. |
| Risque | **Cohérence des données / fiabilité** : un snapshot pris pendant la première minute après l'ouverture (spreads larges IEX) sera consommé tel quel par le filtre `spread_bps <= 25` du selector. |
| Risque 2 | Pas de garantie `quote_timestamp` < 60 s par rapport au moment de la collecte ; aucun seuil de rejet documenté. |
| Impact | Faux positifs / faux négatifs sur le filtre de spread — directement dans la sélection de portefeuille. |
| Criticité | Critique |
| Recommandation | (a) Refuser une quote dont le `bid_size`/`ask_size` < N (configurable, ex. 100) ; (b) refuser une quote au-delà de X minutes après la cutoff (ex. 60 min) ; (c) **planifier la sync hors RTH** (ex. 16:05 ET) pour avoir un close stable ; (d) ajouter `cleaning_audit_quotes_*` (compteur de symboles ignorés, raisons) ; (e) historiser au moins 30 jours pour pouvoir backtester les filtres. |

### 2.6 `sync_earnings_calendar.py`

| Item | Détail |
|---|---|
| Constat | Fenêtre `J-7 → J+30` ; pas d'audit SQL dédié ; throttling Finnhub identique à `update_sector`. |
| Risque | **Cohérence** : si un earnings est annoncé tardivement (J+5), le rafraîchissement "le matin du run" peut le rater jusqu'au prochain run. |
| Risque 2 | Source unique Finnhub free → pas de cross-check (ex. Nasdaq earnings calendar, Yahoo, FMP). |
| Impact | Risque de prendre des positions juste avant un earnings non détecté. |
| Criticité | Élevé |
| Recommandation | (a) Étendre la fenêtre par défaut à `J-3 → J+45` ; (b) cron implicite : si dernier sync > 12 h, refuser le selector via dépendance IHM (déjà partiellement fait côté IHM, à matérialiser côté CLI selector aussi) ; (c) cross-check optionnel Yahoo (free, fiable, pas de quota strict). |

### 2.7 Couplage `stock_metadata.history_status`

| Item | Détail |
|---|---|
| Constat | `history_status` est un état qui pilote toute la chaîne aval (sélection, screening). |
| Risque | **Maintenabilité** : un changement de sémantique d'un seul état casse silencieusement la sélection. |
| Recommandation | (a) Documenter formellement la machine d'états dans un commentaire SQL (`COMMENT` MySQL) ; (b) ajouter un test d'intégration qui contrôle qu'aucun état "inconnu" n'apparaît jamais en base. |

---

## 3. Risques prioritaires

### Critique
- **Quotes pollués par IEX en début de séance** consommés tel quels par le selector
  (`stock_quote_snapshots` sans audit ni filtres de fraîcheur).

### Élevé
- Volume / liquidité sous-représentés à cause de la couverture IEX gratuite (impact sur
  `liquidity_val`, `avg_dollar_volume_20d`, `total_score` percentile-based).
- `market_cap` figé sans TTL → filtre `market_cap >= 2 Md$` peut être faux pendant des mois.
- SPY = calendrier = source de prix : couplage qui peut tout faire dérailler en cas
  d'incident provider.
- Earnings sous une seule source Finnhub free.

### Modéré
- Pas de marquage automatique des assets disparus côté Alpaca.
- `run_summary` ne déclenche pas d'`exit code ≠ 0` quand le ratio de succès est trop faible.
- Pas de versioning fort de `data_adjustment` au niveau SQL.

### Faible
- Nom de script `update_sector.py` trompeur (gère aussi `market_cap`).
- Multi-compte non exposé côté CLI (acceptable car données partagées, à documenter).

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

### Constat technique
Le client Alpaca gratuit utilise le feed **IEX**, qui représente ~2-3 % du volume consolidé US.
Les conséquences directes pour `dataIntegrityEngine` :

- **`volume`** : sous-évalué d'un facteur ~30-50× sur la plupart des large caps. Les calculs
  type `avg_dollar_volume_20d` (filtre liquidité du selector à `30 M$`) sont biaisés mais
  *de manière relativement homogène entre symboles*. Le ranking relatif tient.
- **`vwa_price` (vwap)** : calculé sur IEX uniquement → peu fiable comme prix de référence
  pour TCA. Pas critique ici (TCA est fait par `execution_engine`).
- **OHLC** : les `open`/`high`/`low`/`close` IEX sont raisonnablement proches du
  consolidated tape pour les large caps liquides ; pour les small caps illiquides, les écarts
  peuvent être réels (parfois plusieurs %).
- **Bid/ask** (snapshot quotes) : c'est **le point le plus problématique**. IEX a des spreads
  notoirement plus larges que NBBO ; le filtre `spread_bps <= 25` est probablement
  pessimiste de manière non uniforme.

### Filtres / pipelines impactés

| Composant | Impact |
|---|---|
| `screener.stock_screener` (`liquidity_val`) | Sous-estimation systématique. Mitigé par le ranking percentile. |
| `selector.alpha_scanner` (`avg_dollar_volume_20d >= 30M$`) | Faux négatifs probables sur certains mid caps. |
| `selector.alpha_scanner` (`spread_bps <= 25`) | Faux négatifs très probables : exclut des titres exécutables en réalité. |
| `screener` `total_score` percentile | Robuste relativement, biais absolu acceptable. |
| `execution_engine.tca` | Slippage calculé contre un `decision_price` IEX vs fill consolidé broker → biais TCA. |

### Alternatives gratuites pertinentes

| Source | Avantages | Limites | Pertinence |
|---|---|---|---|
| **Stooq** (`pandas-datareader`) | Daily OHLCV consolidé, gratuit, pas de clé. | Pas d'intraday, pas de quotes, latence J+0 imparfaite. | **Élevée** — idéale pour cross-checker volume / OHLC daily. |
| **Yahoo Finance** (`yfinance`) | Daily consolidé, fundamentals, earnings, splits, dividendes. | Non officiel, rate-limit informel, sujet à blocage. | **Élevée** pour earnings + cross-check volume. |
| **Polygon.io** free | Plan gratuit avec NBBO et trade data limités. | 5 req/min, historique limité. | Modérée — utile pour test/dev. |
| **Tiingo** free | EOD consolidé, news limitée. | Quota strict free. | Modérée. |
| **FMP** free | Earnings calendar, fundamentals. | Quota free serré. | Modérée — utile en backup earnings. |
| **Nasdaq Data Link** (ex-Quandl) | EOD partiel free. | Couverture restreinte. | Faible. |
| **SEC EDGAR** | Filings officiels (10-K, 10-Q, 8-K). | Pas du marché de prix. | Cible plutôt fundamentals. |

### Recommandation
Adopter **Stooq comme source de cross-check daily volume / OHLC** dans
`data_sanitizer_daily.py` :

- récupérer en best-effort les bars Stooq pour les symboles déjà ingérés ;
- si écart significatif détecté (`abs(volume_iex - volume_stooq) / volume_stooq > 50 %`
  ou `abs(close_diff_pct) > 1 %`), marquer l'anomalie dans `cleaning_audit_runs`.

Ne pas chercher à *remplacer* Alpaca (cela casserait l'intégration broker), mais à *valider*.

---

## 5. Choix recommandé `split_adjusted` vs `all`

| Critère | `split_adjusted` (choix actuel) | `all` |
|---|---|---|
| Simplicité | ✅ une série, pas de réécriture continue de l'historique | ❌ recalcule l'historique dès qu'un dividende tombe |
| Cohérence comptable | ✅ les dividendes sont gérés à part par `corporate_actions` | ❌ double comptage potentiel |
| Backtest fidèle au cash réel | ✅ + cash ledger CA pour la performance totale | ❌ rendement total déjà incorporé dans les prix → moins explicable |
| Cohérence avec exécution live | ✅ broker affiche aussi des prix split-adjusted | ✅ |
| Comparabilité long terme avec dividendes réinvestis | ❌ il faut additionner manuellement | ✅ direct |

**Recommandation : conserver `split_adjusted`** — cohérent avec l'architecture cash ledger
existante, plus simple à auditer, plus stable comme convention canonique.

Implications pratiques :
- Documenter explicitement dans `README.md` que la performance "totale dividendes inclus"
  doit lire `stock_bars_daily.close` + `portfolio_cash_ledger`.
- Ajouter un `CHECK (data_adjustment = 'split')` sur `stock_bars_daily` après réinitialisation.
- Dans `BacktestReport`, exposer une métrique distincte "Total return incl. dividends"
  qui consomme `portfolio_cash_ledger`.

---

## 6. Quick wins

1. **Ajouter un seuil d'alerte d'échec d'ingestion** : `import_alpaca_bar` exit ≠ 0 si
   `successful / targeted < 0.80`.
2. **Renommer / wrapper `update_sector` → `update_fundamentals`** + ajouter
   `market_cap_refreshed_at`.
3. **Filtre fraîcheur sur `sync_latest_quotes`** : refuser les quotes de plus de 60 min
   ou avec `bid_size < 100` ou `ask_size < 100`.
4. **Documenter `history_status` dans le DDL** (commentaire MySQL `COMMENT`).
5. **Ajouter un `CHECK (data_adjustment='split')` sur `stock_bars` et `stock_bars_daily`**
   après reset de la base.
6. **Ajouter dans `data_sanitizer_daily` une détection d'anomalie volume** (`volume == 0`
   ou z-score volume < -3) et la persister dans l'audit.
7. **Planifier `sync_latest_quotes` après la cloche (16:10 ET)** dans le runbook
   (et le préciser dans la doc `dataIntegrityEngine.md`).
8. **Découpler le calendrier de SPY** via `pandas_market_calendars` (déjà dépendance
   `requirements.txt`).

## 7. Recommandations structurelles

1. **Créer un audit dédié pour les flux quotes / earnings** (`cleaning_audit_quotes_runs`,
   `cleaning_audit_earnings_runs`) sur le modèle de `cleaning_audit_runs`.
2. **Introduire une seconde source de volume daily (Stooq)** en mode validation, avec
   alerte si divergence > seuil.
3. **Historiser `stock_quote_snapshots`** sur 30 jours pour permettre un backtest des
   filtres de spread.
4. **Refactorer le sanitizer** pour exposer une fonction `process_symbol(symbol, calendar)`
   pure et testable (réduction du couplage à la classe `DataSanitizer`).
5. **Découpler `dataIntegrityEngine` de `database/`** via une interface `BarsRepository`
   (Protocol), pour que `screener` puisse mocker plus simplement et que les flux puissent
   évoluer indépendamment du schéma SQL.
6. **Centraliser un orchestrateur Data Integrity** (`dataIntegrityEngine/orchestrator.py`)
   au lieu de scripts indépendants — un seul point d'entrée qui exécute la séquence,
   gère les exit codes et publie un résumé global.

## 8. Plan d'action priorisé

### Court terme (≤ 2 semaines)
- Quick wins 1, 2, 3, 4, 5, 7 (tous indépendants, faible risque).
- Ajout d'une alerte critique dans le `run_summary` quand le ratio de succès s'effondre.
- Migration calendrier vers `pandas_market_calendars`.

### Moyen terme (≤ 2 mois)
- Audit SQL dédié pour quotes / earnings.
- Cross-source Stooq pour volume / OHLC daily, avec marquage `cleaning_audit_runs`.
- Refactoring `update_sector` → `update_fundamentals` avec TTL.
- Historisation des snapshots de quotes.
- Tests d'intégration end-to-end avec `testcontainers[mysql]` (déjà dans `requirements.txt`).

### Long terme (≤ 6 mois)
- Orchestrateur unique dataIntegrity avec exit codes explicites et résumé consolidé.
- Repository abstrait `BarsRepository` (Protocol) pour découpler du schéma SQL.
- Évaluation d'une migration partielle vers Polygon free (NBBO consolidé) si le quota le permet.
- Surveillance Prometheus / fichier JSONL des metrics quotidiens.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Bonne couverture unitaire (cf. liste tests). **Manque** :
  - test d'intégration "univers complet" sur petite DB MySQL via `testcontainers`.
  - test sur le scénario `provider_error` à grande échelle.
  - test de non-régression sur le ratio `is_filled` après run sanitizer.
  - test cross-source (Stooq vs Alpaca) à introduire en parallèle de l'évolution.

### Monitoring
- Aucune métrique exposée hors logs / `run_summary` stdout. Ajouter au minimum :
  - dump JSONL quotidien dans `log/data_integrity_metrics.jsonl` ;
  - badges IHM sur la fraîcheur de chaque table (`stock_bars_daily.date_max`,
    `stock_quote_snapshots.quote_date_max`, `stock_earnings_calendar.fetched_at_max`).

### Documentation
- Bien fournie (`doc/dataIntegrityEngine.md` ~1180 lignes). **Manque** :
  - section explicite "Limitations IEX et leur impact concret".
  - documentation formelle de la machine d'états `history_status`.
  - runbook "incident provider Alpaca" (que faire en cas de timeout massif).
  - section "policy de prix" explicite (`split_adjusted` choisi et pourquoi).


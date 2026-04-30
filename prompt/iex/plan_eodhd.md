# Plan d'intégration EOD Historical Data (EODHD) — Alpha Trade

> **Objectif** : remplacer Alpaca/IEX comme source primaire des **barres OHLCV** (`stock_bars` + `stock_bars_daily`) par **EODHD** (plan All-In-One ou US-only à 19,99 $/mois), avec **un seul appel bulk** alimentant les deux tables.
>
> **Hors périmètre** :
> - `stock_metadata` reste piloté par **Alpaca** (assets, `id_alpaca`, `tradable`, `status`, `bars_available`) + **Finnhub** (`sector`, `market_cap`).
> - Exécution / fills / `buying_power` / quotes live → **Alpaca inchangé**.
>
> **Date** : 2026-04. Référence : `prompt/iex/audit.md`.
>
> **État pré-requis** : ✅ alignement `database/sql/` ↔ migrations alembic effectué (cf. §1). 8 divergences corrigées (5 .sql créés, 2 patchés, 1 patch loader). `python database/sql/all_tables.py` produit désormais un schéma complet.

---

## 0. TL;DR

| Table / usage | Avant | Après | Notes |
|---|---|---|---|
| `stock_metadata` | Alpaca + Finnhub | **Alpaca + Finnhub (inchangé)** | Broker = Alpaca |
| `stock_bars` (intraday théorique, **1D en pratique**) | Alpaca/IEX | **EODHD (alimentée par même bulk)** | §3 — redondance documentée |
| `stock_bars_daily` | Alpaca/IEX | **EODHD bulk daily** | Cœur du screener/selector |
| `stock_quote_snapshots` | Alpaca IEX | **Alpaca IEX (inchangé)** | Quotes broker-facing |
| Splits / dividendes | engine projet + cross-check Yahoo | engine projet + EODHD source primaire + Yahoo cross-check (inchangé) | |
| Cross-check daily bars | code Stooq présent **mais non câblé** | **Stooq enfin activé** | Première vraie activation |
| Exécution / fills / `buying_power` | Alpaca | **Alpaca (inchangé)** | EODHD n'est pas broker |
| Indicateurs (RSI/ATR/VCP/beta) | calcul local | **calcul local (inchangé)** | Refus de l'API `/technical/` EODHD |

**Coût EODHD** : **1 seul appel bulk/jour** alimente `stock_bars` ET `stock_bars_daily` (§3.6). ~320 calls/jour sur quota 100 000.

---

## 1. État du socle (acquis avant ce plan)

Pré-requis P0 résolus le 2026-04-29 :

### 1.1 Patch `all_tables.py` (glob récursif)
Le loader utilise désormais `glob('**/*.sql', recursive=True)` et exclut `truncate_*.sql` + `migration_*.sql`. Détection vérifiée : **56 CREATE statements** chargés.

### 1.2 Tables créées (5 SQL canoniques manquants)

| Migration alembic | Fichier SQL créé |
|---|---|
| 0016 `model_metrics_full_blob` | `database/sql/ml/model_metrics_full.sql` |
| 0017 `execution_kill_switch_runs` | `database/sql/execution/execution_kill_switch_runs.sql` |
| 0020 `weights_calibration_runs` | `database/sql/ml/weights_calibration_runs.sql` |
| 0021 `ml_drift_runs` | `database/sql/ml/ml_drift_runs.sql` |
| 0022 `shadow_drift_runs` | `database/sql/risk/shadow_drift_runs.sql` |

### 1.3 SQL existants patchés (2 fichiers)

| Migration | Fichier patché | Ajout |
|---|---|---|
| 0015 `finbert_model_fingerprint` | `database/sql/news/news_sentiment.sql` | Colonne `model_fingerprint VARCHAR(32)` + index `idx_news_sentiment_model_fingerprint` |
| 0019 `corporate_actions_account_idempotency` | `database/sql/corporate_actions/corporate_actions_events.sql` | Colonne `account_idempotency_key VARCHAR(64)` + `UNIQUE KEY uq_corporate_actions_events_account_idem` |

### 1.4 Commentaires `data_source` élargis pour anticiper EODHD

`stock_bars.sql` et `stock_bars_daily.sql` : commentaire mis à jour pour autoriser conceptuellement `eodhd_eod` (VARCHAR(16) suffit, pas de CHECK enum). Aucune modification structurelle.

### 1.5 Observation hors périmètre

`database/sql/news/init_event_sentiment.sql` duplique 6 CREATE déjà présents dans les fichiers dédiés (`news_raw.sql`, `news_sentiment.sql`, etc.). Idempotent grâce à `IF NOT EXISTS`, **non bloquant** mais à factoriser dans un futur cleanup.

### 1.6 Tables `stock_bars*` et `stock_metadata` — alignement vérifié
Migration `0012_market_data_provenance_and_check.py` totalement reflétée dans :
- `stock_bars.sql` (`data_adjustment`, `data_source`, `chk_bars_adj`)
- `stock_bars_daily.sql` (idem + `chk_daily_adj`)
- `stock_metadata.sql` (`data_source`, `market_cap_refreshed_at`, `metadata_synced_at`)
Aucune migration ultérieure (0013→0022) ne les touche.

---

## 2. État réel des sources externes (vérifié dans le code)

### 2.1 Alpaca — utilisé partout
- `service/alpaca/clientAlpaca.py` : client primary.
- `dataIntegrityEngine/import_alpaca_assets.py` → alimente `stock_metadata`. **Reste tel quel.**
- `dataIntegrityEngine/import_alpaca_bar.py` → alimente `stock_bars` + `stock_bars_daily`. **À doubler avec EODHD daily, no-op sous flag.**
- `dataIntegrityEngine/sync_latest_quotes.py` → quotes IEX. **Reste tel quel.**
- `execution_engine/` → ordres. **Reste tel quel.**

### 2.2 Finnhub — utilisé en prod
Sector + market_cap pour `stock_metadata`. Cache `artifacts/finnhub_cache/`. **Reste tel quel.**

### 2.3 Stooq — code présent, **JAMAIS appelé en production**
Vérifié par grep :
- `dataIntegrityEngine/cross_check_stooq.py::compare_with_stooq` : prêt.
- `service/stooq/clientStooq.py::fetch_daily_bars` : prêt.
- **Aucun import depuis le pipeline daily**.
- **Action plan** : profiter d'EODHD pour **enfin câbler** Stooq comme audit best-effort (§5.7).

### 2.4 Yahoo / yfinance — utilisé en prod, périmètre étroit
Vérifié par grep :
- `corporate_actions/cross_check_yahoo.py::YahooDividendCrossCheckProvider`.
- `corporate_actions/cli.py` lignes 334 + 475 : appelé via `_run_cross_check_yahoo()`.
- Périmètre : **dividendes corporate actions uniquement**.
- Module `service/yahoo/` : vide (`__pycache__/` seul).
- **Action plan** : conserver Yahoo tel quel ; EODHD `/div` devient source primaire des dividendes, Yahoo reste cross-check tiers.

### 2.5 Tiingo — préparé, jamais utilisé
`service/tiingo/` vide. EODHD remplace définitivement l'intention Tiingo. Suppression Phase 6.

---

## 3. Architecture `stock_bars` vs `stock_bars_daily` — Décision

### 3.1 Constat (vérifié)

| Aspect | `stock_bars` | `stock_bars_daily` |
|---|---|---|
| Clé temps | `timestamp DATETIME` | `date DATE` |
| Multi-timeframe | OUI (1M, 1D, 1H, 15M, 30M dans `bar_metadata.py::TimeFrame`) | NON |
| Timeframes effectivement ingérés | **`1D` uniquement** — `SUPPORTED_DATA_INTEGRITY_TIMEFRAMES = (TimeFrame.ONE_DAY,)` | `1D` |
| Colonnes quant | trade_count, vwa_price | adj_close, vwap, daily_return, is_filled |
| Format stockage | InnoDB standard | InnoDB **ROW_FORMAT=COMPRESSED** |
| Consommateurs | `dataIntegrityEngine/data_sanitizer_daily.py`, tests | `selector/factors.py`, `screener/pipeline.py`, `backtesting/`, `modelFactory/` |

### 3.2 Diagnostic
Les deux tables stockent les mêmes données aujourd'hui. `stock_bars` = format brut "ingestion" prévu pour multi-timeframe futur. `stock_bars_daily` = format optimisé "consommation quant".

### 3.3 Décision : 1 seul appel, double écriture

```python
# import_eodhd_bar.py — pseudo-code
bulk = fetch_eod_bulk(date=J-1, exchange="US")             # 1 seul appel API (cost=100)
for entry in bulk:
    splits = cached_fetch_splits(entry["code"])             # cache TTL 7j
    bar_split = eodhd_to_split_only(entry, splits)
    upsert_stock_bars_daily(bar_split, data_source="eodhd_eod")
    upsert_stock_bars(bar_split, timeframe="1D", data_source="eodhd_eod")
```

Avantages :
- ✅ Coût API minimal (1 bulk = 2 écritures).
- ✅ Continuité : `data_sanitizer_daily.py` (lit `stock_bars`) et `selector/` (lit `stock_bars_daily`) inchangés.
- ✅ Réversibilité : retirer une écriture si `stock_bars` est déprécié plus tard.

### 3.4 Future dépréciation `stock_bars` — reportée post-MVP
Décision explicitement écartée maintenant : trop intrusif vs sanitizer. À reconsidérer après stabilisation EODHD.

---

## 4. Décisions structurantes

### 4.1 Pas de migration alembic — modifier directement les `.sql`
Le projet utilise `python database/sql/all_tables.py` en runtime. Toutes les évolutions schéma se font dans `database/sql/**/*.sql`.

### 4.2 Convention d'ajustement OHLCV — invariant `split-only`
- Projet : `adjustment="split"` (vérifié `import_alpaca_bar.py:36`).
- SQL : `CHECK (data_adjustment = 'split')` dans `stock_bars` et `stock_bars_daily`.
- EODHD : `open/high/low/close` = raw, `adjusted_close` = split+dividend.
- ⇒ **Reconstruction obligatoire d'un OHLCV split-only** côté adapter (§5.4).
- ⇒ La CHECK constraint reste : EODHD écrit aussi `'split'` après reconstruction.

### 4.3 Flag de bascule (`config.yaml`)

```yaml
market_data:
  bars_provider: alpaca   # alpaca | eodhd  (cible: eodhd)
  fallback_on_failure: true

eodhd:
  enabled: false
  api_token_env: EODHD_API_TOKEN
  exchange: US
  cache_dir: artifacts/eodhd_cache
  daily_quota: 100000
  soft_quota_warn: 80000
  bulk_publish_offset_hours: 2
  circuit_breaker:
    consecutive_failures: 5
    cooldown_minutes: 30
```

`bars_provider` ne touche PAS `import_alpaca_assets.py` (assets restent Alpaca).

### 4.4 Provenance (`data_source`)
Commentaires SQL déjà élargis (§1.4). VARCHAR(16) suffit, pas de CHECK enum.

---

## 5. Architecture & specs techniques

### 5.1 Nouveau module `service/eodhd/`

```
service/eodhd/
    __init__.py
    clientEodhd.py        # fetch_eod_bulk, fetch_eod, fetch_dividends, fetch_splits
    adapters.py           # eodhd_to_split_only, to_stock_bars_daily_row, to_stock_bars_row
    symbols.py            # AAPL <-> AAPL.US, BRK.B <-> BRK-B.US
    cache.py              # cache disque artifacts/eodhd_cache/
    quota.py              # compteur journalier + circuit-breaker
    accounts.py           # registre token (calque service/alpaca/accounts.py)
    symbols_exceptions.json
```

Réutilise : `service._http_retry.RetryPolicy`, `service._telemetry.bump`. Erreurs typées : `EodhdBarsFetchError`, `EodhdQuotaExceeded`, `EodhdAuthError`.

### 5.2 Primitives `clientEodhd.py`

```python
def fetch_eod_bulk(date: str | None = None, exchange: str = "US",
                   symbols: Sequence[str] | None = None) -> list[dict]:
    """1 appel = univers US complet (J-1 par défaut). Coût: 100 calls."""

def fetch_eod(symbol: str, *, start: str | None = None, end: str | None = None,
              period: Literal["d","w","m"] = "d") -> list[dict]:
    """Historique long pour un symbole. Coût: 1 call."""

def fetch_splits(symbol: str, *, start: str | None = None) -> list[dict]: ...
def fetch_dividends(symbol: str, *, start: str | None = None) -> list[dict]: ...
```

### 5.3 Mapping symboles `service/eodhd/symbols.py`

```python
def to_eodhd(symbol: str, exchange: str = "US") -> str: ...   # AAPL -> AAPL.US ; BRK.B -> BRK-B.US
def from_eodhd(eodhd_symbol: str) -> tuple[str, str]: ...     # AAPL.US -> ("AAPL","US")
```

Cas particuliers documentés dans `service/eodhd/symbols_exceptions.json`.

### 5.4 Adapter split-only `service/eodhd/adapters.py`

Algorithme :
1. `splits = fetch_splits(symbol)` (cache TTL 7j).
2. `cum_factor(d) = ∏ ratio_split(d_split > d)`.
3. Pour chaque barre brute `(o,h,l,c,v)` à la date `d` :
   - `o_split = o / cum_factor(d)`, etc.
   - `v_split = v * cum_factor(d)`.

Signatures :

```python
def eodhd_to_split_only(raw_bars: list[dict], splits: list[dict]) -> list[dict]: ...

def to_stock_bars_daily_row(bar: dict, symbol: str) -> dict:
    """Mappe vers stock_bars_daily : symbol, date, open, high, low, close, volume,
       adj_close=close, vwap=None, is_filled=0, data_adjustment='split', data_source='eodhd_eod'."""

def to_stock_bars_row(bar: dict, symbol: str, timeframe: str = "1D") -> dict:
    """Mappe vers stock_bars : symbol, timestamp (= date 16:00 ET), timeframe='1D',
       open_price/high_price/low_price/close_price, volume, trade_count=0, vwa_price=None,
       data_adjustment='split', data_source='eodhd_eod'."""
```

**Test golden obligatoire** : NVDA split 10:1 du 2024-06-10. `close(2024-06-09) == raw_close / 10`, `volume(2024-06-09) == raw_volume * 10`, jonction sans saut > 1 % avec barres `alpaca_iex` antérieures.

### 5.5 Quota & circuit-breaker `service/eodhd/quota.py`

- Compteur dans `artifacts/eodhd_cache/quota_YYYYMMDD.json`.
- Coûts EODHD : bulk = 100, eod = 1, splits/div = 1.
- N erreurs HTTP consécutives → `circuit_open=True` pour `cooldown_minutes`.
- Métriques injectées dans `run_summary` : `eodhd.calls_used`, `eodhd.calls_failed`, `eodhd.circuit_open`.

### 5.6 Ingestion `dataIntegrityEngine/import_eodhd_bar.py`

Pipeline (1 seul appel API) :

1. Lire `market_data.bars_provider` ; si `alpaca`, exit 0 (no-op).
2. Charger univers éligible via `database/assets.py::build_eligible_stock_metadata_filters`.
3. **1 appel** `fetch_eod_bulk(date=J-1, exchange="US")`.
4. Pour chaque symbole de l'univers présent dans le bulk :
   - `splits = cached_fetch_splits(symbol)`
   - `bar_split = eodhd_to_split_only(raw, splits)`
   - **Upsert `stock_bars_daily`** (`data_source='eodhd_eod'`)
   - **Upsert `stock_bars`** (`timeframe='1D'`, même `data_source`)
5. Symboles absents du bulk → tentative individuelle `fetch_eod` (limit 100 calls).
6. Circuit-breaker ouvert → fallback `import_alpaca_bar.py` pour ce run uniquement (logger `eodhd.fallback_used=true`, sans muter le flag global).
7. Émission `run_summary` enrichi (cf. §7).

**Invariant** : on n'écrit JAMAIS `data_source='alpaca_iex'` depuis ce script. Cohabitation propre avec lignes Alpaca héritées.

### 5.7 Activation effective de Stooq comme audit (P1)

Dans `import_eodhd_bar.py`, après ingestion :

```python
try:
    from dataIntegrityEngine.cross_check_stooq import compare_with_stooq
    anomalies = compare_with_stooq(rows_ingested, lookback_days=5, today=run_date)
    summary["cross_check_stooq"] = {"anomalies_count": len(anomalies), "failed": False}
except Exception as exc:
    LOGGER.warning("cross_check_stooq failed (non bloquant): %s", exc)
    summary["cross_check_stooq"] = {"anomalies_count": 0, "failed": True}
```

Persistance dans `cleaning_audit_runs.cross_check_anomalies`. **Première activation effective de Stooq**.

### 5.8 Corporate actions

- `corporate_actions/engine.py` : ajouter EODHD comme source primaire des dividendes/splits via `fetch_dividends` / `fetch_splits`.
- `corporate_actions/cli.py::_run_cross_check_yahoo` : **conserver tel quel** (Yahoo en triangulation).
- Optionnel : `_run_cross_check_eodhd` symétrique pour comparer.

### 5.9 Selector / Screener — **aucune modification de code**

`selector/factors.py::avg_dollar_volume_20d` et `screener/pipeline.py` consomment `stock_bars_daily` via SQL. Une fois les barres EODHD en base, ils profitent automatiquement du volume consolidé.

---

## 6. Plan d'exécution par phases

### Phase 1 — Cadrage EODHD (0,5 j)
- [ ] Souscrire EODHD All-In-One ; stocker `EODHD_API_TOKEN`.
- [ ] Mesurer délai effectif de publication du bulk J-1 sur 3 jours.
- [ ] Confirmer mapping symboles sur 20 cas (BRK.B, GOOG/GOOGL, ETFs).

### Phase 2 — Socle service `service/eodhd/` (2 j)
- [ ] `clientEodhd.py` + `tests/test_clientEodhd.py`.
- [ ] `symbols.py` + `tests/test_eodhd_symbols.py`.
- [ ] `cache.py` + `quota.py`.
- [ ] `adapters.py::eodhd_to_split_only` + **golden test NVDA 10:1**.
- [ ] `to_stock_bars_daily_row()` + `to_stock_bars_row()` + tests de mapping.
- [ ] `doc/service.md` mis à jour.

### Phase 3 — Ingestion shadow (1 j)
- [ ] `dataIntegrityEngine/import_eodhd_bar.py` (mode `--dry-run` qui n'upsert pas mais log les diffs).
- [ ] Audit SQL manuel : 50 symboles, comparer `volume_alpaca_iex` vs `volume_eodhd_eod` sur 60 jours → ratio attendu médian ∈ [10, 50] sur S&P 500.

### Phase 4 — Bascule contrôlée (1 j)
- [ ] Activer `eodhd.enabled=true` et `market_data.bars_provider=eodhd` en staging.
- [ ] Câbler Stooq cross-check (§5.7).
- [ ] Lancer le pipeline daily complet ; comparer `run_summary` selector avant/après.
- [ ] **Critère go/no-go** : ratio médian volume EODHD/Alpaca-IEX ∈ [10, 50] sur S&P 100 ; 0 large cap (mc > 10 G$) rejetée à tort par `min_avg_dollar_volume_20d=30_000_000`.

### Phase 5 — Backfill historique + corporate actions (1,5 j)
- [ ] `dataIntegrityEngine/backfill_eodhd_history.py` : 5 ans pour univers actif, jusqu'à 30 ans pour univers ML restreint. Bookmark dans `artifacts/eodhd_cache/backfill_state.json`.
- [ ] Backfill écrit dans **les deux tables**.
- [ ] EODHD source primaire des dividendes dans `corporate_actions/engine.py` ; Yahoo en cross-check.
- [ ] Re-run d'un backtest représentatif sur 2020-2025 ; consigner Sharpe / max DD vs Alpaca dans `prompt/iex/eodhd_ab_results.md`.

### Phase 6 — Production & nettoyage (0,5 j)
- [ ] Bascule prod.
- [ ] Conserver le chemin Alpaca daily désactivé pendant 1 mois (réversibilité).
- [ ] Suppression du dossier vide `service/tiingo/`.
- [ ] `doc/data_lineage_matrix.md` mis à jour.

**Total : ~6,5 j-h** (Phase 0 d'alignement SQL déjà acquise).

---

## 7. Stratégie de tests

### 7.1 Nouveaux tests à créer

| Test | Fichier | But |
|---|---|---|
| T-EOD-1 | `tests/test_clientEodhd.py` | mocks HTTP : bulk, eod, splits, dividends ; auth ; quota ; circuit-breaker |
| T-EOD-2 | `tests/test_eodhd_symbols.py` | mapping BRK.B / GOOG / ETFs / cas dégradés |
| T-EOD-3 | `tests/test_eodhd_split_only.py` | **golden NVDA 10:1** ; jonction sans saut avec barres `alpaca_iex` |
| T-EOD-4 | `tests/test_import_eodhd_bar.py` | bulk → upsert **les 2 tables** ; provenance `eodhd_eod` ; fallback Alpaca quand circuit ouvert ; émission `run_summary` |
| T-EOD-5 | `tests/test_backfill_eodhd_history.py` | reprise sur bookmark ; idempotence ; mode shadow |
| T-EOD-6 | `tests/test_eodhd_liquidity_impact.py` | fixture : large cap rejeté `alpaca_iex` passe le filtre avec `eodhd_eod` |
| T-EOD-7 | `tests/test_eodhd_corporate_actions.py` | EODHD source primaire dividendes/splits ; Yahoo cross-check toujours appelé |
| T-EOD-8 | `tests/test_eodhd_run_summary_keys.py` | clés `eodhd.*` + `cross_check_stooq.*` |
| T-EOD-9 | `tests/test_eodhd_quota.py` | dépassement soft-quota → warning ; hard-quota → exception |
| T-EOD-10 | `tests/test_eodhd_provider_switch.py` | `bars_provider=alpaca` → `import_eodhd_bar` no-op ; `=eodhd` → `import_alpaca_bar` no-op |
| T-EOD-11 | `tests/test_stooq_cross_check_pipeline.py` | active réellement Stooq ; non-bloquant en cas d'échec |
| T-EOD-12 | `tests/test_eodhd_dual_table_consistency.py` | pour un même payload bulk, vérifie que `stock_bars` (timeframe='1D') et `stock_bars_daily` ont mêmes OHLCV |

### 7.2 Tests existants à protéger

`tests/test_clientAlpaca.py`, `test_phase1_run_summary.py`, `test_stooq_cross_check.py`, `test_selector_alpha_scanner.py`, `test_selector_run_summaries.py`, `test_backtesting.py`, `test_corporate_actions_cross_check_yahoo.py`, `test_sanitizer_db_ops.py`.

### 7.3 Commandes de validation

**Batterie EODHD seule** :
```powershell
python -m pytest tests/test_clientEodhd.py tests/test_eodhd_symbols.py tests/test_eodhd_split_only.py tests/test_import_eodhd_bar.py tests/test_backfill_eodhd_history.py tests/test_eodhd_liquidity_impact.py tests/test_eodhd_corporate_actions.py tests/test_eodhd_run_summary_keys.py tests/test_eodhd_quota.py tests/test_eodhd_provider_switch.py tests/test_stooq_cross_check_pipeline.py tests/test_eodhd_dual_table_consistency.py -q -o addopts=""
```

**Non-régression complète** :
```powershell
python -m pytest tests/test_clientAlpaca.py tests/test_phase1_run_summary.py tests/test_stooq_cross_check.py tests/test_selector_alpha_scanner.py tests/test_selector_run_summaries.py tests/test_backtesting.py tests/test_corporate_actions_cross_check_yahoo.py tests/test_sanitizer_db_ops.py -q -o addopts=""
```

---

## 8. Observabilité

### 8.1 `run_summary` enrichi

| Clé | Type | Description |
|---|---|---|
| `eodhd.calls_used` | int | calls EODHD du run |
| `eodhd.calls_failed` | int | calls en erreur |
| `eodhd.bulk_size` | int | symboles renvoyés par le bulk |
| `eodhd.symbols_missing` | int | symboles univers absents du bulk |
| `eodhd.fallback_used` | bool | bascule fallback Alpaca |
| `eodhd.circuit_open` | bool | circuit-breaker déclenché |
| `eodhd.adjustment_mismatch_count` | int | divergences split-only détectées |
| `eodhd.rows_upserted_stock_bars` | int | lignes écrites dans `stock_bars` (timeframe='1D') |
| `eodhd.rows_upserted_stock_bars_daily` | int | lignes écrites dans `stock_bars_daily` |
| `cross_check_stooq.anomalies_count` | int | anomalies Stooq sur le run |
| `cross_check_stooq.failed` | bool | indispo Stooq (non bloquant) |

### 8.2 Logs
Préfixe `[eodhd]` dans `service/eodhd/*` et `import_eodhd_bar.py`. INFO/WARNING/ERROR comme `clientAlpaca.py`.

### 8.3 IHM
Étendre l'écran `ihm/` qui consomme `run_summary` :
- jauge consommation EODHD (sur 100 000) ;
- compteur d'anomalies Stooq actives ;
- provenance dominante du jour (`alpaca_iex` vs `eodhd_eod`).

---

## 9. Politique de rollback

1. `config.yaml : market_data.bars_provider: alpaca` → `import_eodhd_bar.py` no-op au prochain run.
2. Anciennes lignes `alpaca_iex` jamais supprimées → continuité immédiate.
3. Optionnel pour isoler : `DELETE FROM stock_bars_daily WHERE data_source='eodhd_eod' AND date >= :cutoff;` (idem `stock_bars`).

---

## 10. Coûts API EODHD

| Poste | Volume / jour | Calls EODHD |
|---|---|---|
| Bulk daily US (alimente **les 2 tables**) | 1 appel | **100** |
| Backfill incrémental symboles manquants | ~50 | 50 |
| Splits / dividendes refresh hebdo | ~500 amorti | ~70/jour |
| Cross-check ponctuel | ~100 | 100 |
| **Total opérationnel** | | **~320 / jour** |

Quota 100 000/jour → marge confortable. **Pas de doublement** API malgré 2 tables (1 bulk = 2 écritures).

---

## 11. Documentation à mettre à jour

- [ ] `doc/dataIntegrityEngine.md` — section EODHD ingestion + bulk + activation Stooq + écriture mutualisée.
- [ ] `doc/data_lineage_matrix.md` — ligne `eodhd_eod` (`stock_bars` + `stock_bars_daily`).
- [ ] `doc/service.md` — module `service/eodhd/`.
- [ ] `doc/database.md` — clarifier la sémantique `stock_bars` vs `stock_bars_daily`.
- [ ] `doc/DOC_TECHNIQUE.md` — switch `market_data.bars_provider`.
- [ ] `README.md` — section "Sources de données".
- [ ] `prompt/iex/audit.md` §12 — addendum arbitrage final EODHD.

---

## 12. Definition of Done

1. ✅ Pipeline daily tourne avec `bars_provider=eodhd` 10 jours ouvrés consécutifs sans intervention.
2. ✅ Médiane ratio `volume_eodhd / volume_alpaca_iex` sur top 100 large caps ∈ [10, 50].
3. ✅ Aucun symbole S&P 100 rejeté à tort par `min_avg_dollar_volume_20d`.
4. ✅ Test golden split-only NVDA vert.
5. ✅ Stooq cross-check **réellement appelé** dans le pipeline.
6. ✅ Yahoo cross-check dividendes toujours appelé en corporate actions.
7. ✅ `stock_bars` et `stock_bars_daily` synchronisées sur les mêmes OHLCV (test T-EOD-12).
8. ✅ Backtest A/B 2020-2025 produit dans `prompt/iex/eodhd_ab_results.md`.
9. ✅ Aucune régression sur la batterie de tests existants.
10. ✅ `stock_metadata` reste 100 % Alpaca + Finnhub.

---

## 13. Décisions explicitement écartées

- ❌ **API `/technical/` EODHD** : casse la reproductibilité PIT (cf. audit §4.2).
- ❌ **Migration alembic dédiée** : projet utilise `all_tables.py`.
- ❌ **Migration vers convention `split+dividend`** : casserait CHECK constraints + tests.
- ❌ **Remplacer Alpaca pour exécution / quotes live / metadata** : EODHD n'est pas broker.
- ❌ **Suppression de Yahoo** : conservé pour cross-check dividendes (réellement utilisé).
- ❌ **Suppression de Stooq** : au contraire, on l'**active enfin**.
- ❌ **Conservation de `service/tiingo/` (vide)** : à supprimer Phase 6.
- ❌ **Migration immédiate de `stock_bars` (intraday multi-timeframe)** : reportée post-MVP.
- ❌ **Déprécier `stock_bars` immédiatement** : trop intrusif vs `data_sanitizer_daily.py` (§3.4).
- ❌ **Doubler les appels API EODHD pour les 2 tables** : 1 seul bulk → 2 écritures (§3.3).

---

## 14. Annexe — payloads EODHD et mapping schéma

### Bulk EOD
```
GET https://eodhd.com/api/eod-bulk-last-day/US?api_token=XXX&fmt=json
[
  {"code":"AAPL","exchange_short_name":"NASDAQ","date":"2026-04-28",
   "open":189.12,"high":191.50,"low":188.80,"close":190.74,
   "adjusted_close":190.51,"volume":58234100},
  ...
]
```

### Splits
```
GET https://eodhd.com/api/splits/NVDA.US?from=2010-01-01&fmt=json
[{"date":"2024-06-10","split":"10/1"}, ...]
```
Ratio numérique = numerator / denominator.

### Mapping → `stock_bars_daily`
```
EODHD bar (split-only)        stock_bars_daily
---------------------------   -----------------------
code (normalize)              symbol
date                          date
open_split                    open
high_split                    high
low_split                     low
close_split                   close
volume_split                  volume
close_split                   adj_close (= close, convention split-only)
NULL                          vwap
0                             is_filled
'split'                       data_adjustment
'eodhd_eod'                   data_source
```

### Mapping → `stock_bars` (depuis le même payload)
```
EODHD bar (split-only)        stock_bars
---------------------------   -----------------------
code (normalize)              symbol
date + 16:00 ET               timestamp
"1D"                          timeframe
open_split                    open_price
high_split                    high_price
low_split                     low_price
close_split                   close_price
volume_split                  volume
0                             trade_count   (non fourni par EODHD bulk)
NULL                          vwa_price     (non fourni par EODHD bulk)
'split'                       data_adjustment
'eodhd_eod'                   data_source
```


Reste opérationnel (hors scope code)
Lancer le backfill réel : python -m dataIntegrityEngine.backfill_eodhd_history --write --years 5
Lancer 5 jours de shadow write : python -m dataIntegrityEngine.import_eodhd_bar --write quotidien
Audit go/no-go : python scripts/eodhd_phase4_volume_audit.py --lookback-days 60
Cutover : bars_provider: eodhd dans config.yaml (procédure complète dans prompt/iex/phase4_runbook.md)

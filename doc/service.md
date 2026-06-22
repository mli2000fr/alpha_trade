# Service — Guide d'usage

## Objectif

Ce document résume le rôle du dossier `service/` et les usages utiles pour :

- centraliser les clients HTTP externes du projet,
- gérer l'authentification multi-comptes Alpaca,
- exposer les appels market data, trading et news,
- enrichir les métadonnées société via Finnhub.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `service/alpaca/accounts.py` | Registre multi-comptes Alpaca |
| `service/alpaca/clientAlpaca.py` | Client market data Alpaca : assets + bars |
| `service/alpaca/clientNewsAlpaca.py` | Client Alpaca News |
| `service/alpaca/trading_client.py` | Client Alpaca Trading v2 |
| `service/finnhub/clientFinnhub.py` | Client Finnhub pour profils société / secteurs |

---

## 2. Prérequis

### 2.1 Variables d'environnement minimales

#### Pour Alpaca

```powershell
$env:ALPACA_API_KEY = "PK..."
$env:ALPACA_SECRET_KEY = "..."
```

#### Pour multi-comptes

```powershell
$env:ALPACA_LIVE1_API_KEY = "AK..."
$env:ALPACA_LIVE1_SECRET_KEY = "..."
$env:ALPACA_LIVE1_MODE = "live"
$env:ALPACA_LIVE1_LABEL = "Compte live"
```

#### Pour Finnhub

```powershell
$env:FINNHUB_API_KEY = "..."
```

Le code supporte aussi l'alias historique `CLE_FINNHUB`.

### 2.2 Alternative via `config.yaml`

Le registre Alpaca peut aussi charger :

- `alpaca.accounts` dans `config.yaml`
- avec placeholders `${VAR}` résolus depuis l'environnement

---

## 3. Exemples d'usage

### Lister les comptes Alpaca détectés

```powershell
python -c 'from service.alpaca.accounts import AccountRegistry; print([a.account_id for a in AccountRegistry.get().list_accounts()])'
```

### Résoudre un compte donné

```powershell
python -c 'from service.alpaca.accounts import AccountRegistry; acct = AccountRegistry.get().resolve("default"); print(acct.account_id, acct.mode)'
```

### Récupérer quelques actifs Alpaca

```powershell
python -c 'from service.alpaca.clientAlpaca import fetch_alpaca_assets; print(len(fetch_alpaca_assets()))'
```

### Récupérer des bars Alpaca pour un symbole

```powershell
python -c 'from service.alpaca.clientAlpaca import fetch_bars; bars = fetch_bars("AAPL", "1Day", start_date="2026-01-01T00:00:00Z"); print(len(bars))'
```

### Vérifier l'état du compte broker

```powershell
python -c 'from service.alpaca.trading_client import AlpacaTradingClient; client = AlpacaTradingClient("paper"); print(client.get_account().get("status"))'
```

### Récupérer le secteur Finnhub d'un symbole

```powershell
python -c 'from service.finnhub.clientFinnhub import fetch_symbol_sector; print(fetch_symbol_sector("AAPL"))'
```

---

## 4. Ce que fait le module

### 4.1 Registre multi-comptes Alpaca

`AccountRegistry` charge les comptes dans cet ordre :

1. `config.yaml`
2. variables d'environnement préfixées `ALPACA_<ID>_*`
3. fallback mono-compte `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`

### 4.2 Client market data Alpaca

`clientAlpaca.py` couvre notamment :

- la récupération des actifs,
- la récupération des bars OHLCV,
- la gestion des timeouts,
- la pagination côté données marché.

### 4.3 Client News Alpaca

`clientNewsAlpaca.py` couvre :

- le fetch paginé des news,
- la construction des headers Alpaca,
- la gestion timeout / rate limit,
- l'itération continue via `iter_news_pages()`.

### 4.4 Client Trading Alpaca

`trading_client.py` couvre :

- `submit_order()`
- `get_order()`
- `list_orders()`
- `cancel_order()`
- `replace_order()`
- `get_positions()`
- `get_account()`
- `get_clock()`

C'est la brique HTTP utilisée par `execution_engine`.

### 4.5 Client Finnhub

`clientFinnhub.py` couvre :

- le profil société,
- la récupération du secteur,
- le traitement des timeouts,
- le respect d'un intervalle minimal entre requêtes.

---

## 5. Pourquoi un appel service peut échouer

### 5.1 Credentials absents

Causes probables :

1. variables Alpaca absentes ;
2. compte demandé introuvable dans `AccountRegistry` ;
3. token Finnhub absent.

### 5.2 Rate limit ou timeout

Les clients gèrent des retries, mais peuvent finir par échouer si :

- le réseau reste indisponible ;
- le rate limit persiste ;
- la réponse API est invalide.

### 5.3 Mauvais mode de compte

Un compte `paper` et un compte `live` n'utilisent pas la même base URL côté trading.

---

## 6. Vérifications utiles

### Vérifier les comptes disponibles

```powershell
python -c 'from service.alpaca.accounts import AccountRegistry; print(AccountRegistry.get().list_account_ids())'
```

### Vérifier l'horloge marché Alpaca

```powershell
python -c 'from service.alpaca.trading_client import AlpacaTradingClient; client = AlpacaTradingClient("paper"); print(client.get_clock())'
```

---

## 7. Tests

### Tests ciblés service

```powershell
python -m pytest tests/test_clientAlpaca.py tests/test_clientNewsAlpaca.py tests/test_trading_client.py tests/test_clientFinnhub.py tests/test_client_finnhub.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseille :
1. valider d''abord `AccountRegistry` ;
2. tester `get_account()` ou `fetch_alpaca_assets()` ;
3. seulement ensuite brancher les modules metier ;
4. utiliser Finnhub surtout pour l''enrichissement secteur, pas comme dependance bloquante du pipeline principal.
### Sequence recommandee
```powershell
python -c "from service.alpaca.accounts import AccountRegistry; print(AccountRegistry.get().list_account_ids())"
python -c "from service.alpaca.trading_client import AlpacaTradingClient; print(AlpacaTradingClient(''paper'').get_account().get(''status''))"
python -c "from service.finnhub.clientFinnhub import fetch_symbol_sector; print(fetch_symbol_sector(''AAPL''))"
```
---
## 9. Helpers transverses Phase 2.3 (refactor)
### 9.1 `service/_http_retry.py` — politique unifiee
Tous les clients HTTP (`clientAlpaca`, `clientFinnhub`, `clientNewsAlpaca`) utilisent
desormais un helper unique :
```python
from service import RetryPolicy, request_with_retry
policy = RetryPolicy(
    max_attempts=10,
    base_delay_seconds=5.0,
    max_delay_seconds=60.0,
    timeout_seconds=15.0,
)
response = request_with_retry(
    session,                # requests.Session ou objet exposant get/post
    "GET",
    url,
    policy=policy,
    headers=headers,
    params=params,
)
```
Caracteristiques :
- backoff exponentiel + jitter ;
- retry uniquement sur `Timeout`, `ConnectionError`, `5xx`, `429` ;
- `4xx` (sauf 429) leve immediatement (`requests.HTTPError`) ;
- circuit breaker partage par hote (`service._http_retry.DEFAULT_CIRCUIT_BREAKER`)
  qui ouvre apres N echecs consecutifs et bloque les appels pendant un cooldown.
Telemetrie : compteurs disponibles via `service.get_telemetry()` (decompose par
hote : `requests`, `retries`, `circuit_open`).
### 9.2 Cache Finnhub 7 jours
`service/_finnhub_cache.py` cache les profils Finnhub pendant 7 jours dans
`artifacts/finnhub_cache/<symbol>.json`. Reduit fortement la consommation de
quota lors des reruns dataIntegrityEngine.
```python
from service.finnhub.clientFinnhub import fetch_company_profile
profile = fetch_company_profile("AAPL")  # cache hit/miss transparent
```
TTL configurable via env `FINNHUB_CACHE_TTL_DAYS` (defaut 7).
### 9.3 Parametre `feed=iex` Alpaca — impact concret
`service.alpaca.clientAlpaca.fetch_bars(symbol, timeframe, feed="iex")` :
- Le parametre `feed` est valide via `Literal["iex", "sip"]`. Toute autre
  valeur leve immediatement `ValueError` au lieu de partir en silence.
- `feed="iex"` est le defaut et le seul tier supporte par notre abonnement
  Alpaca actuel. **Implication tres importante** : les volumes et quotes IEX
  ne representent qu'une fraction (~2-3%) du volume consolide US. Cela
  introduit deux biais documentes :
  - `avg_dollar_volume_20d` sous-estime ; les filtres liquidite (selector)
    sont calibres en consequence (`spread_bps` relache, voir
    `selector/audit_selector.md` §IEX).
  - les `latest_quote` IEX peuvent etre 50-200ms en retard et avoir un
    spread artificiellement large hors heures de pointe. Le compteur
    `stale_quote_pct` (Phase 1.3) est propage dans `run_summary` pour
    rendre ce biais visible operationnellement.
- Si vous obtenez un acces SIP plus tard, basculer simplement
  `ALPACA_DATA_FEED=sip` (env var) ou changer le defaut.
  **Ne JAMAIS** appeler `fetch_bars(..., feed="sip")` en dur dans le code
  metier : le bias-tracking suppose que `feed` est uniforme.
Voir aussi `doc/dataIntegrityEngine.md` section "Limites IEX".
### 9.4 Tests
```powershell
python -m pytest tests/test_phase1_http_retry.py tests/test_clientAlpaca.py tests/test_client_finnhub.py -q --no-cov
```

<!-- BEGIN provider_table_matrix -->
<!-- generated by scripts/generate_data_lineage.py — do not edit by hand -->

### 10. Matrice Provider → Tables alimentées

| Provider | Module(s) service | Tables alimentées (DB) | Mode appel | Criticité |
|---|---|---|---|---|
| `eodhd` | `service/eodhd/` | `stock_bars_daily(provider=eodhd)`, `stock_bars(1D)`, `corporate_actions_events(div/split)` | bulk EOD + on-demand | P1 |
| `alpaca` | `service/alpaca/` | `stock_assets`, `stock_bars(intraday)`, `stock_quote_snapshots`, `news_articles`, `execution_orders`, `execution_positions`, `broker_positions_snapshots` | REST + WS | P1 |
| `finnhub` | `service/finnhub/` | `stock_metadata`, `earnings_calendar` | REST throttle | P2 |
| `yahoo` | `service/yahoo/` | `corporate_actions_events (cross-check)` | best-effort | P3 |
| `stooq` | `service/stooq/` | `cleaning_audit_runs.cross_check_anomalies` | best-effort | P3 |
| `tiingo` | `service/tiingo/` | `(réservé, pas de table prod)` | inactif | — |

> Matrice détaillée table-par-table : voir [`doc/data_lineage_matrix.md`](data_lineage_matrix.md).

---

## 10. Module Alerting & Notifications (Sprint S9)

### 10.1 Architecture

**Fichier** : `service/alerting.py`

Le module expose une interface uniforme `Notifier` (Protocol) avec 6 implémentations :

| Canal | Classe | Variable d'environnement | Fallback |
|---|---|---|---|
| **Slack** | `SlackNotifier` | `ALPHA_TRADE_SLACK_WEBHOOK` | LogNotifier |
| **Email SMTP** | `EmailNotifier` | `ALPHA_TRADE_SMTP_HOST`, `_PORT`, `_FROM`, `_TO`, `_USER`, `_PASSWORD` | LogNotifier |
| **Telegram** | `TelegramNotifier` | `ALPHA_TRADE_TELEGRAM_BOT_TOKEN`, `ALPHA_TRADE_TELEGRAM_CHAT_ID` | LogNotifier |
| **Discord** | `DiscordNotifier` | `ALPHA_TRADE_DISCORD_WEBHOOK` | LogNotifier |
| **SMS (Twilio)** | `SMSNotifier` | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `NUM_SMS_ALERT` | LogNotifier |
| **Log (fallback)** | `LogNotifier` | Toujours disponible | — |

### 10.2 Variables d'environnement — Alerting

```bash
# ─── Slack ───
$env:ALPHA_TRADE_SLACK_WEBHOOK = "https://hooks.slack.com/services/..."

# ─── Email SMTP ───
$env:ALPHA_TRADE_SMTP_HOST = "smtp.gmail.com"
$env:ALPHA_TRADE_SMTP_PORT = "587"
$env:ALPHA_TRADE_SMTP_FROM = "alpha-trade@example.com"
$env:ALPHA_TRADE_SMTP_TO = "ops@example.com"
$env:ALPHA_TRADE_SMTP_USER = "user@example.com"
$env:ALPHA_TRADE_SMTP_PASSWORD = "..."

# ─── Telegram ───
$env:ALPHA_TRADE_TELEGRAM_BOT_TOKEN = "123456:ABC-DEF..."
$env:ALPHA_TRADE_TELEGRAM_CHAT_ID = "-1001234567890"

# ─── Discord ───
$env:ALPHA_TRADE_DISCORD_WEBHOOK = "https://discord.com/api/webhooks/..."

# ─── SMS (Twilio) ───
$env:TWILIO_ACCOUNT_SID = "AC..."
$env:TWILIO_AUTH_TOKEN = "..."
$env:TWILIO_PHONE_NUMBER = "+1234567890"
$env:NUM_SMS_ALERT = "+33612345678"
```

### 10.3 Fonction principale

```python
from service.alerting import send_system_alert

send_system_alert(
    event="CIRCUIT_BREAKER_FIRED",
    payload={"drawdown_pct": 15.2, "threshold_pct": 15.0},
    severity="critical",
)
# → Diffusé sur TOUS les canaux configurés (Slack + Telegram + Discord + SMS + Email + Log)
```

**Anti-doublon** : SHA256(event + payload) avec cooldown de 5 minutes (configurable via `cooldown_seconds`).

### 10.4 Événements couverts

| Événement | Fichier émetteur | Severity |
|---|---|---|
| `CIRCUIT_BREAKER_FIRED` | `risk_management/circuit_breaker.py` | `critical` |
| `DRAWDOWN_APPROACHING` | `risk_management/circuit_breaker.py` | `warning` |
| `KILL_SWITCH_ACTIVATED` | `execution_engine/executor.py` | `critical` |
| `SLIPPAGE_EXCEEDED` | `execution_engine/executor.py` | `warning` |
| `CASH_LEDGER_MISALIGNMENT` | `execution_engine/cash_ledger_guard.py` | `critical` |
| `SYNC_QUOTES_FAILED` | `dataIntegrityEngine/sync_latest_quotes.py` | `critical` |
| `API_ALPACA_*_FAILURE` | `service/alpaca/clientAlpaca.py` | `critical`/`warning` |
| `WATCHER_STALE_HEARTBEAT` | `ihm/services/ops_supervision.py` | `critical` |
| `EMPTY_TRADING_UNIVERSE` | `selector/scanner.py` | `warning` |
| `ML_MODEL_DRIFT_KILL_SWITCH` | `modelFactory/drift_policy.py` | `critical` |
| `ML_MODEL_DRIFT_WARNING` | `modelFactory/drift_policy.py` | `warning` |

---

## 11. Module Métriques Prometheus (Sprint S9)

**Fichier** : `service/prometheus_metrics.py`

### 11.1 Variables d'environnement

```bash
# Port du serveur HTTP /metrics (défaut 9090)
$env:ALPHA_TRADE_PROMETHEUS_PORT = "9090"

# Chemin du fichier .prom pour node_exporter textfile collector
$env:ALPHA_TRADE_PROMETHEUS_FILE = "artifacts/metrics/alpha_trade.prom"
```

### 11.2 Métriques exposées

| Métrique | Type | Description |
|---|---|---|
| `alpha_trade_api_errors_total` | counter | Erreurs API par service (`alpaca`, `finnhub`, etc.) |
| `alpha_trade_execution_runs_total` | counter | Nombre total de runs d'exécution |
| `alpha_trade_alerts_total` | counter | Alertes émises par severity |
| `alpha_trade_circuit_breaker_active` | gauge | 1 si circuit breaker actif |
| `alpha_trade_heartbeat_stale` | gauge | 1 si heartbeat watcher stale |
| `alpha_trade_empty_universe` | gauge | 1 si univers de trading vide |
| `alpha_trade_kill_switch_active` | gauge | 1 si kill switch exécution actif |
| `alpha_trade_model_drift_active` | gauge | 1 si drift ML détecté |
| `alpha_trade_cash_ledger_aligned` | gauge | 1 si cash ledger aligné, 0 si désaligné |

### 11.3 Utilisation

```python
# Incrémenter un compteur
from service.prometheus_metrics import bump_api_error, bump_alert
bump_api_error("alpaca")
bump_alert("critical")

# Mettre à jour une gauge
from service.prometheus_metrics import set_circuit_breaker_active
set_circuit_breaker_active(True)

# Écrire le fichier pour node_exporter
from service.prometheus_metrics import write_metrics_file
write_metrics_file()  # → artifacts/metrics/alpha_trade.prom

# Démarrer le serveur HTTP (daemon thread)
from service.prometheus_metrics import start_prometheus_server
start_prometheus_server(port=9090)  # → GET /metrics, GET /health
```

### 11.4 Intégration Grafana

Configurer Prometheus pour scraper :
- **Fichier** : `scrape_configs` → `file_sd_configs` pointant vers `artifacts/metrics/`
- **HTTP** : `scrape_configs` → `static_configs` ciblant `localhost:9090`

Dashboard Grafana recommandé : graphiques de santé avec alertes sur :
- `rate(alpha_trade_api_errors_total[5m]) > 0.05` (taux d'erreur > 5%)
- `alpha_trade_circuit_breaker_active == 1`
- `alpha_trade_heartbeat_stale == 1`
- `alpha_trade_cash_ledger_aligned == 0`

---

## 12. Cash Ledger Guard (Sprint S9)

**Fichier** : `execution_engine/cash_ledger_guard.py`

```python
from execution_engine.cash_ledger_guard import check_cash_ledger_consistency

check_cash_ledger_consistency(
    settled_cash=5000.0,
    unsettled_cash=12000.0,
    market_value=8000.0,
    reported_equity=25000.0,
    tolerance_pct=0.01,  # 1%
    account_id="live1",
)
# → Alerte CASH_LEDGER_MISALIGNMENT si écart > 1%
```

Intégré automatiquement dans `execution_engine/executor.py` après chaque construction de l'état de compte.

<!-- END provider_table_matrix -->


---

## Note Plan v2 / Plan ML v2 (juin 2026)

Le module `service/` n'a pas ete modifie pour le support short selling ou
le mode ternaire ML. Les services broker (Alpaca), market data (EODHD),
et news (Finnhub) restent inchanges.

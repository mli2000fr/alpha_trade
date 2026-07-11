# Runbook — Incident provider data (Phase 7.6)

> **Audience** : opérateur on-call Alpha Trade.
> **Périmètre** : panne ou dégradation d'un fournisseur upstream (Alpaca,
> Finnhub, Stooq, Yahoo).

---

## 1. Détection

### Signaux automatiques (alertes push)

> **Sprint S9** : Tous les signaux ci-dessous déclenchent désormais une alerte
> multi-canal automatique (Slack, Telegram, Discord, SMS, Email) en plus des
> métriques Prometheus. Voir `doc/service.md` §10-11 pour la configuration.

| Signal | Source | Seuil | Alerte auto ? |
|---|---|---|---|
| Erreur API Alpaca (auth 401/403) | `service/alpaca/clientAlpaca.py` | immédiat | ✅ `API_ALPACA_*_FAILURE` |
| Erreur API Alpaca (5xx répétés) | `service/_http_retry.py` | après retries | ✅ `API_ALPACA_*_FAILURE` |
| Sync quotes échoué | `dataIntegrityEngine/sync_latest_quotes.py` | run en erreur | ✅ `SYNC_QUOTES_FAILED` |
| Univers de trading vide | `selector/scanner.py` | 0 candidats | ✅ `EMPTY_TRADING_UNIVERSE` |
| Métrique `alpha_trade_data_freshness_hours` | Prometheus `/metrics` | > 36h | ⚠️ Grafana alert |
| Code retour ≠ 0 de `import-bars` | run_summary | exit_code ≠ 0 | ⚠️ Log + IHM |
| `errors > 0` dans `cleaning_audit_runs` | DB | toute valeur | ⚠️ Log + IHM |

### Signaux automatiques (Prometheus)

| Signal | Source | Seuil |
|---|---|---|
| Métrique `alpha_trade_api_errors_total{service="alpaca"}` | Prometheus (`/metrics`) | rate > 0.05/s |
| Métrique `alpha_trade_empty_universe` | Prometheus (`/metrics`) | == 1 |
| HTTP 5xx répétés dans `service/_http_retry.py` (logs) | logs | ≥ 5 / minute |

### Diagnostic rapide

```powershell
# 1. Inspecter la fraîcheur des principales tables
mysql -e "SELECT table_name, MAX(updated_at) FROM stock_bars_daily; SELECT MAX(updated_at) FROM stock_quote_snapshots;"

# 2. Vérifier les derniers run_summary
python -m dataIntegrityEngine status --last 5

# 3. Pinger les providers
curl -sS https://data.alpaca.markets/v2/stocks/AAPL/bars?timeframe=1Day -H "APCA-API-KEY-ID: $env:ALPACA_KEY"
curl -sS "https://stooq.com/q/d/l/?s=aapl.us&i=d" | head
```

---

## 2. Bascule cross-check (Stooq / Yahoo)

### Stooq (volumes / OHLC daily)

Si Alpaca/IEX renvoie des bars dégradés mais que la pipeline doit continuer :

```python
from dataIntegrityEngine.cross_check_stooq import compare_with_stooq
anomalies = compare_with_stooq(ingested_bars=..., lookback_days=5)
```

Persister dans `cleaning_audit_runs.cross_check_anomalies` (JSON).

### Yahoo (dividendes)

```bash
python -m corporate_actions sync --cross-check yahoo
```

---

## 3. Gel pipeline (kill switch)

Si le risque est trop élevé pour exécuter le run du jour :

```bash
# Annule tous les ordres ouverts pour un compte
python -m execution_engine cancel-all --account live1
```

L'exécution journalière reste **bloquée** tant que le watcher détecte un
`MANUAL_REVIEW` non résolu (cf. `doc/execution_engine.md` §runbook).

---

## 4. Escalade

| Sévérité | Critère | Action |
|---|---|---|
| **P1** | Live trading impacté, equity broker indisponible | Kill switch immédiat + notif + post-mortem ≤ 24h |
| **P2** | Pipeline batch en retard, pas d'impact ordre live | Investigation, retry à H+1 |
| **P3** | Cross-check anomalies | Triage J+1, annoter `cleaning_audit_runs` |

---

## 5. Post-mortem template

Voir `doc/runbook_reconciliation.md` §template post-mortem (mêmes sections).

Fichier suggéré : `doc/postmortems/<YYYY-MM-DD>_<provider>_<incident>.md`.

---

**Réf.** : audit_global §7.6 ; `prompt/refactor/plan.md` Phase 7.


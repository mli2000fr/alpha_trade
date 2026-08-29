# Observabilité — Endpoint `/metrics` Prometheus (Phase 7.5)

> **Audience** : opérateurs Alpha Trade.
> **Périmètre** : exposition de métriques Prometheus minimales depuis les
> daemons (`watcher`, `ihm`) ou les CLI longs.

---

## 1. Activation

### Dépendance

```bash
pip install 'alpha-trade[observability]'   # extra prometheus_client
```

### Démarrage

```python
from core.metrics import start_metrics_server
start_metrics_server(port=9100)            # ou via env ALPHA_TRADE_METRICS_PORT
```

Variables d'environnement :

| Variable | Effet |
|---|---|
| `ALPHA_TRADE_METRICS_PORT` | Port d'écoute (off si vide / non numérique) |

> **Sécurité** : binder `localhost` (paramètre `addr=`) si l'IHM est exposée
> hors VPN. Le défaut `0.0.0.0` est volontaire pour les déploiements daemon
> derrière reverse proxy interne.

---

## 2. Métriques canoniques

| Nom | Type | Labels | Sémantique |
|---|---|---|---|
| `alpha_trade_run_summary_total` | Counter | `module`, `status` | Compte les `run_summary` publiés |
| `alpha_trade_data_freshness_hours` | Gauge | `table` | Âge des dernières données |
| `alpha_trade_iex_stale_quote_pct` | Gauge | — | % quotes stale (audit IEX) |
| `alpha_trade_iex_zero_volume_count` | Gauge | — | Symboles à volume 0 sur 30j |
| `alpha_trade_watcher_heartbeat_age_seconds` | Gauge | `account_id` | Âge dernier heartbeat |
| `alpha_trade_ml_drift_status` | Gauge | `model_id` | 0=OK, 1=WARN, 2=ALERT |

---

## 3. Scrape Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: alpha_trade
    scrape_interval: 30s
    static_configs:
      - targets: ['localhost:9100']
```

Test rapide :

```bash
curl -sS localhost:9100/metrics | grep alpha_trade
```

---

## 4. Exemples PromQL

```promql
# Nombre de runs OK les 24 dernières heures par module
sum by (module) (increase(alpha_trade_run_summary_total{status="OK"}[24h]))

# Watcher dont heartbeat > 5 minutes
alpha_trade_watcher_heartbeat_age_seconds > 300

# Données stock_bars_daily en retard (> 36h)
alpha_trade_data_freshness_hours{table="stock_bars_daily"} > 36

# Modèles ML en alert
alpha_trade_ml_drift_status >= 2
```

---

## 5. Alertes recommandées

| Nom | Condition | Sévérité |
|---|---|---|
| `WatcherHeartbeatStale` | `> 600s` pendant 5 min | P1 |
| `DataFreshnessStale` | `stock_bars_daily > 36h` | P2 |
| `MLDriftAlert` | `ml_drift_status == 2` pendant 1h | P2 |
| `RunSummaryFailureSpike` | `increase(run_summary_total{status="ERROR"}[15m]) > 0` | P2 |

Un jeu de base prêt à l'emploi est désormais versionné :

- dashboard Grafana : `doc/monitoring/grafana_dashboard_alpha_trade.json`
- règles Prometheus : `doc/monitoring/prometheus_alert_rules.yml`

Ces livrables couvrent un socle Sprint 5 (monitoring opérateur + alertes
standards). L'industrialisation complète (SLO formels, Alertmanager multi-route,
on-call, dashboard avancé par module) reste une extension long terme.

---

**Réf.** : audit_global §7.5 ; `core/metrics.py` ; `prompt/refactor/plan.md` Phase 7.


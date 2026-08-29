# Actifs Prometheus et Grafana

- `prometheus_alert_rules.yml` utilise les métriques exposées par `service/prometheus_metrics.py` ;
- `grafana_dashboard_alpha_trade.json` est le dashboard importable correspondant.

Le registre est local au processus et repart à zéro au redémarrage. Après changement des métriques, revalider chaque expression dans ces deux fichiers, la syntaxe PromQL/Grafana et le déclenchement en environnement de test. Voir [alerting et métriques](../alerting_et_metriques.md).


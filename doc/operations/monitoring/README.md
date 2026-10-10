# Actifs Prometheus et Grafana

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

- `prometheus_alert_rules.yml` utilise les métriques exposées par `service/prometheus_metrics.py` ;
- `grafana_dashboard_alpha_trade.json` est le dashboard importable correspondant.

Le registre est local au processus et repart à zéro au redémarrage. Après changement des métriques, revalider chaque expression dans ces deux fichiers, la syntaxe PromQL/Grafana et le déclenchement en environnement de test. Voir [alerting et métriques](../alerting_et_metriques.md).


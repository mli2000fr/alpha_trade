# 01 — Global Scorecard — Alpha Trade

> **Date** : mai 2026 | **Méthode** : audit code + doc + config exhaustif

---

## Tableau de bord global

| Module / Domaine | Note /10 | Verdict court |
|---|---|---|
| **Documentation** | 8.0 | Complète, actualisée, quelques écarts résiduels |
| **Configuration** (`config.yaml` + presets) | 7.0 | Cohérente, 1 anomalie P1 sur preset micro-compte |
| **dataIntegrityEngine** | 7.5 | Solide, EODHD primaire bien implémenté, tests complets |
| **database / migrations** | 7.0 | SQLAlchemy Core, Alembic présent, lineage matrix à corriger |
| **service / providers** | 7.5 | Alpaca, EODHD, Finnhub, Stooq bien encapsulés, retry/CB |
| **screener** | 7.0 | Fonctionnel, ProcessPoolExecutor, run_summaries, quelques risques univers vide |
| **selector** | 7.5 | AlphaScanner multi-facteurs, profils stricts partagés, PIT-safe |
| **event_sentiment** | 6.5 | FinBERT présent, pondération configurable, relevance backfill non systématique |
| **modelFactory** | 6.5 | Gouvernance multi-champions, mais DB résumée (selected_model absent) |
| **risk_management** | 7.5 | ATR/Kelly, corrélation, circuit breaker, Market-Aware intégré |
| **execution_engine** | 7.5 | Chaîne canonique complète, idempotence, OCO, watcher post-exec |
| **corporate_actions** | 7.0 | Dividendes/splits, idempotence, audit trail, provider primaire à confirmer |
| **backtesting** | 7.0 | modes research/pipeline, PIT, phases fidélité, diagnostic screener |
| **ihm** | 7.5 | Streamlit complet, pipeline workflow, Market-Aware, watcher supervision |
| **observabilité / run summaries / logs** | 7.0 | RotatingFileHandler, run_summaries, audit trail DB, pas de monitoring externe |
| **sécurité / readiness prod** | 7.0 | Secrets env/vault, scan literals, confirmation live, SSL DB absent |
| **qualité logicielle globale** | 8.0 | 250+ tests, mypy, ruff, idempotence généralisée, dette technique réduite |

---

## Note globale : **7,2 / 10**

### Décomposition par catégorie

| Catégorie | Poids | Note |
|---|---|---|
| Données / intégrité | 20% | 7.5 |
| Signal / ML | 20% | 6.8 |
| Risk / exécution | 25% | 7.5 |
| Infrastructure / qualité | 20% | 7.7 |
| IHM / ops | 15% | 7.3 |
| **Moyenne pondérée** | **100%** | **7.2** |

---

## Comparaison niveaux professionnels

| Niveau | Note typique | Alpha Trade actuel |
|---|---|---|
| Amateur sérieux | 3–4/10 | ❌ Très au-dessus |
| Indépendant avancé | 5–6.5/10 | ✅ Dépassé |
| Quasi-pro / pre-institutional | 7–8/10 | 🟡 **Ici (7.2 → vise 8)** |
| Pro-grade buy-side / prop desk | 8–9/10 | ❌ ~1 sprint majeur manque |
| Institutionnel très mature | 9.5–10/10 | ❌ 3–4 sprints majeurs |

---

## Résumé des axes de progrès pour atteindre 8.5+

1. **ML governance en DB** : persister `selected_model`, `decision_threshold` dans `model_predictions`
2. **Notifications externes** : email/Slack circuit breaker, fin de run, erreurs P0
3. **Orchestrateur pipeline** : remplacer le pipeline manuel IHM par scheduler (Prefect/Airflow ou équivalent léger)
4. **SSL DB + vault formalisé** : connexion MySQL chiffrée, rotation secrets automatique
5. **Monitoring live** : Prometheus/Grafana ou équivalent pour métriques pipeline
6. **Corriger anomalies P0/P1** : capital preset micro-compte, lineage matrix, suppression vestiges vectorbt doc


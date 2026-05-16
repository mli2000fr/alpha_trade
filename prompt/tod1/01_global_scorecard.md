# 01 — Global Scorecard — Alpha Trade

> **Date** : mai 2026 | **Méthode** : audit code + doc + config exhaustif

---

## Tableau de bord global

| Module / Domaine | Note /10 | Verdict court |
|---|---|---|
| **Documentation** | 9.0 | Complète, vectorbt éliminé ✅, lineage matrix synchronisée ✅ (A-002 ✅, A-004 ✅, A-018 ✅) |
| **Configuration** (`config.yaml` + presets) | 7.5 | Preset micro-compte corrigé ✅ (A-001 ✅), PDT rule margin P2 reste (A-006) |
| **dataIntegrityEngine** | 7.5 | Solide, EODHD primaire bien implémenté, tests complets |
| **database / migrations** | 7.5 | SQLAlchemy Core, Alembic, unicité model_predictions ✅ (A-009 ✅), lineage régénérée ✅ (A-002 ✅) |
| **service / providers** | 7.5 | Alpaca, EODHD, Finnhub, Stooq bien encapsulés, retry/CB |
| **screener** | 7.0 | Fonctionnel, ProcessPoolExecutor, run_summaries, quelques risques univers vide |
| **selector** | 7.5 | AlphaScanner multi-facteurs, profils stricts partagés, PIT-safe |
| **event_sentiment** | 6.5 | FinBERT présent, pondération configurable, relevance backfill non systématique |
| **modelFactory** | 7.0 | Gouvernance ML en DB complète ✅ (A-003 ✅), multi-champions, mais LSTM sur séries courtes |
| **risk_management** | 7.5 | ATR/Kelly, corrélation, circuit breaker, Market-Aware intégré |
| **execution_engine** | 7.5 | Chaîne canonique complète, idempotence, OCO, watcher post-exec |
| **corporate_actions** | 7.5 | Dividendes/splits, idempotence, provider CA documenté ✅ (A-005 ✅) |
| **backtesting** | 7.0 | modes research/pipeline, PIT, phases fidélité, ParquetCache non branché (A-010), résidu vectorbt éliminé ✅ |
| **ihm** | 7.5 | Streamlit complet, pipeline workflow, Market-Aware, watcher supervision |
| **observabilité / run summaries / logs** | 7.0 | RotatingFileHandler, run_summaries, audit trail DB, pas de monitoring externe |
| **sécurité / readiness prod** | 7.5 | Secrets env/vault, scan literals, SSL MySQL activable ✅ (A-012 ✅) |
| **qualité logicielle globale** | 8.5 | 255+ tests (5 nouveaux A-001/A-016), mypy, ruff, idempotence généralisée |

---

## Note globale : **7,5 / 10** *(post Sprint S1 — configuration et lineage matrix corrigées)*

### Décomposition par catégorie

| Catégorie | Poids | Note |
|---|---|---|
| Données / intégrité | 20% | 7.5 |
| Signal / ML | 20% | 7.0 |
| Risk / exécution | 25% | 7.5 |
| Infrastructure / qualité | 20% | 8.0 |
| IHM / ops | 15% | 7.3 |
| **Moyenne pondérée** | **100%** | **7.5** |

---

## Comparaison niveaux professionnels

| Niveau | Note typique | Alpha Trade actuel |
|---|---|---|
| Amateur sérieux | 3–4/10 | ❌ Très au-dessus |
| Indépendant avancé | 5–6.5/10 | ✅ Dépassé |
| Quasi-pro / pre-institutional | 7–8/10 | 🟡 **Ici (7.5 post-S1 → vise 8.0 post-S2)** |
| Pro-grade buy-side / prop desk | 8–9/10 | ❌ ~1 sprint majeur manque |
| Institutionnel très mature | 9.5–10/10 | ❌ 3–4 sprints majeurs |

---

## Résumé des axes de progrès pour atteindre 8.5+

> ✅ = Déjà accompli — ne nécessite plus d'action

1. ✅ **ML governance en DB** : `selected_model`, `decision_threshold` déjà persistés dans `model_predictions` (A-003 ✅)
2. ✅ **SSL DB** : connexion MySQL avec TLS activable via `DB_SSL_CA_PATH` (A-012 ✅)
3. ✅ **Provider CA documenté** : règle de sélection Alpaca/EODHD clarifiée dans DOC_FONCTIONNELLE + lineage matrix (A-005 ✅)
4. ✅ **Preset micro-compte corrigé** : `risk_max_positions: 3`, `min_notional: 500$` (A-001 ✅ Sprint S1)
5. ✅ **Lineage matrix synchronisée** : `execution_order_requests`, `execution_broker_orders`, `execution_events` (A-002 ✅ Sprint S1)
6. ✅ **PDT rule commentée sur comptes cash** : 4 presets annotés (A-016 ✅ Sprint S1)
7. **PDT rule margin** : passer `pdt_rule: "auto"` sur les 3 presets margin (A-006 → Sprint S2)
8. **min_close uniformisé** : `selector_min_close: 10.0` sur `capital_0_5000` (A-007 → Sprint S2)
9. **Notifications externes** : email/Slack circuit breaker, fin de run, erreurs P0 (A-013 → Sprint S3)
10. **Orchestrateur pipeline** : scheduler léger ou Prefect (Sprint S5)
11. **Monitoring live** : Prometheus/Grafana ou équivalent (Sprint S5)


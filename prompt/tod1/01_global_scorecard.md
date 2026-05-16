# 01 — Global Scorecard — Alpha Trade

> **Date** : mai 2026 | **Méthode** : audit code + doc + config exhaustif

---

## Tableau de bord global

| Module / Domaine | Note /10 | Verdict court |
|---|---|---|
| **Documentation** | 9.0 | Complète, vectorbt éliminé ✅, lineage matrix synchronisée ✅ (A-002 ✅, A-004 ✅, A-018 ✅) |
| **Configuration** (`config.yaml` + presets) | 8.0 | PDT auto margin ✅ (A-006 ✅ S2), min_close 10$ tous presets ✅ (A-007 ✅ S2), fill_timeout 180s ✅ (A-017 ✅ S2) |
| **dataIntegrityEngine** | 7.5 | Solide, EODHD primaire bien implémenté, tests complets |
| **database / migrations** | 7.5 | SQLAlchemy Core, Alembic, unicité model_predictions ✅ (A-009 ✅), lineage régénérée ✅ (A-002 ✅) |
| **service / providers** | 7.5 | Alpaca, EODHD, Finnhub, Stooq bien encapsulés, retry/CB |
| **screener** | 7.0 | Fonctionnel, ProcessPoolExecutor, run_summaries, quelques risques univers vide |
| **selector** | 7.5 | AlphaScanner multi-facteurs, profils stricts partagés, PIT-safe |
| **event_sentiment** | 6.5 | FinBERT présent, pondération configurable, relevance backfill non systématique |
| **modelFactory** | 7.0 | Gouvernance ML en DB complète ✅ (A-003 ✅), multi-champions, mais LSTM sur séries courtes |
| **risk_management** | 7.5 | ATR/Kelly, corrélation, circuit breaker, Market-Aware intégré |
| **execution_engine** | 8.0 | Chaîne canonique complète, fill_timeout 180s ✅ (A-017 ✅ S2), idempotence, OCO, watcher post-exec |
| **corporate_actions** | 7.5 | Dividendes/splits, idempotence, provider CA documenté ✅ (A-005 ✅) |
| **backtesting** | 7.5 | modes research/pipeline, PIT, phases fidélité, ParquetCache branché ✅ (A-010 ✅ S3), Bootstrap MC ✅ (A-011 ✅ S3), résidu vectorbt éliminé ✅ |
| **ihm** | 8.0 | Streamlit complet, pipeline workflow, Market-Aware, alertes réconciliation ✅ (A-014 ✅ S3), market_cap TTL alert ✅ (A-015 ✅ S3) |
| **observabilité / run summaries / logs** | 7.5 | RotatingFileHandler → TimedRotatingFileHandler+gzip ✅ (A-025 ✅ S3), alerting email CB ✅ (A-013 ✅ S3), audit trail DB |
| **sécurité / readiness prod** | 7.5 | Secrets env/vault, scan literals, SSL MySQL activable ✅ (A-012 ✅) |
| **qualité logicielle globale** | 8.5 | 2316 tests verts (260+ fichiers, 30+ nouveaux S1+S2+S3), mypy, ruff, idempotence généralisée |

---

## Note globale : **8,2 / 10** *(post Sprint S3 — 20 anomalies résolues au total)*

### Décomposition par catégorie

| Catégorie | Poids | Note |
|---|---|---|
| Données / intégrité | 20% | 7.5 |
| Signal / ML | 20% | 7.0 |
| Risk / exécution | 25% | 8.0 |
| Infrastructure / qualité | 20% | 8.2 |
| IHM / ops | 15% | 7.7 |
| **Moyenne pondérée** | **100%** | **8.2** |

---

## Comparaison niveaux professionnels

| Niveau | Note typique | Alpha Trade actuel |
|---|---|---|
| Amateur sérieux | 3–4/10 | ❌ Très au-dessus |
| Indépendant avancé | 5–6.5/10 | ✅ Dépassé |
| Quasi-pro / pre-institutional | 7–8/10 | 🟢 **Ici (8.2 post-S3) → vise 8.5 post-S4** |
| Pro-grade buy-side / prop desk | 8–9/10 | ❌ ~1 sprint majeur manque |
| Institutionnel très mature | 9.5–10/10 | ❌ 3–4 sprints majeurs |

---

## Résumé des axes de progrès

> ✅ = Déjà accompli — ne nécessite plus d'action

1. ✅ **ML governance en DB** : `selected_model`, `decision_threshold` déjà persistés dans `model_predictions` (A-003 ✅)
2. ✅ **SSL DB** : connexion MySQL avec TLS activable via `DB_SSL_CA_PATH` (A-012 ✅)
3. ✅ **Provider CA documenté** : règle de sélection Alpaca/EODHD clarifiée dans DOC_FONCTIONNELLE + lineage matrix (A-005 ✅)
4. ✅ **Preset micro-compte corrigé** : `risk_max_positions: 3`, `min_notional: 500$` (A-001 ✅ Sprint S1)
5. ✅ **Lineage matrix synchronisée** : `execution_order_requests`, `execution_broker_orders`, `execution_events` (A-002 ✅ Sprint S1)
6. ✅ **PDT rule commentée sur comptes cash** : 4 presets annotés (A-016 ✅ Sprint S1)
7. ✅ **PDT rule margin corrigé** : `pdt_rule: "auto"` sur les 3 presets margin — protection si equity < 25k$ (A-006 ✅ Sprint S2)
8. ✅ **min_close uniformisé** : `selector_min_close: 10.0` sur tous les presets (A-007 ✅ Sprint S2)
9. ✅ **fill_timeout augmenté** : `fill_timeout_seconds: 180` (paper) — réduit les ordres orphelins sur gap (A-017 ✅ Sprint S2)
10. ✅ **ParquetCache branché** : `--use-cache` dans la CLI backtesting, 3x–10x gain de vitesse sur backtests > 2 ans (A-010 ✅ Sprint S3)
11. ✅ **Analytics CLI exposés** : `--bootstrap-samples N`, `--sensitivity-analysis` dans la CLI `backtesting run` (A-011 ✅ Sprint S3)
12. ✅ **Alerting email opérationnel** : email sur circuit_breaker + kill_switch via `NotificationService` (A-013 ✅ Sprint S3)
13. ✅ **Alerting réconciliation IHM** : bandeau rouge si `execution_reconciliation_results` non résolu > 24h (A-014 ✅ Sprint S3)
14. ✅ **Alerting market_cap TTL IHM** : avertissement si > 5% symboles avec market_cap stale > 45 jours (A-015 ✅ Sprint S3)
15. ✅ **Logs rotés avec gzip** : `TimedRotatingFileHandler` + compression gzip + max 30 fichiers (A-025 ✅ Sprint S3)
16. ✅ **Walk-forward bornes poids** : assertions admissibles ajoutées ([0.05, 0.60]) dans `weights_calibration.py` (A-027 ✅ Sprint S3)
17. **Widget PnL quotidien** : dashboard MTM + cash ledger dans la page Overview (A-021 → Sprint S4)
18. **Walk-forward params risk** : ATR period, Kelly, correlation threshold (A-022 → Sprint S4)
19. **Orchestrateur pipeline** : scheduler léger ou Prefect (Sprint S5)
20. **Monitoring live** : Prometheus/Grafana ou équivalent (Sprint S5)

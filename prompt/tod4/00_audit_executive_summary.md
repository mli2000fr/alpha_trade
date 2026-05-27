# 00 — Synthèse d'audit (Executive Summary)

**Application** : Alpha Trade  
**Version** : 0.3.0  
**Auditeur** : Principal software + quant trading + architecture data/ops  
**Date** : mai 2026  
**Périmètre** : Audit exhaustif code + documentation + configuration + paramétrage + IHM + cohérence inter-modules

---

## Verdict global

**Alpha Trade est une application de swing trading US de qualité solide, avec une architecture modulaire bien pensée et un pipeline de bout en bout fonctionnel.** Elle se situe à un niveau **« prometteur → solide »**, significativement au-dessus d'une application amateur, mais encore en dessous d'un standard buy-side professionnel.

**Note globale : 7,3 / 10**

L'application est **exploitable en paper trading discipliné dès aujourd'hui**. Pour un passage en live trading, plusieurs corrections de sécurité et de cohérence sont nécessaires (voir plan de sprints).

---

## Forces majeures

1. **Architecture modulaire claire** : séparation nette entre ingestion, screening, sélection, sentiment, ML, risk, exécution, corporate actions, backtesting, IHM.
2. **Convention de prix explicite et cohérente** : `data_adjustment='split'` portée de bout en bout, avec dividendes tracés via `portfolio_cash_ledger`.
3. **Provider OHLCV switch maîtrisé** : EODHD primaire, Alpaca rétrocompat, no-op contrôlé, pas de fallback silencieux.
4. **Exécution canonique robuste** : chaîne `targets → requests → orders → fills → positions/lots → reconciliation` bien conçue, multi-comptes, idempotence, TCA.
5. **Presets de capital détaillés** : 7 tranches avec paramètres risk/selector/screener/execution différenciés, couvrant de 0 à 100 k$+.
6. **Backtesting PIT intégré** : fidélité point-in-time, contraintes compte réalistes (margin/cash/PDT/swing_only), phases de replay.
7. **Profil strict partagé** (`STRICT_SWING_CASH_FILTERS`) : source unique de vérité pour screener + backfill + backtest.
8. **Documentation riche** : ~30 fichiers dans `doc/`, conventions centralisées, matrices de lineage, runbooks.
9. **Tests significatifs** : couverture des modules critiques avec 40+ fichiers de test.

---

## Faiblesses majeures

1. **Incohérence doc ↔ code sur le provider news par défaut** : la documentation (DOC_FONCTIONNELLE.md, DOC_TECHNIQUE.md, CONVENTIONS.md) affirme `alpaca` comme provider news par défaut, alors que le README.md indique `eodhd` comme défaut recommandé. Le code réel de `event_sentiment` doit être vérifié.
2. **Hétérogénéité des résumés de run** : tous les modules n'émettent pas des `run_summary` structurés de manière uniforme ; la persistance SQL des résumés n'est pas systématique.
3. **Absence d'orchestrateur formel** : le pipeline repose sur un lancement manuel ou semi-manuel via l'IHM, sans véritable orchestrateur (Airflow/Prefect).
4. **Tests d'intégration insuffisants** : pas de tests avec MySQL Docker, pas de tests E2E complets du pipeline.
5. **Surveillance production limitée** : pas de Prometheus/Grafana, pas d'alerting email/SMS/Slack, logs fichiers uniquement.
6. **ML gouvernance incomplète en DB** : `model_predictions` ne persiste pas `selected_model`, `decision_threshold`, `calibration_method`.
7. **Risque d'univers vide sur petits comptes** : les presets `capital_0_5000` sont très restrictifs et peuvent produire 0 candidats en régime de marché normal.
8. **Absence de short selling** : limitation de design assumée mais qui empêche les stratégies baissières.

---

## Anomalies critiques (P0/P1)

- **P0** : Aucune anomalie P0 détectée (l'application ne présente pas de bug bloquant immédiat).
- **P1** : 7 anomalies de priorité haute identifiées (incohérences doc/code, sécurité config, risques paramétrage).
- **P2** : 18 anomalies de priorité moyenne.
- **P3** : 11 anomalies de priorité basse (dette technique, améliorations).

Voir `03_anomalies_register.md` pour le détail complet.

---

## Recommandation prioritaire

1. **Corriger les incohérences doc ↔ code** (provider news, conventions) — Sprint 1
2. **Renforcer la sécurité** (secrets, préflight live bloquant) — Sprint 1
3. **Uniformiser les run_summary et la persistance SQL** — Sprint 2
4. **Ajouter des tests d'intégration et E2E** — Sprint 3
5. **Industrialiser l'orchestration et le monitoring** — Sprint 4+

---

## À partir de quel sprint l'application est-elle « suffisamment robuste pour du swing trading réel discipliné » ?

**Sprint 3** — après correction des P1, uniformisation des résumés, renforcement des tests, et validation du paramétrage par tranche de capital, l'application atteint un niveau de confiance suffisant pour du paper trading avancé et une préparation au live.

**Sprint 5** — pour le live trading avec de l'argent réel, après industrialisation de l'orchestration et du monitoring.

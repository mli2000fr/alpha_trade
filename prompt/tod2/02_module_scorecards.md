# 02 — Scorecards module par module

## Documentation — 6,5 / 10

Résumé : la documentation est abondante et souvent très utile, avec des fichiers spécialisés (`doc/DOC_TECHNIQUE.md`, `doc/DOC_FONCTIONNELLE.md`, `doc/data_lineage_matrix.md`, `doc/EODHD_vs_Alpaca.md`). Elle documente le provider EODHD comme primaire. En revanche, des sections historiques restent contradictoires, surtout dans `doc/dataIntegrityEngine.md` qui recommande encore `python -m dataIntegrityEngine.import_alpaca_bar` dans les séquences de bootstrap/quotidiennes alors que l’IHM route vers EODHD si `bars_provider=eodhd`.

- Points forts : couverture large, runbooks, détails tables/modules, contexte métier.
- Faiblesses : contradictions internes, certaines références de lignes obsolètes, doc générée à régénérer.
- Risques : opérateur lance mauvais module, confusion sur `data_source`, faux sentiment de fallback.
- Pour atteindre 10/10 : génération doc/code contrôlée en CI, matrice d’écarts automatisée, runbooks uniques par provider.

## Configuration — 6,8 / 10

Résumé : `config.yaml` centralise DB, comptes Alpaca, market regimes, OHLCV et conviction. `config/capital_presets.yaml` est détaillé et couvre les tranches demandées. Le point faible principal est l’existence de clés non consommées réellement, notamment `market_data.fallback_on_failure: true` présent à `config.yaml:181-183` mais trouvé seulement en tests/config schema côté Python.

- Points forts : provider primaire explicite, secrets via env, presets capital nombreux.
- Faiblesses : paramètres orphelins, comments parfois contradictoires (`market_regimes.enabled=true` avec commentaire off par défaut).
- Risques : opérateur croit à un fallback automatique ou à des defaults non réels.
- Pour atteindre 10/10 : schema strict + test “toutes clés consommées”, validation runtime au lancement.

## dataIntegrityEngine — 7,0 / 10

Résumé : l’ingestion Alpaca est bien protégée par no-op quand `bars_provider=eodhd` (`import_alpaca_bar.py:571-629`). L’ingestion EODHD existe en shim + orchestrateur (`import_eodhd_bar.py`, `dataIntegrityEngine/eodhd/orchestrator.py`) et écrit `stock_bars` + `stock_bars_daily`. La sanitation daily reste utile mais garde des commentaires Alpaca (`data_sanitizer_daily.py:169-175`) et des flux doc historiques.

- Points forts : validation business des bars, run summaries, circuit/quota EODHD, no-op symétrique provider.
- Faiblesses : `stock_bars_daily` ne versionne pas par `data_source`, vwap EODHD est proxy typical price.
- Risques : écrasement source, diagnostics volumes/spreads mal interprétés.
- Pour atteindre 10/10 : data versioning complet, tests de migration/cohabitation, métriques qualité centralisées.

## Database — 6,7 / 10

Résumé : les schémas SQL sont lisibles et matérialisent des contraintes importantes. `chk_bars_adj` et `chk_daily_adj` imposent `split`. Toutefois `stock_bars_daily` a une PK `(symbol,date)` (`database/sql/stock/stock_bars_daily.sql:24`) alors que `doc/data_lineage_matrix.md:114-115` affirme une cohabitation simultanée `alpaca_iex` et `eodhd_eod` sur la même `(symbol,date)`, impossible sans écrasement.

- Points forts : nombreuses tables métier, audit trail exécution/CA, contraintes de prix.
- Faiblesses : versioning source incomplet, migrations à auditer systématiquement.
- Risques : état DB incompatible avec promesse doc, perte de trace source.
- Pour atteindre 10/10 : migrations Alembic exhaustives, tests de schéma, modèle lineage généré.

## Service/providers — 7,0 / 10

Résumé : les providers Alpaca, Finnhub et EODHD sont structurés. EODHD dispose d’adapters de reconstruction split-only (`service/eodhd/adapters.py:153-194`) et d’une factory CA (`corporate_actions/provider.py:402-432`). Le point faible est le fallback EODHD→Alpaca configuré mais non effectif globalement.

- Points forts : clients séparés, quotas/retry, account registry.
- Faiblesses : fallback non câblé, dépendance aux API externes dans runs longs.
- Risques : panne provider = arrêt ou état partiel malgré config rassurante.
- Pour atteindre 10/10 : provider router testé, circuit breakers cross-provider, sandbox replay.

## Screener — 7,0 / 10

Résumé : le screener produit les scores de base et dépend des barres daily. La migration EODHD améliore fortement le volume vs IEX. Le risque reste l’univers vide/trop large selon seuils de capital et la dépendance aux volumes/proxies.

- Points forts : seuils exposés IHM, run summaries, profils stricts.
- Faiblesses : dépendance qualité upstream, diagnostics investissabilité à automatiser.
- Risques : faux rejets de liquidité ou univers non exécutable.
- Pour atteindre 10/10 : tests d’univers par capital, diagnostics quotidiens bloquants.

## Selector — 7,2 / 10

Résumé : `AlphaScanner` est riche : filtres market cap, beta, spread, earnings, ATR, MA200, neutralisation sectorielle. Le profil canonique est dans `core/filter_profiles.py` et aliasé dans `selector/strict_filter_profiles.py`. C’est une bonne base pour swing trade, mais certains presets relâchent fortement spreads/corrélation petits comptes.

- Points forts : filtres métier pertinents, PIT possible, profil strict partagé.
- Faiblesses : complexité élevée, risque d’univers vide selon data quotes/earnings.
- Risques : sélection non investissable ou trop sensible aux snapshots IEX.
- Pour atteindre 10/10 : stress tests par régime/capital, explainability complète, validation out-of-sample.

## event_sentiment — 6,3 / 10

Résumé : le pipeline sentiment est ambitieux et l’IHM lance une chaîne mixte pour news, relevance, standard/contextual et features. L’utilité économique doit être prouvée et gouvernée. Le risque principal est la sur-complexité pour un gain alpha incertain.

- Points forts : scope mixte, run summaries, séparation features ticker/sector.
- Faiblesses : latence/coût, bruit news, calibration incertaine.
- Risques : faux boost sentiment, surajustement des signaux.
- Pour atteindre 10/10 : ablation live, monitoring drift sentiment, tests de pertinence.

## modelFactory — 6,2 / 10

Résumé : LSTM, challengers LightGBM/CatBoost, champion selection et artefacts indiquent une vraie gouvernance ML. Mais pour du swing trade réel, la robustesse out-of-sample, la calibration et le drift doivent être prouvés plus durement.

- Points forts : multi-modèles, artefacts, walk-forward, champion inférable.
- Faiblesses : complexité, dépendance artefacts, risque overfitting.
- Risques : ML surpondéré dans risk (`prediction_weight` jusqu’à 0.60).
- Pour atteindre 10/10 : validation statistique obligatoire avant live, drift gates bloquants, ablations.

## risk_management — 7,1 / 10

Résumé : `PortfolioBuilder` fusionne score quant et ML (`portfolio_builder.py:85-92`), filtre corrélation et applique sizing/contraintes. Les presets par capital sont détaillés. Le risque est la cohérence live entre equity détectée, preset, min notional et exécution.

- Points forts : circuit breaker, corrélation, Kelly désactivable, min notionals.
- Faiblesses : calibration empirique complexe, risque petits comptes concentrés.
- Risques : portefeuille accepté mais difficile à exécuter ou trop corrélé.
- Pour atteindre 10/10 : tests par capital + parité broker snapshots + stress corrélation.

## execution_engine — 7,4 / 10

Résumé : l’exécution est le module le plus proche du niveau pro. `run_execution.py` impose un preflight live et interdit le fallback equity silencieux. `ExecutionConfig` modélise cash/margin/PDT/swing/protections. Il reste une orchestration locale et une dépendance forte à l’opérateur.

- Points forts : preflight, dry-run, paper/live, snapshot compte, protections, reconciliation/TCA.
- Faiblesses : pas de moteur de scheduling robuste, incident response encore manuel.
- Risques : ordres partiels/orphelins si processus interrompu, réconciliation post-fail à durcir.
- Pour atteindre 10/10 : locks globaux, kill switch central, runbook incident, tests broker contract.

## corporate_actions — 7,0 / 10

Résumé : la séparation prix split-only / dividendes en ledger est correcte. `CorporateActionEngine` ne touche pas les bars (`engine.py:52-55`) et applique les événements sur positions. La factory provider est cohérente avec EODHD.

- Points forts : idempotence, applications, cash ledger, provider factory.
- Faiblesses : dépendance aux positions broker snapshots, risques doubles événements provider.
- Risques : dividende non crédité si snapshot absent ; mismatch EODHD/Alpaca.
- Pour atteindre 10/10 : cross-check provider, tests ex-date/pay-date, reconciliation broker cash.

## backtesting — 6,8 / 10

Résumé : le backtesting contient des briques avancées : PIT, microstructure, replay execution/protection/watcher. Mais la parité live est opt-in et le pipeline peut être trompeur si lancé en mode recherche tolérant.

- Points forts : phases de fidélité, reports, constraints cash/PDT/swing.
- Faiblesses : mode pipeline strict pas systématiquement imposé, cache non branché par défaut.
- Risques : illusion de performance si données ou ML non PIT.
- Pour atteindre 10/10 : gate CI backtest-live parity, jeux golden, reporting risk-adjusted obligatoire.

## IHM — 7,0 / 10

Résumé : l’IHM Streamlit expose vraiment le workflow 1→14 et construit les commandes backend. Elle route EODHD correctement. Elle est riche, mais potentiellement complexe pour un opérateur, et certains runs réseau historiques peuvent durer très longtemps.

- Points forts : pilotage local, options détaillées, run history, watcher block.
- Faiblesses : UX dense, pas d’orchestrateur distribué, commandes longues.
- Risques : mauvaise option, run partiel, opérateur croit un step terminé alors qu’un autre est stale.
- Pour atteindre 10/10 : cockpit incident, dépendances bloquantes visuelles, dry-run plan avant exécution.

## Observabilité — 6,7 / 10

Résumé : les `run_summary`, logs et tables d’audit sont nombreux. C’est supérieur à beaucoup de projets indépendants. Mais les signaux sont dispersés et pas encore convertis en SLO/alerting robuste.

- Points forts : run summaries structurés, artifacts, DB audit.
- Faiblesses : pas de dashboard incident unique, métriques Prometheus optionnelles.
- Risques : diagnostic incident lent.
- Pour atteindre 10/10 : tracing pipeline, alerting, SLO, correlation-id global.

## Sécurité/readiness production — 6,2 / 10

Résumé : secrets env, live confirmation, preflight et interdiction d’equity fallback sont forts. Mais la maturité production exige rotation secrets, séparation envs, CI sécurité et procédures d’urgence.

- Points forts : no secrets racine, live preflight, account registry.
- Faiblesses : policy complète absente, configs opérateur locales.
- Risques : live mal configuré, environnement non conforme.
- Pour atteindre 10/10 : secret manager obligatoire, approvals live, audit CI sécurité bloquant.

## Qualité logicielle globale — 6,8 / 10

Résumé : structure riche, tests nombreux, typage progressif et linter configuré. La dette principale est la complexité et les écarts doc/config/code. Les modules sont maintenables si la discipline de tests de conventions est renforcée.

- Points forts : 298 fichiers de tests détectés, pytest strict, ruff/mypy config.
- Faiblesses : couverture partielle non probante, tests intégration/E2E à renforcer.
- Risques : régression inter-modules non captée.
- Pour atteindre 10/10 : contract tests par step, mutation testing critique, CI complète.


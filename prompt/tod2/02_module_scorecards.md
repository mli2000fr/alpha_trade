# 02 — Scorecards module par module

## Documentation — 7,7 / 10

Résumé : la documentation est abondante et désormais bien plus cohérente avec le code, en particulier sur le provider EODHD primaire, la stratégie de source unique active et les garde-fous live. Il reste toutefois quelques traces historiques et des runbooks incident à homogénéiser pour atteindre un niveau pleinement industrialisé.

- Points forts : couverture large, runbooks, détails tables/modules, contexte métier.
- Faiblesses : contradictions internes, certaines références de lignes obsolètes, doc générée à régénérer.
- Risques : opérateur lance mauvais module, confusion sur `data_source`, faux sentiment de fallback.
- Pour atteindre 10/10 : génération doc/code contrôlée en CI, matrice d’écarts automatisée, runbooks uniques par provider.

## Configuration — 7,8 / 10

Résumé : `config.yaml` centralise DB, comptes Alpaca, market regimes, OHLCV et conviction, et les presets capital sont désormais beaucoup mieux alignés avec l’exécutabilité réelle. Le faux fallback runtime a été retiré et les principaux contrats config/runtime/IHM sont aujourd’hui sensiblement plus cohérents, même si une validation encore plus systématique en CI resterait souhaitable.

- Points forts : provider primaire explicite, secrets via env, presets capital nombreux.
- Faiblesses : paramètres orphelins, comments parfois contradictoires (`market_regimes.enabled=true` avec commentaire off par défaut).
- Risques : opérateur croit à un fallback automatique ou à des defaults non réels.
- Pour atteindre 10/10 : schema strict + test “toutes clés consommées”, validation runtime au lancement.

## dataIntegrityEngine — 7,8 / 10

Résumé : l’ingestion provider-aware est désormais beaucoup plus lisible : EODHD daily canonique, no-op provider explicites, diagnostics quotes enrichis, garde-fous sur les runs historiques et wrappers IHM mieux outillés. Le principal axe restant concerne le versioning source/audit plus fin et la centralisation des métriques qualité data.

- Points forts : validation business des bars, run summaries, circuit/quota EODHD, no-op symétrique provider.
- Faiblesses : `stock_bars_daily` ne versionne pas par `data_source`, vwap EODHD est proxy typical price.
- Risques : écrasement source, diagnostics volumes/spreads mal interprétés.
- Pour atteindre 10/10 : data versioning complet, tests de migration/cohabitation, métriques qualité centralisées.

## Database — 7,5 / 10

Résumé : les schémas SQL sont lisibles, contraints et mieux réalignés avec la documentation. La décision de **source unique active** sur `stock_bars_daily` clarifie désormais le contrat réel ; la limite restante est l’absence de versioning multi-source daily natif quand on voudrait conserver plusieurs provenances simultanément.

- Points forts : nombreuses tables métier, audit trail exécution/CA, contraintes de prix.
- Faiblesses : versioning source incomplet, migrations à auditer systématiquement.
- Risques : état DB incompatible avec promesse doc, perte de trace source.
- Pour atteindre 10/10 : migrations Alembic exhaustives, tests de schéma, modèle lineage généré.

## Service/providers — 7,6 / 10

Résumé : les providers Alpaca, Finnhub et EODHD sont bien structurés. EODHD dispose d’adapters de reconstruction split-only (`service/eodhd/adapters.py:153-194`) et d’une factory CA (`corporate_actions/provider.py:402-432`). Le faux fallback implicite a été retiré, ce qui rend le comportement plus honnête ; il manque encore un vrai routeur cross-provider résilient et centralisé.

- Points forts : clients séparés, quotas/retry, account registry.
- Faiblesses : fallback non câblé, dépendance aux API externes dans runs longs.
- Risques : panne provider = arrêt ou état partiel malgré config rassurante.
- Pour atteindre 10/10 : provider router testé, circuit breakers cross-provider, sandbox replay.

## Screener — 7,6 / 10

Résumé : le screener produit les scores de base sur un socle daily plus cohérent et bénéficie désormais de meilleurs garde-fous IHM sur les runs historiques, le coût et la volumétrie. Le risque principal reste la dépendance à la qualité upstream et au calibrage des seuils par capital.

- Points forts : seuils exposés IHM, run summaries, profils stricts.
- Faiblesses : dépendance qualité upstream, diagnostics investissabilité à automatiser.
- Risques : faux rejets de liquidité ou univers non exécutable.
- Pour atteindre 10/10 : tests d’univers par capital, diagnostics quotidiens bloquants.

## Selector — 7,9 / 10

Résumé : `AlphaScanner` est riche : filtres market cap, beta, spread, earnings, ATR, MA200, neutralisation sectorielle. Le profil canonique est dans `core/filter_profiles.py` et aliasé dans `selector/strict_filter_profiles.py`. Avec les améliorations quotes, exécutabilité petits comptes et visibilité IHM, c’est désormais une base nettement plus robuste pour du swing discipliné.

- Points forts : filtres métier pertinents, PIT possible, profil strict partagé.
- Faiblesses : complexité élevée, risque d’univers vide selon data quotes/earnings.
- Risques : sélection non investissable ou trop sensible aux snapshots IEX.
- Pour atteindre 10/10 : stress tests par régime/capital, explainability complète, validation out-of-sample.

## event_sentiment — 7,1 / 10

Résumé : le pipeline sentiment est ambitieux et l’IHM lance une chaîne mixte pour news, relevance, standard/contextual et features. Les sprints récents ont apporté plus de gouvernance, d’ablation et de visibilité ; le risque principal reste la sur-complexité pour un gain alpha qui doit continuer à être démontré en exploitation.

- Points forts : scope mixte, run summaries, séparation features ticker/sector.
- Faiblesses : latence/coût, bruit news, calibration incertaine.
- Risques : faux boost sentiment, surajustement des signaux.
- Pour atteindre 10/10 : ablation live, monitoring drift sentiment, tests de pertinence.

## modelFactory — 7,2 / 10

Résumé : LSTM, challengers LightGBM/CatBoost, champion selection et artefacts indiquent une vraie gouvernance ML. Les sprints S3 et S7 ont renforcé le gate ML, l’ablation et la visibilité des seuils ; pour du swing trade réel, la robustesse out-of-sample, la calibration et le drift doivent toutefois rester sous contrôle strict.

- Points forts : multi-modèles, artefacts, walk-forward, champion inférable.
- Faiblesses : complexité, dépendance artefacts, risque overfitting.
- Risques : ML surpondéré dans risk (`prediction_weight` jusqu’à 0.60).
- Pour atteindre 10/10 : validation statistique obligatoire avant live, drift gates bloquants, ablations.

## risk_management — 7,9 / 10

Résumé : `PortfolioBuilder` fusionne score quant et ML (`portfolio_builder.py:85-92`), filtre corrélation et applique sizing/contraintes. Les presets par capital, l’exécutabilité petits comptes et le gate ML explicite rendent désormais l’ensemble beaucoup plus crédible ; le risque restant concerne surtout la discipline d’exploitation live et la calibration empirique avancée.

- Points forts : circuit breaker, corrélation, Kelly désactivable, min notionals.
- Faiblesses : calibration empirique complexe, risque petits comptes concentrés.
- Risques : portefeuille accepté mais difficile à exécuter ou trop corrélé.
- Pour atteindre 10/10 : tests par capital + parité broker snapshots + stress corrélation.

## execution_engine — 8,4 / 10

Résumé : l’exécution est le module le plus proche du niveau pro. `run_execution.py` impose un preflight live, interdit le fallback equity silencieux, exige un token d’approbation live (`ALPHA_TRADE_LIVE_APPROVAL_TOKEN`) et écrit/vérifie un run plan immuable pour les runs live. `ExecutionConfig` modélise cash/margin/PDT/swing/protections. Il reste surtout une orchestration locale et une dépendance forte à l’opérateur.

- Points forts : preflight, dry-run, paper/live, snapshot compte, protections, reconciliation/TCA, approval token live, run plan immuable.
- Faiblesses : pas de moteur de scheduling robuste, incident response encore manuel, dépendance à des variables d’env opérateur.
- Risques : ordres partiels/orphelins si processus interrompu, réconciliation post-fail à durcir, dérive process hors CI centralisée.
- Pour atteindre 10/10 : locks globaux, kill switch central, runbook incident, tests broker contract et workflow CI d’approbation versionné.

## corporate_actions — 7,9 / 10

Résumé : la séparation prix split-only / dividendes en ledger est correcte. `CorporateActionEngine` ne touche pas les bars (`engine.py:52-55`) et applique les événements sur positions. La factory provider est cohérente avec EODHD, et les préflights/apply guards rendent désormais le périmètre production nettement plus fiable.

- Points forts : idempotence, applications, cash ledger, provider factory.
- Faiblesses : dépendance aux positions broker snapshots, risques doubles événements provider.
- Risques : dividende non crédité si snapshot absent ; mismatch EODHD/Alpaca.
- Pour atteindre 10/10 : cross-check provider, tests ex-date/pay-date, reconciliation broker cash.

## backtesting — 7,8 / 10

Résumé : le backtesting contient des briques avancées : PIT, microstructure, replay execution/protection/watcher. L’ajout du profil `production-parity` et des garde-fous de replay renforce nettement la crédibilité de la chaîne ; la parité live n’est toutefois pas encore totalement automatique partout.

- Points forts : phases de fidélité, reports, constraints cash/PDT/swing.
- Faiblesses : mode pipeline strict pas systématiquement imposé, cache non branché par défaut.
- Risques : illusion de performance si données ou ML non PIT.
- Pour atteindre 10/10 : gate CI backtest-live parity, jeux golden, reporting risk-adjusted obligatoire.

## IHM — 8,0 / 10

Résumé : l’IHM Streamlit expose vraiment le workflow 1→14 et construit les commandes backend. Elle route EODHD correctement et rend visibles les garde-fous live/compliance, la supervision ops, la corrélation workflow et plusieurs commandes de maintenance/sécurité. Elle reste riche, mais potentiellement dense pour un opérateur, et l’orchestration demeure locale.

- Points forts : pilotage local, options détaillées, run history, watcher block, panneaux compliance/settings/ops reliés aux garde-fous réels du backend.
- Faiblesses : UX dense, pas d’orchestrateur distribué, commandes longues.
- Risques : mauvaise option, run partiel, opérateur croit un step terminé alors qu’un autre est stale.
- Pour atteindre 10/10 : cockpit incident unifié, dépendances bloquantes visuelles, prévisualisation complète du run plan avant exécution live.

## Observabilité — 7,8 / 10

Résumé : les `run_summary`, logs et tables d’audit sont nombreux. La corrélation workflow, la supervision ops et le contrôle coverage ont sensiblement amélioré l’exploitabilité. Les signaux restent cependant moins centralisés qu’un dispositif de monitoring/alerting production dédié.

- Points forts : run summaries structurés, artifacts, DB audit.
- Faiblesses : pas de dashboard incident unique, métriques Prometheus optionnelles.
- Risques : diagnostic incident lent.
- Pour atteindre 10/10 : tracing pipeline, alerting, SLO, correlation-id global.

## Sécurité/readiness production — 7,6 / 10

Résumé : la posture sécurité/runtime s’est fortement renforcée : secrets env, live confirmation, preflight, interdiction d’equity fallback, policy live explicite (Vault requis par défaut ou override assumé `ALPHA_TRADE_LIVE_SECRET_POLICY=env`), token d’approbation et run plan immuable. Les scripts `generate_sbom.py`, `scan_cves.py`, `scan_repo_secrets.py` et `verify_vault_rotation.py` existent et sont testés ; l’IHM les expose. La maturité production reste toutefois incomplète faute de workflow CI security versionné dans le repo et de procédures d’urgence exhaustives.

- Points forts : no secrets racine, live preflight, account registry, Vault/env policy explicite, approval token, immutable plan, scripts de scan/rotation testés.
- Faiblesses : pas de workflow `.github/workflows` imposant ces scans, configs opérateur encore locales.
- Risques : live mal configuré, environnement non conforme, sécurité dépendante d’une discipline locale plutôt que d’une CI bloquante.
- Pour atteindre 10/10 : secret manager obligatoire en pratique, approvals live intégrés au change management, audit CI sécurité bloquant et runbooks incident versionnés.

## Qualité logicielle globale — 7,7 / 10

Résumé : structure riche, tests nombreux, typage progressif et linter configuré. Les régressions ciblées et AppTests IHM ont significativement amélioré la confiance, mais la dette principale reste la complexité et l’homogénéisation complète de la chaîne qualité/CI.

- Points forts : 298 fichiers de tests détectés, pytest strict, ruff/mypy config.
- Faiblesses : couverture partielle non probante, tests intégration/E2E à renforcer.
- Risques : régression inter-modules non captée.
- Pour atteindre 10/10 : contract tests par step, mutation testing critique, CI complète.


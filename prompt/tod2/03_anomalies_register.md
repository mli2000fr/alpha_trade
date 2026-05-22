# 03 — Registre des anomalies

## Légende

- **P0** : doit être corrigé avant tout live réel.
- **P1** : prioritaire avant montée en taille / usage régulier.
- **P2** : important, mais contournable avec supervision.
- **P3** : amélioration, dette documentaire ou confort.

---

## A-001 — `fallback_on_failure` configuré mais non consommé

- Sévérité : **P0**
- Domaine : configuration / providers
- Description : `config.yaml` contient `market_data.fallback_on_failure: true`, mais la recherche code ne trouve pas de consommation Python hors tests/schema. Le système peut donc laisser croire à un fallback automatique EODHD→Alpaca qui n’existe pas.
- Preuve : `config.yaml:181-183`; grep `fallback_on_failure` → tests seulement.
- Impact métier : panne EODHD = pipeline bloqué ou incomplet alors que l’opérateur croit à un secours.
- Impact technique : clé morte, comportement non déterministe attendu vs réel.
- Probabilité : élevée.
- Confiance : élevée.
- Recommandation : soit implémenter un provider router explicite, soit supprimer/renommer la clé en `fallback_on_failure_reserved` avec warning runtime.
- Tests :
  - Objectif : vérifier que toute clé `market_data` est consommée ou explicitement déclarée réservée.
  - Type : config + non-régression.
  - Priorité : P0.
  - Fichiers probables : `tests/test_market_data_provider_switch.py`, `tests/test_config_yaml_schema.py`.
  - Given : config avec `bars_provider=eodhd`, `fallback_on_failure=true`, EODHD simulé en échec.
  - When : lancement step import bars.
  - Then : soit Alpaca fallback est appelé et tracé, soit le run échoue avec message “fallback non supporté”.
  - Fixtures : monkeypatch `fetch_eod_bulk`, `fetch_bars`, config YAML temporaire.
  - Oracle : aucun comportement silencieux.

## A-002 — Cohabitation `data_source` documentée mais impossible dans `stock_bars_daily`

- Sévérité : **P1**
- Domaine : DB / lineage / OHLCV
- Description : `doc/data_lineage_matrix.md:114-115` indique que `stock_bars_daily` peut contenir simultanément `alpaca_iex` et `eodhd_eod` sur la même `(symbol,date)`. Le schéma a `PRIMARY KEY(symbol,date)`.
- Preuve : `database/sql/stock/stock_bars_daily.sql:24`; doc `data_lineage_matrix.md:114-115`.
- Impact métier : confusion sur l’audit source ; backtest et live peuvent ne pas lire la source attendue.
- Impact technique : upsert écrase la source précédente.
- Probabilité : élevée en transition provider.
- Confiance : élevée.
- Recommandation : corriger la doc ou migrer la PK vers `(symbol,date,data_source)` + consumers explicites.
- Tests : SQL migration + data quality ; insérer deux sources même symbole/date ; oracle selon décision : refus documenté ou coexistence réelle.

## A-003 — `doc/dataIntegrityEngine.md` recommande encore Alpaca comme séquence quotidienne

- Sévérité : **P0**
- Domaine : documentation / opérateur
- Description : le document ouvre sur EODHD primaire mais conserve des runbooks `python -m dataIntegrityEngine.import_alpaca_bar` pour bootstrap et quotidien.
- Preuve : `doc/dataIntegrityEngine.md:136-149`, `:519-623`, alors que `ihm/services/pipeline_runner.py:1494-1506` route vers EODHD.
- Impact métier : lancement manuel du mauvais import, no-op inattendu, retard pipeline.
- Impact technique : divergences docs/runbooks.
- Probabilité : élevée.
- Confiance : élevée.
- Recommandation : réécrire les séquences en provider-aware et signaler qu’en mode EODHD `import_alpaca_bar` est un no-op.
- Tests : doc-code check ; rechercher commandes obsolètes non annotées ; fichier `tests/test_docs_provider_switch_consistency.py`.

## A-004 — Backtesting force EODHD mais la DB ne garantit pas source/version par lecture générale

- Sévérité : **P1**
- Domaine : backtesting / DB / OHLCV
- Description : la doc backtesting indique source `eodhd_eod` obligatoire, mais la table daily ne permet qu’une ligne par `(symbol,date)`. Si la table a été écrasée par Alpaca ou réimportée, la source réelle doit être validée avant backtest.
- Preuve : `doc/backtesting.md:76-79`; `stock_bars_daily.sql:24`; `import_eodhd_bar.py:218-247` upsert.
- Impact métier : backtest peut reposer sur source inattendue.
- Impact technique : parité provider fragile.
- Probabilité : moyenne.
- Confiance : moyenne-élevée.
- Recommandation : préflight backtest bloquant sur `data_source='eodhd_eod'` par date/symbole.
- Tests : backtest-live parity ; dataset mixte ; oracle = run refuse si source non conforme.

## A-005 — `market_regimes.enabled=true` malgré commentaire “off par défaut”

- Sévérité : **P2**
- Domaine : config / risk / execution
- Description : commentaire `config.yaml:49-51` indique comportement historique préservé quand disabled, mais `market_regimes.enabled: true` à `config.yaml:54-55`.
- Impact métier : l’opérateur peut subir un mode `close_only/cash_only/capital_preservation` non anticipé.
- Recommandation : clarifier défaut réel, afficher explicitement l’état dans IHM avant exécution.
- Tests : config regression ; Given config défaut ; Then l’IHM et `run_execution` affichent un preflight regime.

## A-006 — Tranche micro-compte incohérente entre description “ticket minimum bas” et `min_notional=500`

- Sévérité : **P1**
- Domaine : presets capital / exécution
- Description : `capital_0_2000_eur` décrit ticket minimum bas, mais `risk_min_position_notional=500`, 3 positions, `max_position_weight=35%`.
- Preuve : `config/capital_presets.yaml:8-20`.
- Impact métier : micro-compte fortement concentré, peu de lignes, risque psychologique et drawdown.
- Recommandation : renommer “concentration assumée” partout, ou abaisser min notional avec frais/slippage adaptés.
- Tests : config par tranche ; equity=2000 ; oracle : aucune proposition < broker min, concentration expliquée.

## A-007 — Seuils de spread petits comptes très permissifs

- Sévérité : **P1**
- Domaine : selector / execution
- Description : micro-compte accepte `selector_max_spread_bps=80`, `selector_max_spread_bps_iex=100`; 2–5k accepte 60/80. Pour du swing actions US, cela peut absorber une fraction importante de l’alpha court terme.
- Preuve : `capital_presets.yaml:51-55`, `:103-107`.
- Impact : trades chers, slippage sous-estimé.
- Recommandation : durcir ou conditionner aux tailles quote, ADV et min notional.
- Tests : unit selector spread ; fixtures quotes bid/ask/size ; oracle = rejet spreads trop larges sans taille suffisante.

## A-008 — `stock_quote_snapshots` Alpaca/IEX reste critique malgré EODHD bars

- Sévérité : **P1**
- Domaine : data / selector
- Description : OHLCV daily EODHD corrige volume, mais quotes/spreads restent Alpaca IEX (`ihm/services/pipeline_runner.py:563-568`, docs). Les filtres de spread peuvent être biaisés.
- Impact métier : faux rejets ou fausse acceptation de liquidité exécutable.
- Recommandation : documenter explicitement NBBO vs IEX, ajouter source quote et stale checks bloquants.
- Tests : data quality quotes ; stale quote > seuil ; oracle = alpha scanner bloqué ou downgrade.

## A-009 — Sync historique quotes peut être trop lente/coûteuse sur univers large

- Sévérité : **P1**
- Domaine : IHM / data ops
- Description : le sous-run historique quotes peut parcourir des milliers de symboles × jours, avec appels réseau nombreux. Les logs récents montrent une interruption après un run long.
- Preuve : `ihm/pages/pipeline.py:186-270`; logs/résumé terminal d’un `sync_latest_quotes` historique interrompu.
- Impact métier : blocage opérateur, quotas, coûts temps.
- Recommandation : limites par défaut, estimation coût avant lancement, mode batch résumé.
- Tests : E2E-IHM ; Given univers 12k symboles/période 6 ans ; Then warning + confirmation + estimation.

## A-010 — Corporate actions apply dépend des snapshots broker disponibles

- Sévérité : **P1**
- Domaine : corporate_actions / execution
- Description : `CorporateActionEngine.apply()` charge les positions depuis le dernier snapshot ; si absent, il loggue warning et ne peut créditer/ajuster.
- Preuve : `corporate_actions/engine.py:202-213`.
- Impact métier : dividendes/splits non appliqués à temps.
- Recommandation : preflight CA bloquant si positions détenues mais snapshot absent/stale.
- Tests : intégration DB SQLite ; pending dividend + no positions ; oracle = status skipped explicite et run_summary actionnable.

## A-011 — Factory CA EODHD refuse `symbols=None`, mais sync globale peut appeler provider avec `None`

- Sévérité : **P1**
- Domaine : corporate_actions/provider
- Description : `EodhdCorporateActionProvider.fetch_events` lève `ValueError` si `symbols is None`; `CorporateActionEngine.sync` appelle `provider.fetch_events(symbols=None)` si on lui passe un scope global.
- Preuve : `corporate_actions/provider.py:262-266`; `corporate_actions/engine.py:121-127`.
- Impact : crash sync globale EODHD si pas de résolution explicite d’univers.
- Recommandation : interdire sync globale avant provider ou résoudre l’univers en repo.
- Tests : unit ; provider EODHD + sync(symbols=None) ; oracle = erreur utilisateur claire avant appel provider.

## A-012 — Exécution très solide mais dépendante d’un processus local IHM/subprocess

- Sévérité : **P1**
- Domaine : execution / ops
- Description : l’IHM lance `run_execution.py` comme subprocess. Pas d’orchestrateur transactionnel central ou queue durable visible pour tout le workflow.
- Preuve : `ihm/services/pipeline_runner.py:2176-2214`, `_stream_subprocess`.
- Impact : interruption locale = run partiel, diagnostic manuel.
- Recommandation : locks/persistence/resume par étape, orchestrateur durable optionnel.
- Tests : E2E process kill ; oracle = run marqué failed + reprise sûre.

## A-013 — Parité live/backtest non automatique

- Sévérité : **P1**
- Domaine : backtesting / execution
- Description : les phases `execution_replay`, `protection_replay`, `watcher_replay`, `exit_lifecycle_replay` existent, mais sont opt-in dans les commandes docs.
- Preuve : `doc/DOC_TECHNIQUE.md:695-696`; `backtesting/simulator.py` docs.
- Impact : backtest peut rester trop optimiste.
- Recommandation : profil “production parity” par défaut pour validation live.
- Tests : parity golden ; mêmes targets, constraints, fills simulés ; oracle décisions équivalentes.

## A-014 — Poids ML élevés pour une preuve alpha insuffisamment documentée

- Sévérité : **P2**
- Domaine : risk / ML
- Description : presets utilisent souvent `risk_prediction_weight=0.55/0.60`, `risk_score_weight=0.40/0.45`. Cela donne un poids élevé aux prédictions.
- Preuve : `capital_presets.yaml:28-31`, `:180-181`, `:280-281`; `portfolio_builder.py:85-92`.
- Impact : surpondération modèle fragile.
- Recommandation : gate ML par drift/precision/action-rate et fallback quant-only.
- Tests : unit risk ; prediction manquante/drift alert ; oracle = poids ML réduit ou kill switch.

## A-015 — Couverture `coverage.json` non probante

- Sévérité : **P2**
- Domaine : qualité logicielle
- Description : `pytest.ini` impose `--cov-fail-under=70`, mais le `coverage.json` lu affiche environ 3% car issu d’un run partiel. Le fichier courant ne prouve donc pas la santé de couverture.
- Preuve : `pytest.ini:7-18`; commande de lecture `coverage.json`.
- Impact : faux signal qualité si artifact obsolète/partiel.
- Recommandation : ne publier coverage qu’après suite complète CI ; ajouter timestamp/run id.
- Tests : CI artifact validation ; oracle = coverage rejetée si run partiel.

## A-016 — DB credentials : message/commentaire incohérent sur `user/pass`

- Sévérité : **P3**
- Domaine : sécurité / doc code
- Description : `database/connection.py:25-27` dit permissif sur `user/pass`, mais l’erreur `:73-75` dit remplacer `pass/user/changeme`.
- Impact : confusion opérateur.
- Recommandation : aligner message et policy.
- Tests : unit credentials sentinels ; oracle = messages cohérents.

## A-017 — `data_sanitizer_daily.py` garde une note Alpaca dans la construction `adj_close`

- Sévérité : **P3**
- Domaine : doc inline / data
- Description : commentaire `data_sanitizer_daily.py:169-175` explique `adj_close=close` par l’API Alpaca alors que EODHD est primaire. La convention reste correcte, l’explication est obsolète.
- Impact : confusion mainteneur.
- Recommandation : reformuler provider-agnostique split-only.
- Tests : doc-lint simple ; oracle = pas de justification provider obsolète dans zone canonique.

## A-018 — IHM très riche, risque UX opérateur

- Sévérité : **P2**
- Domaine : IHM / exploitation
- Description : `PipelineLaunchOptions` expose de très nombreuses options. La puissance est réelle, mais le risque de mauvaise combinaison est élevé.
- Preuve : `ihm/services/pipeline_runner.py:242-360+`.
- Impact : run avec paramètres non souhaités.
- Recommandation : mode “preset verrouillé” + diff de commande avant lancement.
- Tests : E2E-IHM ; Given preset capital ; Then options critiques préremplies/verrouillables.


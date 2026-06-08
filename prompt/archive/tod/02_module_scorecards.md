# 02 — Scorecards par module

> Notation /10. Pour chaque module : note, résumé, points forts, faiblesses,
> risques principaux, et gap pour atteindre 10/10.

---

## 1. Documentation (`doc/`, `README.md`) — **5.5 / 10**

**Résumé.** Documentation **abondante** (24 fichiers `doc/` + README) et
historiquement bien structurée (DOC_FONCTIONNELLE, DOC_TECHNIQUE, runbooks,
guides). Mais le code a évolué plus vite que la doc : la convention
`bars_provider=eodhd` (config.yaml:51) n'est pas reflétée dans les bandeaux
IEX (`doc/dataIntegrityEngine.md:3-22`), la matrice lineage
(`doc/data_lineage_matrix.md:27-31` met `Alpaca IEX` comme producteur) ni
dans le runbook quotidien (`README.md:142` recommande `import_alpaca_bar`).

- **Points forts** : runbooks dédiés (`runbook_provider_incident.md`,
  `runbook_reconciliation.md`), guide d'ajout de table, doc par module.
- **Faiblesses** : doublon `doc/backetesting.md` vs `doc/backtesting.md`
  (faute de frappe non purgée — P3) ; bandeau IEX figé ; convention
  `data_adjustment` mentionnée correctement dans README mais contredite par
  la docstring `corporate_actions/engine.py:36`.
- **Risques** : un nouvel intervenant suit la doc, lance `import_alpaca_bar`
  avec `bars_provider=eodhd`, obtient un no-op silencieux et croit son
  pipeline opérationnel.
- **Gap pour 10/10** : sprint doc dédié (S1) + processus de mise à jour doc
  obligatoire dans la Definition of Done de chaque PR refactor.

---

## 2. Configuration — **6.0 / 10**

**Résumé.** Architecture de config raisonnable : `config.yaml` central +
`config/capital_presets.yaml` détaillé sur 6 tranches + `pyproject.toml`,
`mypy.ini`, `pytest.ini`. Politique secrets DB durcie (sentinelles rejetées,
placeholders `${VAR}`).

- **Points forts** : presets de capital riches (29 paramètres × 6 tranches),
  loader cache LRU avec hash, multi-comptes Alpaca déclaratifs.
- **Faiblesses** :
  - `config.yaml:51` `bars_provider: eodhd` mais `config.yaml:55`
    `eodhd.enabled: false` → contradiction interne, et `eodhd.enabled` n'est
    **jamais lu en code applicatif** (`grep_search` confirme : seul mention
    dans docstring `service/eodhd/__init__.py:21`) ;
  - `config.yaml:10-11` contient encore `api_key: "PK..."` /
    `secret_key: "..."` en clair (rétrocompat) → anti-pattern ;
  - `risk.max_drawdown=0.15` / `risk.max_daily_loss=0.05` (`config.yaml:39-40`)
    sont **globaux** et non override-ables par tranche de capital — agressifs
    pour un compte 0–5 000 $.
- **Risques** : opérateur croit l'EODHD désactivé (`enabled:false`) alors que
  c'est le provider primaire actif.
- **Gap pour 10/10** : supprimer `eodhd.enabled` (ou le câbler), vider les
  `"PK..."`, override risk.* par préset, schéma JSON/Pydantic de validation.

---

## 3. `dataIntegrityEngine/` — **7.0 / 10**

**Résumé.** Cœur d'ingestion solide : `import_alpaca_bar.py` (644 lignes),
`import_eodhd_bar.py` (871 lignes), `data_sanitizer_daily.py`,
`update_sector.py`, `sync_latest_quotes.py`, `sync_earnings_calendar.py`.
`DATA_ADJUSTMENT='split'` codé en dur côté Alpaca
(`import_alpaca_bar.py:36`), aligné avec adapters EODHD
(`service/eodhd/adapters.py:262`).

- **Points forts** : run summaries enrichis, schéma versioning, télémétrie
  staleness (calendar+trading days), upserts par batch avec checkpoints.
- **Faiblesses** : la résolution `_resolve_target_bars_provider` retourne
  `default='alpaca'` (`import_alpaca_bar.py:572`) — donc si la clé est
  absente, on revient sur Alpaca, ce qui peut surprendre. La doc
  `doc/dataIntegrityEngine.md` ne reflète pas le mode EODHD primaire.
- **Risques** : aucun `assert` runtime que `data_adjustment` écrit
  effectivement vaut `'split'` (la contrainte SQL `chk_bars_adj` couvre, mais
  un échec serait une erreur tardive d'insertion).
- **Gap pour 10/10** : assertion runtime du provider effectivement utilisé,
  log de cohérence cross-provider, migration de la doc.

---

## 4. `database/` — **7.5 / 10**

**Résumé.** Schémas SQL versionnés (`database/sql/`), repositories typés,
`alembic` activé (`alembic/env.py` + `versions/`), contrainte CHECK
`chk_bars_adj`/`chk_daily_adj` mentionnée dans la doc, propagation
`account_id` sur les tables critiques (cf. `README.md:496-510`).

- **Points forts** : repositories par domaine, séparation `selector_reference`
  / `sanitizer_db_ops` / `stock_scores` / `bar_metadata` / `assets`.
- **Faiblesses** : la doc `data_lineage_matrix.md` est **éditée à la main**
  (lignes 8-10) — à terme, un script `scripts/generate_data_lineage.py` est
  prévu mais non implémenté ; la matrice cite `Alpaca IEX` partout.
- **Risques** : drift entre schéma réel et matrice lineage.
- **Gap pour 10/10** : autogen lineage matrix, suite de tests SQL contre une
  DB éphémère, vérification Alembic d'idempotence.

---

## 5. `service/` — **7.5 / 10**

**Résumé.** Adapters providers bien découpés : `alpaca/` (clientAlpaca,
trading_client), `eodhd/` (adapters, cache, clientEodhd, quota), `finnhub/`
(profile, earnings, news), `stooq/`, `tiingo/`, `yahoo/`. Telemetry et
retries HTTP centralisés (`_telemetry.py`, `_http_retry.py`).

- **Points forts** : EODHD avec quota tracker, circuit breaker, cache disque
  TTL splits 7 j ; Stooq pour cross-check. Adapter `to_stock_bars_daily_row`
  écrit explicitement `data_adjustment='split'`.
- **Faiblesses** : Tiingo et Yahoo présents mais sous-documentés ; pas de
  matrice claire de quel provider est lu pour quelle table.
- **Risques** : ajout d'un provider sans plan de fallback documenté.
- **Gap pour 10/10** : matrice « provider → table → fallback » dans
  `doc/service.md`, contrats de SLA et tests d'intégration mockés.

---

## 6. `screener/` (`stock_screener.py`, `pipeline.py`) — **6.5 / 10**

**Résumé.** Calcule scores liquidité, RS, range historique. Multi-thread
(`--max-workers`), benchmark configurable (`--benchmark SPY`).

- **Points forts** : sortie `stock_scores` exploitée par tout l'aval,
  `screener_run_summaries` pour audit.
- **Faiblesses** : couplage fort à la qualité des barres (volume EODHD vs
  Alpaca IEX) ; pas de filtre explicite `data_source` lors de la lecture →
  un mix de barres venant de plusieurs sources passerait silencieusement.
- **Risques** : RS biaisé si volumes IEX hérités cohabitent avec EODHD.
- **Gap pour 10/10** : audit `data_source` à la lecture, télémétrie « % rows
  par data_source », gating qualité.

---

## 7. `selector/` — **7.5 / 10**

**Résumé.** `alpha_scanner.py` (1 421 lignes) façade autour de
`selector.factors`, `selector.filters`, `selector.ranking`, alimenté par
`core.filter_profiles.STRICT_SWING_CASH_FILTERS`. Profils stricts unifiés.

- **Points forts** : extension IEX (`max_spread_bps_iex`, `min_quote_size`)
  et TTL `market_cap_max_age_days` ; neutralisation sectorielle ; tests
  multiples.
- **Faiblesses** : `alpha_scanner.py` reste massif (1 400+ lignes) —
  refactor partiel mais la classe `AlphaScanner` reste une grande façade.
- **Risques** : régression silencieuse lors de la modification des poids ou
  des seuils.
- **Gap pour 10/10** : finir l'extraction de `AlphaScanner` (étapes encore
  dans la classe), property-based tests sur l'invariance neutralisation
  sectorielle.

---

## 8. `event_sentiment/` — **6.0 / 10**

**Résumé.** Pipeline news (Alpaca News) → FinBERT → agrégats par
ticker/secteur → `signal_aggregator` (fusion quant 75 % + sentiment 15 % +
macro 10 %).

- **Points forts** : architecture claire ; tests sur alignement temporel,
  règles macro, agrégation, preprocessor FinBERT ; macros calibrées.
- **Faiblesses** : le bénéfice métier réel des poids 15 % sentiment n'est pas
  démontré empiriquement dans la doc ; risque de double application si
  `signal_aggregator` lancé séparément (`README.md:316`) ; FinBERT lourd.
- **Risques** : sur-complexité pour un effet alpha incertain.
- **Gap pour 10/10** : étude d'attribution alpha sentiment vs quant pur,
  mode « disable_sentiment » testable.

---

## 9. `modelFactory/` — **6.0 / 10**

**Résumé.** Pipeline ML (LSTM + Attention, et apparemment LightGBM/CatBoost
selon `data_lineage_matrix.md:49`), governance, drift monitor (Phase 7.4),
champion selection.

- **Points forts** : champion governance, drift runs persistés
  (`ml_drift_runs` P2), métriques full.
- **Faiblesses** : pas de seuil clair de « drift catastrophique → kill
  switch ML » documenté ; gouvernance des artefacts (`artifacts/models/`)
  peu documentée ; risque overfitting.
- **Risques** : décision live sur prédiction biaisée non détectée.
- **Gap pour 10/10** : seuils drift → action automatique, calibration
  documentée, attestation d'entraînement.

---

## 10. `risk_management/` — **6.5 / 10**

**Résumé.** `position_sizer` ATR-only strict, `circuit_breaker` drawdown +
daily loss, `correlation_filter`, `kelly` (désactivé partout dans les
presets), `portfolio_builder`, `constraints`, `conviction` (fusion
quant/ML).

- **Points forts** : sizing prudent, audit, shadow_compare (Phase 7.7).
- **Faiblesses** :
  - `circuit_breaker.py` lit `PnLSnapshot` injecté manuellement — aucun
    branchement automatique sur le portefeuille réel par défaut ;
  - télémétrie « rejets sizing pour notional insuffisant » manquante dans
    le `run_summary` — invisible pour l'opérateur du préset 0–5 000 $ qui
    voit 0 ordres sans savoir pourquoi ;
  - `risk.max_drawdown`/`max_daily_loss` non override par préset.
- **Risques** : circuit breaker silencieusement inactif, opérateur sans
  visibilité sur friction sizing.
- **Gap pour 10/10** : adapter PnLSnapshot auto, télémétrie sizing,
  override par préset, simulation circuit breaker.

---

## 11. `execution_engine/` — **7.5 / 10**

**Résumé.** Synthetic Bracket OCO, audit trail extensif (snapshot →
requests → broker_orders → fills → positions/lots → reconciliation →
TCA), `protection_watcher` post-run secondaire,
`broker_state_sync`, multi-comptes propagé.

- **Points forts** : architecture solide, tests `tests/test_executor*.py`,
  `tests/test_oco_manager*.py`, gestion cash/margin/swing-only, kill switch,
  exécution locks.
- **Faiblesses** : un seul broker concret (Alpaca) — l'abstraction
  `BrokerAdapter` existe mais l'extensibilité n'est pas testée ; le watcher
  reste *secondaire* et l'opérateur peut l'oublier.
- **Risques** : oubli de lancer le watcher → trailing non promu sur
  positions existantes.
- **Gap pour 10/10** : test E2E sandbox Alpaca, deuxième broker (mock)
  branché, watcher rendu obligatoire post-run via flag.

---

## 12. `corporate_actions/` — **6.5 / 10**

**Résumé.** `engine.py` orchestrant sync (ingestion provider → DB) puis
apply (positions → cash ledger). Idempotence scopée par `account_id`,
réconciliation, processors splits/dividendes.

- **Points forts** : design idempotent propre, audit trail
  (`corporate_actions_applications`, `corporate_actions_audit_runs`),
  cross-check Yahoo, factory provider selon `bars_provider`.
- **Faiblesses** :
  - **`engine.py:36` (docstring) ment** : « Alpaca adjustment="all" » alors
    que la convention projet est `'split'` (P0 — incohérent avec la
    sémantique réelle du module qui gère justement le ledger dividendes).
  - L'ordre du pipeline (`README.md:182`) place le sync CA *après*
    `run_execution` ; documenté mais déroutant.
- **Risques** : un futur intervenant croyant les barres ajustées « all »
  duplique les ajustements ou ignore le ledger.
- **Gap pour 10/10** : corriger docstring (S1), assertion runtime de la
  convention en lisant `data_source`/`data_adjustment` des barres.

---

## 13. `backtesting/` — **6.5 / 10**

**Résumé.** Module riche : `simulator.py`, `execution_replay`,
`exit_lifecycle_replay`, `signal_replay`, `walk_forward`,
`statistical_validation`, `microstructure`, `analytics`,
`weights_calibration`, `protection_watcher_replay`, `risk_overlay`, etc.

- **Points forts** : surface fonctionnelle large, tests présents.
- **Faiblesses** : il faut **vérifier explicitement** que la performance
  totale backtest = `MTM(stock_bars_daily.close) +
  cumulative(portfolio_cash_ledger)` (cf. README:15-16). Si l'analytics ne
  charge pas le ledger dividendes, **le backtest sous-estime le rendement
  total** et fausse les comparaisons live/backtest (P1 à confirmer).
- **Risques** : conclusions de calibration biaisées, KPI walk-forward
  trompeurs.
- **Gap pour 10/10** : assertion explicite ledger dividendes, parité
  backtest↔live formalisée, doc `doc/backtesting.md` à enrichir.

---

## 14. `ihm/` — **6.5 / 10**

**Résumé.** Streamlit avec pages riches (overview, pipeline, screening,
portfolio, execution, ml, corporate_actions, reporting, settings,
supervision_ops, risk, backtesting, alpaca_accounts, db_admin).
Découpage Phase 6.2 entamé (`pages/_workflow.py`,
`pages/_data_integrity.py`, `pages/_execution_center.py`,
`pages/_alpha_scanner_diagnostics.py`, `pages/_watcher_block.py`).

- **Points forts** : sélecteur multi-comptes, capital presets exposés,
  diagnostics scanner, panneaux paramètres, watcher embarqué, lancements
  asynchrones.
- **Faiblesses** : `_execution_center.py` reste **2 550 lignes** ; le
  `_build_launch_options` est massif (~1 760 lignes par commentaire en
  tête) ; l'IHM expose `import_alpaca_bar` alors que `bars_provider=eodhd`
  rend cette commande no-op (cf. `pipeline_runner.py` route l'étape
  correctement, mais l'opérateur peut être désorienté).
- **Risques** : régression silencieuse en raison d'un fichier trop massif ;
  divergence IHM ↔ doc.
- **Gap pour 10/10** : finir le découpage `_build_launch_options`, ajouter
  des tests E2E IHM (Streamlit testing), badge clair du provider actif.

---

## 15. Observabilité / `run_summaries` / logs — **7.0 / 10**

**Résumé.** Run summaries en JSON émis avec préfixe magique
(`::alpha_trade_run_summary::`), helpers `core.run_summary` (versioning,
IEX bias counters merge, live progress), persistance via
`database.run_business_summaries`.

- **Points forts** : schéma versioning, propagation IEX bias counters,
  watcher heartbeats persistés (Phase 1.2).
- **Faiblesses** : pas de dashboard standardisé en dehors de l'IHM ; logs
  fichier pas réellement audités.
- **Risques** : run summary émis mais non lu si IHM absente.
- **Gap pour 10/10** : alerting externe (mail/Slack), KPI ops uniformisés.

---

## 16. Sécurité / readiness production — **6.0 / 10**

**Résumé.** Sentinelles secrets DB rejetées au démarrage (`core.secrets`),
ressaisie label compte live obligatoire, `RuntimeError` si
`get_account_equity` échoue (plus de fallback 100 000 $).

- **Points forts** : améliorations récentes documentées README:25-33.
- **Faiblesses** : `run_execution.py:60-62` ne check pas
  `ALPACA_<ID>_API_KEY` quand `--account live1` est fourni → erreur tardive
  côté broker. `config.yaml:10-11` contient encore les valeurs `"PK..."`
  textuelles (rétrocompat).
- **Risques** : ordre live envoyé en croyant être sur le bon compte alors
  que le client retombe sur `default`.
- **Gap pour 10/10** : check env contextuel par `--account`, kill switch
  global facilement actionnable, recette pré-live formalisée.

---

## 17. Qualité logicielle globale — **7.0 / 10**

**Résumé.** ~190 fichiers de tests, mypy strict (`mypy.ini`), ruff (cf.
README:413), `.importlinter` présent (visible dans le tooling).

- **Points forts** : couverture large des modules critiques, tests dédiés
  EODHD switch, idempotence CA, sizing, circuit breaker, executor.
- **Faiblesses** : modules massifs (`alpha_scanner.py` 1 421 l.,
  `executor.py` 1 318 l., `_execution_center.py` 2 550 l.,
  `import_eodhd_bar.py` 871 l.) ; absence visible de couverture E2E IHM
  (Streamlit testing) ; doc d'archi technique partielle.
- **Risques** : régressions silencieuses dans les zones massives.
- **Gap pour 10/10** : seuil de couverture obligatoire en CI, tests E2E,
  refactor des fichiers > 1 000 lignes.

---

## Synthèse

Voir `01_global_scorecard.md` pour le tableau récapitulatif et la note
globale **6.4 / 10**.


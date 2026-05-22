# 03 — Registre d'anomalies

> Sévérités : **P0** (bloquant prod), **P1** (à corriger sous 1–2 sprints),
> **P2** (à traiter dans le trimestre), **P3** (dette / amélioration).
> Confiance : H/M/L (Haute / Moyenne / Limitée — basée sur la profondeur
> de lecture réelle du code par l'auditeur).

> Conventions : chaque anomalie P0/P1 a au moins **un test précis associé**
> (cf. [`10_anomaly_test_matrix.md`](10_anomaly_test_matrix.md) pour la
> matrice complète).

---

## A-001 — Risk per trade agressif sur micro-comptes

| Champ | Valeur |
|---|---|
| Sévérité | **P1** |
| Domaine | risk_management / configuration |
| Confiance | H |
| Preuve | `config/capital_presets.yaml:15` (`risk_per_trade_pct: 0.015` sur 0–2k€), `:66` (`0.02` sur 2k–5k$). |
| Description | Sur un compte 2 000 $ avec 3 lignes max, un stop mal placé risque facilement 1.5–3 % de l'equity. Combiné aux frais Alpaca/spread sur small ticket, l'edge attendu est très érodé. |
| Impact métier | Drawdowns rapides sur séries de 3–5 trades adverses → effet décourageant pour le débutant ciblé. |
| Impact technique | Aucun bug ; paramétrage. |
| Probabilité | Élevée si l'opérateur enchaîne 5–10 trades dans une fenêtre adverse. |
| Recommandation | Réduire à `risk_per_trade_pct: 0.0075–0.01` pour 0–2 k€ et 0–5 k$ ; ajouter un test propriété "DD théorique max si N trades stop-loss consécutifs ≤ `risk_max_drawdown_pct`". |
| Test associé | `tests/test_capital_preset_risk_overrides.py` (étendre) — voir matrice. |

---

## A-002 — Double point d'entrée d'exécution

| Champ | Valeur |
|---|---|
| Sévérité | **P1** |
| Domaine | execution_engine / ops |
| Confiance | H |
| Preuve | `run_execution.py` (1060 lignes, launcher canonique) + façade `python -m execution_engine` documentée comme compatibilité (`README.md §8`). |
| Description | Deux chemins d'entrée pour le flux `run`. Risque de divergence des contrôles (env vars, ressaisie label live, prompts) si modifications appliquées d'un seul côté. |
| Impact métier | Un opérateur lance `-m execution_engine` en live et bypasse une garde-fou ajoutée uniquement à `run_execution.py`. |
| Impact technique | Duplication maintenance. |
| Recommandation | Marquer `python -m execution_engine` comme **dépréciée pour `run`** (DeprecationWarning runtime + bandeau IHM), garder uniquement `cancel-all` natif. Tests de contrat équivalence des deux chemins en attendant. |
| Test associé | `tests/test_execution_cli_cancel_all.py` à étendre + nouveau `tests/test_run_execution_vs_facade_parity.py`. |

---

## A-003 — Ordre des étapes `event_sentiment` non verrouillé

| Champ | Valeur |
|---|---|
| Sévérité | **P1** |
| Domaine | event_sentiment |
| Confiance | H |
| Preuve | `README.md §8 Sentiment` (5 étapes), `event_sentiment/event_sentiment_pipeline.py` et `pipeline.py` ; pas d'assert bloquant que `relevance` a tourné avant `scoring`. |
| Description | Si l'opérateur lance manuellement `scoring` puis `relevance`, les features sentiment downstream peuvent être partielles ou biaisées. |
| Impact métier | Conviction altérée → sizing erroné. |
| Recommandation | Verrou d'ordre : `signal_aggregator` refuse de tourner si checkpoints `relevance_backfill_at` ou `contextual_scoring_at` ne sont pas postérieurs à la dernière ingestion news. |
| Test associé | Nouveau `tests/test_event_sentiment_ordering_guard.py`. |

---

## A-004 — Quotes/spread mesurés sur NBBO IEX biaisé

| Champ | Valeur |
|---|---|
| Sévérité | **P1** |
| Domaine | dataIntegrityEngine / selector |
| Confiance | H |
| Preuve | `doc/dataIntegrityEngine.md §0` (bandeau IEX), `config.yaml:181-184` (eodhd primaire pour barres mais quotes restent Alpaca/IEX), `capital_presets.yaml selector_max_spread_bps*`. |
| Description | Le filtre `max_spread_bps` est mesuré sur quotes IEX (NBBO partiel). En swing US, ce biais induit des faux positifs (liquidité sous-évaluée) et des faux négatifs (spreads gonflés). |
| Impact métier | Univers selector déformé ; petit compte plus exposé. |
| Recommandation | Court terme : exposer la métrique d'écart "quote IEX vs quote consolidée bulk" et un seuil de confiance par ticker. Moyen terme : plug Alpaca SIP ou Polygon NBBO pour les quotes. |
| Test associé | Nouveau `tests/test_quote_iex_vs_consolidated_bias.py`. |

---

## A-005 — Réconciliation J+1 vs broker statement absente en IHM

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | execution_engine / observabilité |
| Confiance | M |
| Preuve | `execution_engine/reconciliation.py` + `broker_state_sync.py` existent ; aucune page IHM ni job CLI documenté "rapprocher avec le statement Alpaca J+1". |
| Description | Le suivi runtime est OK mais pas de contrôle indépendant J+1. |
| Recommandation | Page IHM "Réconciliation J+1" + job nightly + alerting sur divergence > 1 bps. |
| Test associé | `tests/test_broker_statement_reconciliation.py` (étend l'existant). |
| Avancement 2026-05-22 | ✅ Job canonique `execution_engine.reconcile_statement` + persistance du résumé J+1 dans `run_business_summaries` + section IHM dédiée. Reste : parsing PDF natif si requis. |

---

## A-006 — Kelly désactivé partout mais machinerie présente

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | risk_management / configuration |
| Confiance | H |
| Preuve | `config/capital_presets.yaml` : `risk_enable_kelly: false` sur les 7 tranches ; `risk_management/kelly.py` + `tests/test_kelly_sizer.py` existent. |
| Description | Soit Kelly est expérimental (alors `enabled: false` doit être documenté comme tel et la machinerie marquée beta), soit on l'active sur tranches ≥ 25 k$ après calibration. État actuel = incohérence apparente. |
| Recommandation | Décision explicite documentée dans `doc/risk_management.md`. |
| Test associé | `tests/test_kelly_sizer.py` (étendre avec scénario activation conditionnelle). |

---

## A-007 — `macro_provider: eodhd` consomme le quota EODHD sans nécessité

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | configuration / service.eodhd |
| Confiance | H |
| Preuve | `config.yaml:62` `macro_provider: eodhd` ; commentaire l. 59-61 mentionne `stooq` gratuit et `composite` possible. |
| Description | VIX/yields sont accessibles via Stooq gratuit ; consommer le quota EODHD pour ces séries macro réduit le budget OHLCV daily. |
| Recommandation | Défaut `macro_provider: composite` (stooq primaire, EODHD fallback). |
| Test associé | `tests/test_macro_providers.py` (existe — étendre cas `composite`). |

---

## A-008 — `selector_min_close=10$` trop restrictif pour micro-comptes

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | selector / configuration |
| Confiance | H |
| Preuve | `capital_presets.yaml:44` (0–2k€ min_close=10), `:96` (2–5k$ aligné 10$, was 5$). |
| Description | Bon pour limiter l'impact des frais fixes ; mais sur 2 000 $ et 3 lignes (~660 $/ligne), interdire <10 $/share réduit massivement l'univers en swing. Combiné aux filtres market_cap ≥ 500M$, on peut tomber sous 30 tickers. |
| Recommandation | Soit baisser à 7 $ sur 0–2k€, soit augmenter `risk_max_positions=4` et `min_close=10` cohérent. Mesurer empiriquement `selector_universe_size_p25` par tranche. |
| Test associé | `tests/test_capital_preset_universe_yield.py` (existe — étendre). |

---

## A-009 — Parité backtest ↔ live non garantie avec sentiment + ML + macro

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | backtesting / event_sentiment / modelFactory |
| Confiance | M |
| Preuve | `tests/test_parity_backtest_live.py`, `backtesting/signal_replay.py`, `backtesting/parity.py` existent. Pas d'oracle "replay live → backtest" avec sentiment+ML+macro activés simultanément. |
| Description | Risque d'illusion de performance backtest. |
| Recommandation | CI nightly : replay 10 jours live d'un compte paper et comparer à un backtest piloté par les mêmes inputs PIT, avec ε de tolérance déclaré. |
| Test associé | Nouveau `tests/test_parity_backtest_live_full_stack.py`. |
| Avancement 2026-05-22 | 🟡 Test dédié `tests/test_parity_backtest_live_full_stack.py` ajouté sur le socle `backtesting.fidelity.build_compare_to_live_summary(...)`; reste à industrialiser un vrai job nightly 10 jours si voulu. |

---

## A-010 — Doc hétérogène et POCs visibles

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | documentation |
| Confiance | M |
| Preuve | `doc/async_db_poc.md`, `doc/formal_verification.md`, `doc/tlaps_proofs.md` mélangés avec docs prod. |
| Description | Un nouvel arrivant peut prendre un POC pour un état actuel. |
| Recommandation | Sous-dossier `doc/_poc/` ou bandeau `> ⚠️ POC — non activé en prod`. |
| Test associé | `tests/test_doc_index_and_links.py` (étendre pour exiger bandeau sur POCs). |

---

## A-011 — `risk_management.empirical_calibration.fallback_levels` non testé pour ordre dégradé

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | risk_management |
| Confiance | M |
| Preuve | `config.yaml:153-161` 8 niveaux de fallback `weights_calibration_runs`. Comportement P3+ par défaut. |
| Description | L'ordre est documenté mais pas de test garantissant que chaque niveau est effectivement consulté et qu'un fallback inattendu ne masque pas une absence de calibration. |
| Recommandation | Test propriété "si un niveau ne renvoie pas, on tente exactement le suivant ; on log le niveau choisi dans le run_summary". |
| Test associé | `tests/test_weights_calibration.py` (étendre). |

---

## A-012 — `notifications:` smtp commenté → silence si vault non configuré

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | observabilité / ihm |
| Confiance | H |
| Preuve | `config.yaml:218-227` (bloc commenté), `tests/test_ihm_notifications.py` couvre l'IHM mais pas le cas "SMTP absent + opérateur croit recevoir des mails". |
| Description | L'opérateur configure les destinataires dans l'IHM mais ne reçoit rien tant qu'aucune variable d'env SMTP n'est posée. |
| Recommandation | Bannière IHM "SMTP non configuré → aucune notification envoyée" + log avertissement au démarrage. |
| Test associé | Nouveau `tests/test_ihm_notifications_smtp_missing_banner.py`. |

---

## A-013 — `fallback_on_failure: true` sur `market_data` sans alerting

| Champ | Valeur |
|---|---|
| Sévérité | **P1** |
| Domaine | dataIntegrityEngine / observabilité |
| Confiance | H |
| Preuve | `config.yaml:183`. |
| Description | En cas d'incident EODHD, on bascule silencieusement sur Alpaca/IEX → les barres ingérées le jour J ont un `data_source=alpaca_iex` différent du J-1 et le volume devient biaisé sans alerte. |
| Recommandation | Émettre une métrique + alerte si `data_source` change vs J-1, et marquer le run_summary `provider_fallback_triggered=true` en flag haut niveau. |
| Test associé | `tests/test_eodhd_provider_switch.py` (existe — étendre pour assertion alerte). |

---

## A-014 — `selector_max_anomaly_count` élevé sur micro-compte (28)

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | selector |
| Confiance | M |
| Preuve | `capital_presets.yaml:56` (micro 0–2k€ = 28), descendant jusqu'à 18 pour 100k+. |
| Description | Plus le compte est petit, plus on tolère d'anomalies (zéro volume, stale, etc.) — c'est l'inverse de la prudence attendue. |
| Recommandation | Inverser le sens : micro-compte ≤ 15 anomalies, gros compte plus tolérant. |
| Test associé | `tests/test_capital_presets.py` (étendre monotonie). |

---

## A-015 — Pas de garde IHM contre lancement pipeline étape N si N-1 a échoué

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | ihm / orchestration |
| Confiance | M |
| Preuve | `ihm/pages/` + `ihm/services/` + `tests/test_ihm_pipeline_runner.py`. |
| Description | Aucun garde-fou explicite ; l'opérateur peut lancer `selector` après un `import_eodhd_bar` échoué. |
| Recommandation | "Pipeline state machine" IHM : étapes verrouillées tant que N-1 n'est pas `SUCCESS`. |
| Test associé | Nouveau `tests/test_ihm_pipeline_state_machine_lock.py`. |
| Avancement 2026-05-22 | ✅ Verrou state-machine ajouté dans `ihm/pages/pipeline.py` avec helper testé. |

---

## A-016 — IBKR adapter présent mais doctrine basculement opaque

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | service / execution_engine |
| Confiance | M |
| Preuve | `service/ibkr/`, `tests/test_ibkr_adapter_paper.py`, `service/broker_failover.py`, `tests/test_failover_alpaca_to_ibkr.py`. |
| Description | Capacité réelle ; mais ni runbook ni IHM "broker primaire / secondaire" documenté côté opérateur. |
| Recommandation | `doc/runbook_broker_failover.md` + page IHM "Brokers". |

---

## A-017 — Coverage de tests non bloquante en CI publique

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | qualité logicielle |
| Confiance | L (CI pas inspectée) |
| Preuve | `coverage.json` présent mais pas de gate visible (`pytest.ini`, `pyproject.toml`). |
| Recommandation | Gate ≥ 80 % par module critique (risk, execution, corporate_actions, dataIntegrityEngine). |

---

## A-018 — `windows_sleep_guard` actif : couplage Windows fort

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | common / portabilité |
| Confiance | H |
| Preuve | `common/windows_sleep_guard.py`, `tests/test_windows_sleep_guard.py`. |
| Description | Le projet est viable sur Linux mais Windows est implicitement la cible principale. À documenter (déjà partiellement). |

---

## A-019 — `event_sentiment` dépend de provider news EODHD primaire — couplage quota

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | event_sentiment / service.eodhd |
| Confiance | H |
| Preuve | `README.md §8 Sentiment` ("provider news par défaut: eodhd"). |
| Description | Le quota EODHD 100 000 daily est partagé entre OHLCV + news + macro. Sur univers screener large, le quota peut saturer. |
| Recommandation | Tableau de bord "EODHD quota by feature" en IHM (déjà partiellement via run_summary). |
| Test associé | `tests/test_clientEodhd.py` (étend quota tracker). |

---

## A-020 — Pas de signature des artefacts ML (`artifacts/models/`)

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | sécurité / modelFactory |
| Confiance | H |
| Preuve | Dossier `artifacts/models/` non signé, pas de checksum visible. |
| Recommandation | SHA256 + manifest signé au moment du champion selection. |
| Test associé | `tests/test_ml_artifacts_backup.py` (étend). |

---

## A-021 — `execution_engine.preflight` non bloquant en mode `simulate`

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | execution_engine |
| Confiance | M |
| Preuve | `tests/test_run_execution_blocks_on_preflight_fail.py` couvre paper/live, à confirmer simulate. |
| Description | Acceptable mais l'opérateur peut prendre l'habitude que `simulate` valide tout, ce qui crée un faux sentiment de sécurité. |

---

## A-022 — Schéma `stock_bars_daily PRIMARY KEY (symbol,date)` empêche cohabitation multi-source daily

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | database / dataIntegrityEngine |
| Confiance | H |
| Preuve | `doc/data_lineage_matrix.md:16-21`. |
| Description | Empêche un comparatif Alpaca vs EODHD same-day natif. |
| Recommandation | Migration optionnelle `PRIMARY KEY (symbol,date,data_source)` derrière un feature flag. |
| Test associé | Nouveau `tests/test_data_adjustment_multisource_migration.py`. |

---

## A-023 — Pas de runbook publié pour incident sentiment provider (EODHD news)

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | observabilité |
| Confiance | M |
| Preuve | `doc/runbook_provider_incident.md` couvre OHLCV ; pas l'équivalent dédié news. |
| Recommandation | Étendre le runbook existant. |

---

## A-024 — Pas de gel de l'IHM pendant un `live` exécutant

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | ihm / execution_engine |
| Confiance | M |
| Preuve | `ihm/services/`, `test_ihm_pipeline_concurrency_lock.py` couvre pipeline mais pas le cas "exécution live en cours". |
| Recommandation | Bandeau persistant + désactivation des actions destructrices tant que `execution_runs.status='RUNNING' AND mode='live'`. |
| Avancement 2026-05-22 | ✅ Bandeau persistant + gel des lancements manuels/kill switch IHM pendant un run `live` actif. |

---

## A-025 — `risk_correlation_threshold` 0.92–0.78 décroissant : OK ; mais corrélation calculée sur quels prix ?

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | risk_management |
| Confiance | M |
| Preuve | `risk_management/correlation_filter.py`, `tests/test_correlation_filter.py`. |
| Description | À confirmer : corrélation calculée sur `stock_bars_daily.close` split-adjusted (correct) ou sur returns log-adjusted dividendes ? Pour des paires à fort dividende, l'écart peut être notable. |
| Recommandation | Documenter explicitement et tester les deux conventions. |
| Avancement 2026-05-22 | ✅ Convention explicitée dans le code (`price_only_close_split_adjusted` vs `total_return_with_cash_dividends`) + tests dédiés. |

---

## A-026 — Pas d'audit visible "DST / fuseaux" sur calendrier de trading

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | common |
| Confiance | M |
| Preuve | `common/market_calendar.py`, `tests/test_market_calendar.py`, `tests/test_entrypoints_and_market_calendar.py`. |
| Description | Vérifier que le passage DST automnal/printanier ne décale pas les jobs (early close à 13:00 ET notamment). |

---

## A-027 — Pas de quota check préventif EODHD avant `event_sentiment` large run

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | service.eodhd / event_sentiment |
| Confiance | M |
| Preuve | `service/eodhd/quota.py`, `EodhdQuotaTracker`. |
| Description | Le tracker existe ; rien ne semble empêcher de lancer un `event_sentiment --all-symbols` qui ferait sauter le quota. |
| Recommandation | Pre-check "estimated_calls vs remaining_quota → abort si < marge". |

---

## A-028 — Documentation `selector_min_relative_strength_index ≥ 100` ambiguë

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | selector / doc |
| Confiance | M |
| Preuve | `capital_presets.yaml:46-348` (valeurs ≥ 100). |
| Description | Le nom "relative strength index" évoque le RSI classique [0–100] ; ici il s'agit visiblement d'un IBD-like RS rank (centré 100). Ambiguïté nommage. |
| Recommandation | Renommer `selector_min_ibd_rs_rank` ou ajouter docstring + commentaire dans le YAML. |

---

## A-029 — `risk_max_drawdown_pct` 18 % sur gros compte vs 7 % sur micro : monotonie correcte mais explication métier à documenter

| Champ | Valeur |
|---|---|
| Sévérité | **P3** |
| Domaine | doc / risk_management |
| Confiance | H |
| Preuve | `capital_presets.yaml:22, 274, 324`. |
| Description | Choix justifié (gros compte = plus de patience) mais à documenter ; ratio risk/return mensuel à objectiver. |

---

## A-030 — Pas d'oracle "MTM + ledger = total return" en test

| Champ | Valeur |
|---|---|
| Sévérité | **P2** |
| Domaine | corporate_actions / backtesting |
| Confiance | M |
| Preuve | `tests/test_backtest_total_return_with_dividends.py` existe — vérifier qu'il oracle un ground truth externe. |
| Recommandation | Comparer sur 3–5 tickers à dividende récurrent avec données Bloomberg/Yahoo total return. |
| Avancement 2026-05-22 | 🟡 Helper `compare_total_return_to_oracle(...)` ajouté avec tolérance en bps ; reste à brancher un téléchargement nightly d'oracle externe réel si voulu. |

---

Total : **30 anomalies** (0 P0, 5 P1, 16 P2, 9 P3). Voir
[`10_anomaly_test_matrix.md`](10_anomaly_test_matrix.md) pour la matrice
anomalie → test → sprint.


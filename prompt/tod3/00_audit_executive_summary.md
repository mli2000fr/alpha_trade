# 00 — Synthèse exécutive de l'audit

**Date** : 2026-05-22 — **Auditeur** : Copilot agent — **Périmètre** : dépôt
complet Alpha Trade.

## TL;DR

Alpha Trade est une plateforme Python de swing trading US **nettement plus
mature que la moyenne des projets indépendants** : pipeline modulaire de
bout en bout, ~280 fichiers de tests, conventions de données explicitées,
scanner de secrets, recette pré-live, audits internes historisés
(`prompt/refactor/`, `doc/audit/`, `doc/external_audit/`), IHM Streamlit
de supervision riche, presets de capital paramétrés sur 7 tranches.

**Note globale : 7.4 / 10** — verdict : **quasi-pro / pro-grade partiel**
pour usage swing US d'un opérateur indépendant discipliné, avec quelques
zones encore fragiles avant un usage **live argent réel intensif**.

## Forces principales

1. **Conventions OHLCV verrouillées** : `data_adjustment='split'`,
   contraintes SQL `chk_bars_adj` / `chk_daily_adj`, dividendes via
   `portfolio_cash_ledger` (cf. `corporate_actions/engine.py:34-55`).
2. **Provider switch propre** : `market_data.bars_provider` (`eodhd` |
   `alpaca`) avec rétrocompat, no-op contrôlé sur l'autre commande
   (test `tests/test_import_alpaca_bar_noop.py`).
3. **Sécurité secrets** : aucun secret en clair tolérable
   (`core.secrets.scan_yaml_for_literal_secrets` + test
   `tests/test_config_no_literal_secrets.py`).
4. **Exécution carrée** : launcher canonique `run_execution.py`, modes
   `simulate / paper / live / check`, ressaisie du label compte en live,
   `RuntimeError` si equity broker indisponible, machine d'états
   séparée (`execution_engine/state_machine.py`), réconciliation,
   kill-switch (`cancel-all`), watcher post-run secondaire.
5. **Risk management** profond : sizing ATR, Kelly, fusion conviction
   (`core/conviction.py`), corrélation, circuit breaker, contraintes
   sectorielles, regime overlay (`risk_management/regime_apply.py`).
6. **Backtesting** : parité live (`backtesting/parity.py`,
   `execution_lifecycle_replay.py`), fidélité (`fidelity.py`),
   diagnostics screener dédiés, walk-forward, fuzz tolérance, statistique.
7. **Observabilité** : `run_summary` structurés homogènes par module,
   bandeaux IEX, lineage (`scripts/generate_data_lineage.py`), runbooks
   dédiés (provider incident, réconciliation, 24/7, sandbox).
8. **IHM** : sélecteur de compte multi-paper/live, pages spécialisées
   (pipeline, screening, portfolio, exécution scopée run, ML, CA,
   reporting, paramètres), tests E2E `test_ihm_pipeline_e2e.py`,
   `test_ihm_execution_e2e.py`.

## Faiblesses majeures

| ID | Faiblesse | Sévérité |
|---|---|---|
| A-001 | `risk_per_trade_pct = 1.5–2 %` sur micro-comptes 0–5 k$ : combiné à 3–4 lignes seulement, R-max théorique tolère facilement 3–6 % de l'equity sur une seule erreur de stop ; agressif pour un débutant. | P1 |
| A-002 | Présence simultanée d'un launcher `run_execution.py` **et** d'une façade `python -m execution_engine` : risque de double point d'entrée, divergence des comportements (validation env, prompts live) si non testé sur chaque chemin. | P1 |
| A-003 | `event_sentiment` enchaîne 5 sous-étapes (cf. README §8 et `event_sentiment_pipeline.py`) : l'ordre est documenté mais aucun garde-fou bloquant n'empêche une exécution dans le mauvais ordre depuis l'IHM ou en CLI manuelle → risque de features sentiment partielles. | P1 |
| A-004 | `quotes` et `metadata` restent Alpaca/IEX **même en mode `bars_provider=eodhd`** : `selector.max_spread_bps` est mesuré sur un NBBO biaisé IEX (~50 bps) → le filtre peut être à la fois trop laxiste (spreads IEX gonflés) et trop sévère selon le ticker. Documenté dans le bandeau IEX mais aucune métrique d'écart « quote IEX vs quote consolidée » n'est produite. | P1 |
| A-005 | Réconciliation `execution_reconciliation_results` : présente mais aucune métrique consolidée de **réconciliation J+1 vs broker statement** (Alpaca CSV/PDF) n'est exposée en IHM ; risque de dérive silencieuse. | P2 |
| A-006 | `risk_enable_kelly: false` sur **toutes** les tranches : la machinerie Kelly existe (`risk_management/kelly.py`) mais reste désactivée ; soit la documenter comme "expérimental", soit retirer le flag — incohérence apparente. | P2 |
| A-007 | `market_regimes.macro_provider: eodhd` consomme du quota EODHD pour VIX/yields alors qu'un fallback `stooq` (gratuit) existe (`macro_provider: composite`) ; un opérateur peut saturer son quota EODHD daily (100 000) sans s'en apercevoir. | P2 |
| A-008 | `selector_min_close = 10$` désormais uniforme sur 0–25 k$ (cf. `capital_presets.yaml`) : sur un compte 2 000 $, exiger ≥ 10 $/action restreint très significativement l'univers réellement actionnable en 3–4 lignes. | P2 |
| A-009 | Backtesting → live parity : `test_parity_backtest_live.py` existe mais ne garantit pas la parité quand la chaîne **sentiment + ML + macro** est activée (le replay (`signal_replay.py`) reconstitue, mais pas d'oracle global). | P2 |
| A-010 | Documentation `doc/` (~60 fichiers) : très étoffée mais hétérogène en fraîcheur ; plusieurs docs renvoient à des sprints (S25/S26/S27/S30) sans index unique des "conventions en vigueur" facilement consultable hors `doc/INDEX.md`. | P3 |

Détail complet → [`03_anomalies_register.md`](03_anomalies_register.md).

## Verdict synthétique

| Critère | Verdict |
|---|---|
| Cohérent ? | Oui, conventions canoniques explicitées (split-only, dividendes en ledger). |
| Robuste ? | Oui sur l'ossature ; fragile sur micro-comptes 0–5k$ et sur la qualité quotes IEX. |
| Maintenable ? | Oui : tests massifs, modules <2k lignes par fichier, refactors documentés. |
| Exploitable prod ? | **Quasi** : recette pré-live opérationnelle, mais réconciliation J+1 et alerting opérateur à muscler. |
| Adapté swing US réel ? | **Oui** à partir de 10–25 k$ ; **prudence forte** sous 5 k$. |
| Proche d'un niveau pro ? | **Pro-grade partiel** ; il manque ~2 sprints structurants pour passer "pro-grade". |

## Top 5 actions prioritaires (extraits du plan)

1. **Sprint S1** — Durcir presets micro-comptes (A-001, A-008) et publier un mode "discovery" pour 0–5 k$.
2. **Sprint S1** — Unifier la doctrine d'entrée d'exécution (A-002) : `run_execution.py` reste canonique, déprécier la façade `-m execution_engine` sauf `cancel-all`.
3. **Sprint S2** — Verrouillage d'ordre `event_sentiment` (A-003) + assertion IHM.
4. **Sprint S2** — Métrique "spread IEX vs spread consolidé" (A-004) ou plug Alpaca SIP/Polygon.
5. **Sprint S3** — Réconciliation J+1 vs broker statement (A-005) avec page IHM dédiée.

À partir du **Sprint S3**, l'application est **considérée comme robuste pour
un swing trading réel discipliné sur compte ≥ 10 k$**.

Détail complet → [`08_sprint_plan.md`](08_sprint_plan.md).


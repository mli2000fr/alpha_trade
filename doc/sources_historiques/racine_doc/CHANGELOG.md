# Changelog documentaire Alpha Trade

> Journal synthétique des changements de conventions, docs structurantes et clarifications opératoires.

## 2026-05-22 — Clôture documentaire S7 + reliquat A-004

### Ajouté

- `doc/CONVENTIONS.md` comme index unique des conventions canoniques.
- Exposition documentaire du proxy `quote_iex_vs_consolidated_bps`
  (biais quotes IEX vs close consolidée même séance).
- Bandeaux explicites `POC non activé` sur les documents de recherche / consultant.
- Tests DST sur `common/market_calendar.py` (mars / juillet / novembre).

### Mis à jour

- `doc/DOC_FONCTIONNELLE.md` pour refléter l’état S1–S6, le launcher canonique d’exécution,
  les conventions micro-compte, Kelly conditionnel et le proxy A-004.
- `doc/DOC_TECHNIQUE.md` pour refléter l’état S1–S6, les conventions documentaires,
  la signature d’artefacts ML et le proxy de biais quotes IEX.
- `scripts/generate_doc_index.py` pour ignorer les faux H1 dans les blocs de code,
  classer les documents centraux S7 et échapper les cellules Markdown de `doc/INDEX.md`.
- `doc/INDEX.md` régénéré avec les nouvelles entrées S7.

### Confirmé / figé

- `bars_provider=eodhd` reste la convention primaire.
- `data_adjustment="split"` reste la convention unique.
- Les quotes restent servies par `Alpaca / IEX`.
- `run_execution.py` reste l’entrée canonique du flux `run`.
- `python -m execution_engine` reste une façade legacy avec dépréciation pour `run`.

## 2026-05-22 — Synthèse S1 à S6 reflétée dans la documentation

- **S1** : durcissement micro-comptes, alias `selector_min_ibd_rs_rank`, doctrine de dépréciation `execution_engine`.
- **S2** : garde d’ordre sentiment, observabilité provider fallback, quota EODHD, proxy IEX vs consolidé désormais exposé.
- **S3** : réconciliation J+1, TCA agrégé, gel IHM en live.
- **S4** : convention corrélation explicite, oracle total return, parité backtest/live full-stack.
- **S5** : signatures d’artefacts ML et doctrine failover broker.
- **S6** : `macro_provider=composite`, Kelly conditionnel, bandeau SMTP, clarification `risk_max_drawdown_pct`.



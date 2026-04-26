# `core/` + `common/` — Modules de socle

> Documentation Phase 2.1 du refactor (`prompt/refactor/plan.md`).
> Référence audit : `prompt/refactor/audit_core_common.md`.

## Vue d'ensemble

Les packages `core/` et `common/` forment le **socle transverse** consommé par
tous les modules métier (screener, selector, event_sentiment, modelFactory,
risk_management, execution_engine, backtesting, ihm, watcher).

Ils n'ont **aucune dépendance vers les modules métier** (règle architecturale
qui sera enforced via `import-linter` en Phase 7).

```
core/
├── interfaces.py        # Tous les Protocol typés (BrokerPort, BarsRepository, …)
├── types.py             # Aliases (Symbol, AccountId, Adjustment, Feed)
├── conviction.py        # Formule de fusion conviction partagée
├── filter_profiles.py   # Profils de filtres communs (STRICT_SWING_CASH_FILTERS)
├── eligibility.py       # Règles d'éligibilité (PIT-safe)
├── run_summary.py       # Helper schema_version + payload run_summary
└── secrets.py           # Lecture stricte secrets DB (placeholders refusés)

common/
├── logging_setup.py     # configure_root_logging, RotatingFileHandler
├── market_calendar.py   # NYSE calendar (pandas_market_calendars)
├── config_loader.py     # load_config(YAML)
└── utils.py             # Façade rétrocompatible (re-exports)
```

## `core/interfaces.py` — Protocols centralisés

### Pourquoi
Avant Phase 2 : chaque module redéfinissait son propre Protocol ad-hoc, parfois
incompatible. Conséquences : tests difficiles à mocker, couplage implicite aux
implémentations Alpaca/SQLAlchemy.

### Catalogue
| Protocol | Module producteur | Consommateurs |
|---|---|---|
| `PriceRepository` / `BarsRepository` | `database.repositories.bars` | screener, selector, modelFactory |
| `ScoreRepository` / `ScoresRepository` | `database.repositories.scores` | selector, risk_management |
| `MarketDataPort` | `service.alpaca.clientAlpaca` | dataIntegrityEngine |
| `BrokerPort` | `service.alpaca.accounts` + Alpaca trading | execution_engine, risk_management |
| `RiskRepository` | (à créer Phase 5.1) | risk_management |
| `ExecutionRepository` | `execution_engine.db_io` | execution_engine, ihm |
| `NewsProvider` | `service.alpaca.clientNewsAlpaca` | event_sentiment |
| `CorporateActionProvider` | `corporate_actions.provider` | dataIntegrityEngine |
| `SentimentProvider` | `event_sentiment.aggregation` | risk_management, selector |
| `FactorEngine` / `ScoringEngine` | `selector.alpha_scanner` | selector |
| `RiskChecker` / `OrderManager` | `risk_management.*` / `execution_engine.*` | execution_engine |
| `ConvictionAggregator` | `core.conviction` | risk_management, event_sentiment |

### Règle d'or
Les modules métier **DOIVENT** typer leurs paramètres via ces Protocols et
**JAMAIS** importer une classe concrète depuis `service/` ou `database/`
directement (sauf au point d'instanciation `__main__` / `cli.py`).

## `core/conviction.py` — Formule unique

Avant : `risk_management.conviction.combine_signals` ET
`event_sentiment.signal_aggregator.fuse` re-implémentaient une formule similaire
avec drift potentiel. Phase 2.1 introduit une référence unique :

```python
from core.conviction import ConvictionWeights, fuse_conviction

weights = ConvictionWeights(quant=0.4, sentiment=0.6)
score = fuse_conviction(quant_score=0.72, sentiment_score=0.55, weights=weights)
```

Migration prévue :
- `risk_management` : Phase 5.1.
- `event_sentiment.signal_aggregator` : Phase 4.1.
- `backtesting.signal_replay` : Phase 6.1.

## `core/filter_profiles.py` — Profils partagés

Centralise `STRICT_SWING_CASH_FILTERS` et autres profils partagés entre
`selector/`, `screener/`, `backtesting/`. Le module historique
`selector/strict_filter_profiles.py` reste le **point d'implémentation** ;
`core/filter_profiles.py` ré-exporte pour offrir un point d'import stable
indépendant du module métier.

## `common/utils.py` — Façade

Décomposition en sous-modules (Phase 2.1) :

| Sous-module | Contenu | Exemple d'import |
|---|---|---|
| `common.logging_setup` | `configure_root_logging`, `setup_logging_with_file_handler`, `DEFAULT_LOG_FORMAT`, `PROJECT_ROOT` | `from common.logging_setup import configure_root_logging` |
| `common.market_calendar` | `is_trading_day`, `is_us_market_holiday`, `getLastDateMarche` | `from common.market_calendar import getLastDateMarche` |
| `common.config_loader` | `load_config(path?)` | `from common.config_loader import load_config` |
| `common.utils` (façade) | Re-exports tous les symboles publics historiques | `from common.utils import configure_root_logging` (rétrocompatible) |

Les **nouveaux** modules consommateurs doivent importer depuis le sous-module
adapté, pour préparer la dépréciation progressive de la façade.

## `core/run_summary.py` — Schema version

Phase 1.3 a introduit `schema_version: int = 1` dans tous les payloads
`run_summary`. L'helper :

```python
from core.run_summary import build_run_summary

payload = build_run_summary(
    run_id=run_id,
    schema_version=1,
    extra={"chunk_failures": 0, "rejected_by_filter": {…}},
)
```

## `core/secrets.py` — Refus des placeholders

Empêche un démarrage silencieux avec `LOGIN_DB=user / PASSWORD_DB=pass` ou
`changeme`. Liste noire centrale partagée par `database/connection.py`.

## Tests

| Test | Couverture |
|---|---|
| `tests/test_common_utils.py` | Façade `common.utils` + résolution `PROJECT_ROOT` |
| `tests/test_phase1_run_summary.py` | `core.run_summary` schema_version |
| `tests/test_phase1_secrets.py` | `core.secrets` refus placeholders |
| `tests/test_strict_filter_profiles.py` | Profils filtres partagés |
| `tests/test_correlation_filter.py` | `EnrichedCandidate` + fusion conviction |

## Points d'attention

- **Aucun import circulaire** : `core/` ne doit JAMAIS importer un module métier
  (screener, selector, event_sentiment, …). Vérification automatisée Phase 7
  via `import-linter`.
- **Stabilité d'API** : ces modules sont consommés partout, toute évolution
  doit passer par une PR dédiée avec tests + doc mis à jour.
- **Compatibilité ascendante** : la façade `common/utils.py` reste indéfiniment
  pour ne pas casser les imports historiques. Pas de dépréciation programmée
  avant Phase 7.


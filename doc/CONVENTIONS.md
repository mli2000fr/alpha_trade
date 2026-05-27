# Conventions canoniques Alpha Trade

<!-- primary_provider: eodhd -->

> Source de vérité documentaire transversale pour les conventions encore en vigueur.
> En cas d’écart avec une doc plus ancienne, **ce document prime** puis doit être
> répercuté dans `doc/DOC_FONCTIONNELLE.md`, `doc/DOC_TECHNIQUE.md` et les
> runbooks concernés.

## 1. Données marché

- **Provider OHLCV daily primaire** : `EODHD` via `config.yaml > market_data.bars_provider=eodhd`.
- **Mode `alpaca`** : rétrocompatibilité explicite, pas de fallback automatique inter-provider.
- **Quotes bid/ask** : `stock_quote_snapshots` provient d’**Alpaca / IEX**.
- **Convention de prix** : `data_adjustment = "split"` uniquement.
  Les dividendes passent par `portfolio_cash_ledger` / `corporate_actions/`.
- **Proxy de biais quotes IEX** : `quote_iex_vs_consolidated_bps` = écart moyen absolu en bps entre
  le **mid bid/ask IEX** et `stock_bars_daily.close` sur la **même séance**,
  exposé dans les `run_summary` de `sync_latest_quotes`.
- **Conventions corrélation** : prix `split-adjusted` pour les séries de prix,
  rendements `total_return_with_cash_dividends` pour les analyses où les dividendes doivent être inclus.

## 2. Providers annexes

- **News provider par défaut** : `alpaca`.
- **Métadonnées société / secteur / market cap** : `Finnhub`.
- **Earnings calendar** : `Finnhub`.
- **Corporate actions portefeuille** : `Alpaca Corporate Actions`.

## 3. Trading / portefeuille / risque

- **Style opératoire canonique** : `swing_only=True`.
- **Règle PDT** : `pdt_rule=auto` pour les comptes margin < 25 k$.
- **Micro-comptes < 5 k$** : usage éducatif / fortement contraint ; bandeaux IHM obligatoires.
- **Kelly** : activé uniquement sur les presets `>= 25 k$`.
- **Préflight exécution** : bloquant en `paper/live`, dégradé `WARN` en `simulate`.
- **Contrainte live IHM** : gel des actions destructrices si un run live est `RUNNING`.

## 4. Exécution / opérations

- **Entrée canonique du flux `run`** : `run_execution.py`.
- **Compatibilité legacy** : `python -m execution_engine` reste toléré pour `run`
  avec `DeprecationWarning`, mais `cancel-all` reste natif côté module.
- **Doctrine failover broker** : failover manuel/opérateur documenté, pas de bascule silencieuse.
- **Réconciliation broker** : point d’entrée canonique `python -m execution_engine.reconcile_statement`.

## 5. Sécurité / artefacts

- **Signature artefacts ML** : manifestes JSON SHA-256 adjacents aux artefacts, vérifiés au load.
- **Pas de migration DB dédiée** pour cette signature : convention filesystem.
- **IHM** : profil DB read-only souhaitable côté exploitation, mais non bloquant tant qu’il n’est pas livré.

## 6. Documentation / index

- `doc/INDEX.md` est **généré**, pas édité à la main.
- `doc/CHANGELOG.md` trace les changements documentaires / conventions visibles.
- Les documents **POC / recherche / consultant** doivent porter un bandeau explicite
  `POC non activé` ou être déplacés sous `doc/_poc/`.
- Les documents qui parlent de providers marché doivent utiliser le marqueur
  `<!-- primary_provider: eodhd -->` quand pertinent.

## 7. Références associées

- `doc/DOC_FONCTIONNELLE.md`
- `doc/DOC_TECHNIQUE.md`
- `doc/dataIntegrityEngine.md`
- `doc/risk_management.md`
- `doc/runbook_broker_failover.md`
- `doc/CHANGELOG.md`

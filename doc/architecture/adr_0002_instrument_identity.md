# ADR-0002 — Identité canonique des instruments

- Statut : accepté pour implémentation après validation du Sprint 0
- Date : 19 septembre 2026
- Dépendance : ADR-0001

## Contexte

Dans la base US auditée, 58 tables contiennent `symbol` et 39 l’utilisent dans une clé primaire ou unique sans `market_code` ni `instrument_id`. `stock_metadata.symbol` est lui-même la clé primaire. Cette identité n’est pas suffisante pour plusieurs marchés, places, classes de titres, changements de ticker ou symboles fournisseur.

## Décision

Créer un référentiel canonique :

```text
instruments
instrument_id        BIGINT, identité technique dans une base
instrument_uid       identité stable exportable entre bases
market_code
country_code
exchange_mic
local_symbol
currency
valid_from / valid_to
```

`instrument_uid` est stable et construit depuis une identité contrôlée, jamais depuis le seul ticker. Les identifiants numériques peuvent se chevaucher entre `alpha_trade` et `alpha_trade_cn` ; tout échange cross-base utilise donc `instrument_uid` accompagné de `market_code`.

Créer aussi :

- `instrument_provider_symbols` avec période de validité ;
- `instrument_status_history` pour listing, delisting, ST, suspension et board ;
- des contraintes uniques incluant au minimum le marché/MIC et la période appropriée.

## Migration

1. créer le référentiel sans changer les lectures ;
2. backfiller les titres US ;
3. ajouter `instrument_id` nullable aux tables parentes ;
4. dual-write et vérifier la parité ;
5. migrer les jointures et contraintes ;
6. rendre `instrument_id` obligatoire ;
7. conserver `symbol` comme attribut de présentation et index secondaire.

Aucune donnée CN canonique n’est écrite avant la validation du backfill et de la parité US.

## Rejeté

- Préfixer seulement les tickers par `CN:`.
- Utiliser le symbole Tushare comme clé interne.
- Ajouter `market_code` sans reconstruire les contraintes existantes.
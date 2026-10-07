# ADR-0001 — `MarketContext` explicite

- Statut : accepté pour implémentation après validation du Sprint 0
- Date : 19 septembre 2026
- Portée : ingestion, univers, features, ML, backtest, risque, IHM et exécution

## Contexte

Le runtime actuel suppose principalement NYSE, USD, SPY et `America/New_York`. Ces hypothèses sont présentes dans le calendrier, les cutoffs PIT, les benchmarks, les seuils de liquidité et plusieurs commandes. Un simple switch IHM ne suffit pas : deux runs parallèles ne doivent jamais partager un marché mutable global.

La base US observée pendant le Sprint 0 contient 95 tables. Aucune ne porte encore `market_code` ou `instrument_id`. Le contexte marché ne peut donc pas être déduit de manière fiable depuis les lignes existantes.

## Décision

Introduire un objet immuable `MarketContext`, résolu avant toute opération métier et transmis explicitement :

```text
MarketContext
├── market_code          US_EQ | CN_A | CN_BJ
├── database_alias       us_primary | cn_primary
├── country_code
├── currency
├── timezone
├── calendar_id
├── benchmark_instrument
├── sector_taxonomy
├── cost_profile
├── execution_rules_profile
├── feature_profile_root
├── live_enabled
└── short_execution_enabled
```

Règles :

1. une commande moderne doit fournir ou résoudre un `market_code` ;
2. `market_code` et `database_alias` sont validés ensemble par une allowlist ;
3. le contexte est immuable pendant un run ;
4. le contexte effectif et son fingerprint sont persistés dans les manifests ;
5. les traitements cross-sectionnels refusent un dataset multi-marché ;
6. la compatibilité legacy peut résoudre `US_EQ`, mais émet un warning et possède une date de retrait ;
7. aucun singleton `current_market` mutable n’est autorisé.

## Conséquences

- Les APIs de calendrier deviennent génériques tout en conservant temporairement les wrappers NYSE.
- Les batchs, univers, modèles, prédictions et backtests deviennent filtrables par marché.
- Les erreurs de marché deviennent bloquantes avant lecture ou écriture.
- Les tests doivent couvrir deux contextes simultanés et les incompatibilités marché/base.

## Rejeté

- Déduire le marché uniquement du ticker ou du nom de fichier.
- Utiliser un état global IHM.
- Ajouter seulement un champ visuel sans propager le contexte aux repositories.
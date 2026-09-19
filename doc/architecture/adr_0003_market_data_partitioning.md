# ADR-0003 — Isolation physique des données US et Chine

- Statut : accepté
- Date : 19 septembre 2026
- Dépendances : ADR-0001 et ADR-0002

## Décision

Utiliser deux bases physiques avec un contrat logique commun :

```text
alpha_trade       → US_EQ
alpha_trade_cn    → CN_A puis CN_BJ
```

Le code Python, les repositories, les définitions SQL, les migrations paramétrables, le feature engine, les modèles et le backtest restent communs.

Un `DatabaseRouter` applique une allowlist explicite :

```text
US_EQ  → us_primary → alpha_trade
CN_A   → cn_primary → alpha_trade_cn
CN_BJ  → cn_primary → alpha_trade_cn
```

Une incohérence entre marché et base est bloquante. Une requête applicative ne peut pas sélectionner librement un nom de schéma fourni par l’utilisateur.

## Configuration

- `config.yaml` et `batch.yaml` restent US/legacy ;
- `config_cn.yaml` et `batch_cn.yaml` sont les entrées Chine ;
- les autres fichiers propres à la Chine portent le suffixe `_cn` ;
- `config/databases.yaml` reste transversal car il contient le routage ;
- les secrets restent exclusivement en variables d’environnement ou vault.

## Données et artefacts

Les staging fournisseur sont séparés. Les artefacts et sauvegardes utilisent des racines distinctes :

```text
artifacts/models/us_eq
artifacts/models/cn_a
artifacts/backtests/us_eq
artifacts/backtests/cn_a
backups/db/us_eq
backups/db/cn_a
```

Chaque manifest porte aussi `market_code`, `database_alias`, devise, calendrier et fingerprint d’univers. Le chemin seul n’est pas une preuve.

## Motivation

La séparation protège contre un `TRUNCATE`, un nettoyage, une restauration, une migration ou une politique de rétention appliqués au mauvais marché. `market_code` reste obligatoire : la base physique est une seconde barrière, pas un remplacement de l’identité marché.

## Rejeté

- Une branche Git permanente Chine.
- Deux copies divergentes du moteur ML/backtest.
- Une base physique unique reposant uniquement sur la discipline des filtres SQL.
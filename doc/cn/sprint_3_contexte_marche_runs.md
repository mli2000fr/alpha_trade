# Sprint 3 — Contexte marché sur les runs, batches et univers

## Statut

Sprint terminé le 20 septembre 2026. Gate : **GO**.

La migration `0085_market_scope_parents` est appliquée sur la base US. Le backfill a classé 38 batches ML, 9 840 runs ML, 2 779 entrées de registre et 14 537 snapshots d’univers en `US_EQ`. Aucun contexte obligatoire n’est vide et aucune divergence enfant/parent n’a été détectée.

## Objectif fonctionnel

Un symbole seul ne suffit pas à identifier un actif. À partir de ce sprint, chaque objet parent qui lance, sélectionne ou publie un calcul porte son marché. Cette règle empêche notamment :

- un run chinois rattaché à un batch US ;
- la promotion d’un batch US dans le serving CN ;
- le remplacement d’un univers canonique US par un univers CN de même date ;
- la confusion entre deux symboles identiques présents sur deux marchés ;
- la réutilisation silencieuse d’un artefact entraîné avec un autre calendrier ou benchmark.

## Contrat persistant

### Batches ML

`model_training_batch` contient désormais :

- `market_code` : `US_EQ`, `CN_A` ou `CN_BJ` ;
- `calendar_id` : calendrier de sessions utilisé ;
- `base_currency` : monnaie économique du batch ;
- `benchmark_instrument_id` : référence canonique facultative vers `instruments` ;
- `universe_id` : source nominale de l’univers ;
- `universe_fingerprint` : empreinte de marché, source, date et symboles explicites ;
- `sector_taxonomy` : taxonomie sectorielle ;
- `market_context_fingerprint` : empreinte immuable de la configuration marché.

L’index `(market_code, status, started_at)` sert aux diagnostics et à la sélection des campagnes par marché.

### Runs et registre ML

`model_training_run.market_code` hérite du batch parent. Le code refuse une valeur enfant différente. Deux triggers MySQL répètent ce contrôle pour les insertions et mises à jour directes en base. Ils contrôlent aussi la cohérence avec `model_registry`.

La clé logique du registre devient `(market_code, symbol, architecture, version)`. Un ticker identique peut donc exister indépendamment aux États-Unis et en Chine.

### Serving

La clé de `model_serving_batch` devient `(market_code, scope)`. Chaque marché possède sa propre campagne promue. Les appels historiques sans marché continuent de lire `US_EQ` et produisent un avertissement de compatibilité.

### Univers tradables

`tradable_universe_runs` porte le même contexte que les batches ML. La publication d’un nouveau snapshot ne dépublie que le snapshot canonique de même marché, même preset et même date. Toutes les lectures canoniques acceptent désormais un `market_code`; l’absence de code correspond au chemin legacy US avec avertissement.

### Exécution

`execution_runs` porte `market_code`, `calendar_id`, `base_currency` et `market_context_fingerprint`. Une exécution exige un marché activé. Les marchés CN restant désactivés dans Sprint 3, aucune exécution CN réelle ne peut être lancée accidentellement.

## Contrat CLI et artefacts

Model Factory expose `--market-code {US_EQ,CN_A,CN_BJ}` avec `US_EQ` par défaut. Pour une campagne chinoise, le code doit être explicite. Tant que le contexte CN reste désactivé, la CLI bloque le lancement avant tout accès aux données. Le metadata JSON du batch contient un bloc `market_context` et l’empreinte d’univers intègre le marché.

Un lecteur commun accepte encore un ancien manifest dépourvu de `market_context`, le classe comme US legacy et émet un avertissement. Cette tolérance est destinée à la lecture des campagnes existantes, pas à la création de nouveaux batches.

## Migration et SQL

- Alembic : `alembic/versions/0085_market_scope_parents.py` ;
- SQL manuel : `database/sql/migration_0085_market_scope_parents.sql` ;
- DDL frais mis à jour dans `database/sql/ml`, `database/sql/stock` et `database/sql/execution`.

Le backfill utilise le fingerprint US canonique de Sprint 1. Les colonnes `market_code` utilisent explicitement la même collation que `markets.market_code` afin de garantir les clés étrangères MySQL.

## Vérifications réalisées

- 68 tests ciblés réussis ;
- migration appliquée jusqu’à `0085_market_scope_parents` ;
- 100 % des parents historiques classés `US_EQ` ;
- zéro batch avec contexte obligatoire vide ;
- zéro divergence run/batch ;
- zéro divergence run/registre ;
- contrôle statique propre sur les nouveaux fichiers Sprint 3.

## Limites volontaires

Sprint 3 ne rend pas encore les pipelines de données chinois opérationnels. Les tables de marché et le cloisonnement sont prêts, mais l’ingestion CN, les barres, les corporate actions, les fondamentaux et les contrôles PIT appartiennent aux sprints suivants. Le `benchmark_instrument_id` historique reste nullable tant que le référentiel d’instruments n’est pas peuplé ; le symbole benchmark et son fingerprint restent présents dans le manifest.

## Gate vers Sprint 4

Le Sprint 4 peut commencer lorsque la suite complète reste verte. Il devra propager `instrument_id` et `market_code` dans les faits de données sans joindre les actifs critiques uniquement par `symbol`.

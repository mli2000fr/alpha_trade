# Oracle Extreme — labels, univers, calendrier et tables

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Retour : [dossier Oracle](README.md)

## Construction de l’univers

Dans le mode par défaut `static_bars`, `build_labels()` charge les couples `(date, symbol)` de `global_rank_history` pour le batch et l’horizon. Si ces ranks existent, il compare cet ensemble au run synthétique `model_predictions` dont l’id est `<batch_id>_globalrank_synth`.

`check_universe_equality()` publie tailles, écarts et échantillons. Avec `strict_universe=True`, la moindre divergence arrête le run. Avec false, le code utilise l’univers des ranks et journalise l’écart ; ce mode est un outil d’arbitrage, pas une garantie de parité.

Deux fallbacks standalone existent si aucun rank n’est disponible :

- si des symboles sont fournis, l’univers est dérivé de leurs barres sur la fenêtre ;
- sinon, les symboles déjà présents dans les labels du batch sont relus, puis les couples date/symbole viennent des barres.

Ces fallbacks permettent `--oracle-model-only`, mais ils ne sont pas identiques à l’univers historique du Global Ranking. Le summary doit préciser le chemin utilisé.

Deux modes explicites existent aussi : `pit_dynamic_bars` construit une population
quotidienne à partir des barres et exige symboles/bornes ; `stored_membership`
répare les labels en conservant les membres historiques de chaque date. Ce dernier
interdit de restreindre les symboles ; `prediction_dates` est réservé à cette
réparation. Une population dynamique de recherche n'est pas automatiquement
l'univers tradable du serving.

## Prix et rendement futur

La matrice lit `COALESCE(adj_close, close)` dans `stock_bars_daily`, exclut les
barres `is_filled`, ordonne par date/symbole/source et garde le dernier doublon.
Elle est réindexée sur les **séances NYSE**, pas sur les seuls jours présents
dans les prix. Un calendrier indisponible provoque un échec.

Pour une date D et une position `pos` dans l’index :

`future_return_raw = raw_close[D+H] / raw_close[D] - 1`.

Les deux extrémités doivent avoir une vraie barre. Le `ffill` de la vue `close`
sert uniquement à la compatibilité/calendrier : **il ne fabrique pas les targets**.
L'exit date D+H et la disponibilité D+H+1 viennent du calendrier, indépendamment
de la présence d'une barre ce jour-là. Si D+H dépasse la grille de prix observée,
la date est sautée ; si la séance existe mais la barre du symbole manque, une
ligne invalide est conservée avec son motif.

La qualification rejette, dans l'ordre, `missing_start_bar`, `missing_exit_bar`,
`nonpositive_price`, `price_source_mismatch`, `known_security_discontinuity` et
`extreme_unadjusted_price_jump`. Ce dernier contrôle détecte dans le chemin les
ruptures de ratio ≥20 ou ≤1/20 entre observations. Le rendement brut fini reste
auditable, mais `future_return` est NULL si la qualité échoue. Ces contrôles ne
prouvent pas à eux seuls la tradabilité ou toutes les actions sur titres.

## Rang cross-sectionnel

`compute_cross_sectional_ranks()` supprime les rendements non finis puis calcule :

- `oracle_pct_rank = rank(method="max") / n` ;
- `oracle_decile = ceil(percentile × 10)`, borné 1–10 ;
- `oracle_extreme10 = percentile >= 1-top_pct OR percentile <= top_pct`.

Un minimum de 20 rendements finis **et qualifiés** est exigé par date. Sous ce
seuil, les rows restent présentes mais les champs de rang/label sont NULL, même
si `target_quality_valid=1` pour certains titres.

La méthode `rank(method="max")` affecte les égalités. La proportion positive peut dépasser exactement 20 % si beaucoup d’égalités touchent les seuils. Les rapports doivent publier population et taux positif réels.

## Table `global_oracle_labels`

Clé primaire : `prediction_date, symbol, batch_id, horizon`.

| Colonne | Sémantique |
|---|---|
| `prediction_date` | date D |
| `symbol` | symbole dans l’univers |
| `batch_id` | batch source |
| `horizon` | nombre de séances futures |
| `future_return_raw` | rendement brut calculable, même si sa qualité est rejetée |
| `future_return` | rendement réalisé qualifié, sinon NULL ; fraction, pas pourcentage |
| `target_quality_valid` | qualification des prix/du chemin |
| `target_quality_reason` | premier motif d'invalidation |
| `price_start_source`, `price_end_source` | provenance des deux extrémités |
| `oracle_pct_rank` | percentile futur intra-date |
| `oracle_decile` | décile futur |
| `oracle_extreme10` | appartenance à une queue |
| `oracle_exit_date` | séance D+H |
| `oracle_available_date` | première date d’usage du label |
| `created_at` | écriture DB |

Les index couvrent batch/date et available date. L’upsert remplace les valeurs calculées pour une même clé et met à jour `created_at`.

Ce builder est US : son SQL écrit `alpha_trade.global_oracle_labels`. Il ne faut
pas le lancer pour CN/FR en supposant une adaptation automatique du schéma.

## Persistance incrémentale

Les écritures SQL sont chunkées par 2 000 rows. La boucle flush les rows accumulées à partir de 5 000 afin qu’une interruption ne perde pas tout le calcul. Chaque flush appelle d’abord l’assertion de disponibilité.

Le run peut donc laisser un préfixe cohérent mais partiel. Le summary contient rows, labeled, unavailable, skipped dates, symboles, `n_quality_invalid` et `quality_reasons`. Une reprise est idempotente grâce à la clé primaire et à `ON DUPLICATE KEY UPDATE`.

En dry-run, aucune écriture **SQL** n'est réalisée et le summary porte
`status=dry_run`. Un export Parquet demandé peut écrire un fichier local.
La validation T1 est exécutée sur les rows en mémoire ; pas de flush SQL intermédiaire.

## Table `oracle_extreme_predictions`

Clé primaire : `prediction_date, symbol, batch_id`. Elle contient :

- `proba_extreme` obligatoire ;
- `future_return` et `oracle_extreme10` optionnels ;
- `fold_start` pour rattacher le champion ;
- batch et timestamp.

Cette table cumule les campagnes. Une lecture sans batch mélangerait des modèles incompatibles ; le loader refuse donc par défaut un batch vide.

## États d’erreur

| Raison/statut | Interprétation |
|---|---|
| exception strict universe | ranks et predictions divergent |
| `empty_universe` | aucun couple date/symbole |
| `empty_window` | bornes hors univers |
| `no_bars` | matrice de prix vide |
| rows unavailable | prix futur ou rang absent |
| skipped dates | date de l’univers absente de la matrice |

## Contrôles après build

1. Comparer tailles ranks/predictions.
2. Vérifier nombre de symboles par date.
3. Mesurer valeurs nulles et taux positif.
4. Vérifier `exit_date > prediction_date`.
5. Vérifier `available_date > prediction_date`.
6. Inspecter fin de série, barres absentes et motifs de qualification ; ne jamais utiliser la vue ffill pour réparer une target.
7. Relancer une plage et confirmer idempotence.
8. Rapprocher le batch et l’horizon des consumers.

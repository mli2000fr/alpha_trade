# Snapshots analystes Yahoo Finance — contrat PIT de recherche

## Objectif et périmètre

Le batch `analyst_snapshot_collection` construit à partir de sa date d'activation
un historique prospectif des informations analystes observées sur
`config/univers_batch/univers_filtred_tradable.txt`. Il ne reconstruit pas
rétroactivement un historique qu'il n'a pas observé.

Yahoo Finance est interrogé via la bibliothèque non officielle `yfinance`.
Cette source ne fournit aucun SLA et est utilisée exclusivement pour la recherche
personnelle et éducative. Les données ne constituent pas un flux de production
licencié et ne doivent pas être redistribuées.

## Familles collectées

| Objet yfinance | Information | Table |
|---|---|---|
| `earnings_estimate` | consensus EPS moyen/bas/haut, croissance, nombre d'analystes | `stock_analyst_estimate_history` |
| `revenue_estimate` | consensus chiffre d'affaires moyen/bas/haut, croissance, nombre d'analystes | `stock_analyst_estimate_history` |
| `eps_trend` | consensus courant et valeurs 7/30/60/90 jours auparavant | `stock_analyst_eps_trend_history` |
| `eps_revisions` | nombres de révisions positives/négatives à 7 et 30 jours | `stock_analyst_eps_revision_history` |
| `analyst_price_targets` | cours et objectifs bas/moyen/médian/haut | `stock_analyst_target_history` |
| `recommendations` | strong buy/buy/hold/sell/strong sell par bucket Yahoo | `stock_analyst_recommendation_history` |

Chaque run est résumé dans `analyst_snapshot_collection_run`, avec une couverture
distincte pour EPS, Revenue, EPS trend, EPS revisions, targets et recommandations.

## Causalité et périodes relatives

`observed_at` est l'heure UTC réelle de lecture. `available_at` est la prochaine
séance de décision calculée par l'application : une donnée observée après la
clôture n'est jamais rendue disponible rétroactivement.

Yahoo identifie généralement les horizons par `0q`, `+1q`, `0y` et `+1y`, sans
garantir une date de fin fiscale. Le stockage conserve donc `horizon_raw`, sa
normalisation et `relative_horizon_only=true`. Une variation entre deux snapshots
ne doit pas être interprétée comme une révision lorsque la publication des comptes
a fait basculer `0q` vers le trimestre suivant.

## Idempotence et reprise

Les tables sont append-only entre les dates et uniques par fournisseur, symbole,
date de snapshot et horizon. Rejouer la collecte le même jour ne crée pas de
doublon. Le launcher utilise la reprise afin que le second horaire quotidien
complète un premier passage manqué ou incomplet sans réécrire les symboles déjà
présents.

## Features de recherche attendues

Les données brutes permettent notamment de construire, après contrôle du rollover :

```text
revision_7d_pct       = (current - value_7d_ago) / abs(value_7d_ago)
revision_30d_pct      = (current - value_30d_ago) / abs(value_30d_ago)
revision_breadth_7d   = (up_7d - down_7d) / (up_7d + down_7d)
revision_breadth_30d  = (up_30d - down_30d) / (up_30d + down_30d)
revision_acceleration = revision_breadth_7d - revision_breadth_30d
```

Une valeur manquante reste `NULL`; elle n'est jamais convertie en zéro. Ces
features demeurent hors production jusqu'à validation OOF/WF et ablation.

## Exploitation

La configuration active se trouve dans `batch.yaml`. La page **Workflow &
Orchestration → Batch** affiche le calendrier, les tables, le dernier run et
l'avertissement de recherche. La migration `0077_yahoo_analyst_trends` doit être
appliquée avant le premier passage utilisant les deux nouvelles familles.

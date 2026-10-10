# Snapshots analystes Yahoo Finance — contrat PIT de recherche

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Objectif et périmètre

### État actuel — nouvelle désactivation le 10 octobre 2026

L'utilisateur a de nouveau désactivé `analyst_snapshot_collection` US.
Configuration vérifiée : `enabled: false`, statut
`BLOCKED_YAHOO_AUTOMATED_ACCESS`. Aucun nouveau téléchargement Yahoo,
y compris manuel, tant que ce blocage est présent. La tâche installée peut
rester en place : le launcher vérifie ces paramètres avant les appels.
Le statut bloqué ne serait pas levé par le seul passage de `enabled` à `true`.

Aucune purge demandée : les données actuelles et les six tables restaurées
depuis la sauvegarde du 4 octobre sont conservées, ainsi que les résultats
exploratoires. Leurs réserves de droits et de qualification restent applicables.
EODHD Calendar & News est envisagé pour une collecte prospective de remplacement,
mais aucun nouvel abonnement ou batch de remplacement n'est confirmé ici.
[Restauration et analyse](analyst_archive_restore_directional_20261010.md).

### Historique — réactivation temporaire puis retrait de la borne automatique

Le batch US avait été réactivé le **10 octobre 2026**, sans expiration automatique.
`batch.yaml` portait alors `ACTIVE_RESEARCH_RIGHTS_UNCONFIRMED` et `enabled: true`,
sans `trial_start_date` ni `trial_end_date_exclusive`.
À la demande de l'utilisateur, l'arrêt des nouveaux appels prévu le 10 novembre
avait été retiré ; cette réactivation est désormais remplacée par la désactivation ci-dessus.
La tâche existante lit cette configuration à chaque passage ; aucune réinstallation
n'est nécessaire pour supprimer cette borne.

**Permission Yahoo non confirmée.** Le GO de l'utilisateur autorise la
réactivation dans Alpha Trade, mais n'est pas une permission du fournisseur.
Les restrictions contractuelles documentées dans
[l'audit de droits](audit_autorisations_collectes_us_20261006.md) ne sont pas levées.
Pas de redistribution ni de promotion automatique des données vers ML/LIVE.
Les collectes Yahoo FR, FRED et FINRA restent bloquées.

Configuration conservée mais inactive : univers `config/univers_batch/univers_filtred_tradable.txt`. Passage principal
à **22 h Paris**, secours conditionnel à **4 h Paris** avec contrôle de succès
récent, `--resume` et stockage quotidien idempotent existants. Les notifications
email/Telegram restent celles du launcher ; un appel Python direct ne les envoie pas.
Après un mois : couverture par famille, nombre de vraies révisions (pas simplement
nombre de snapshots), contrôles de rollover fiscal, rendement H3/H5/H10 à maturité.
H20 exige vingt séances futures après chaque observation : un bilan après un mois
ne permettra pas d'évaluer les derniers snapshots à H20. Aucun bénéfice directionnel
n'est présumé, aucun entraînement/backtest automatique n'est ajouté.

Installation/réinstallation (référence technique uniquement ; ne lève pas le blocage) :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File F:\projets\scripts\windows\install_analyst_snapshot_task.ps1
```

Suivi : page **Workflow & Orchestration → Batch → US**, table
`analyst_snapshot_collection_run` et log `F:\projets\log\batch\analyst_snapshots.txt`.
Arrêt manuel : `enabled: false`. Le bilan conseillé après un mois ne déclenche aucun arrêt.

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

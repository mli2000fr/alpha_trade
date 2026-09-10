# 6 — Sélection des bons candidats per-symbol par direction

## Objectif

La page **Diagnostic ML** permet de construire, pour un batch ternaire contenant
des modèles per-symbol, un univers réduit de symboles dont la capacité
directionnelle est suffisamment stable en walk-forward.

Cette sélection répond au cas d'usage suivant :

```text
Oracle Extreme                     modèle per-symbol
détecte une amplitude probable  →  estime le côté LONG ou SHORT
```

Un symbole n'a pas besoin d'être bon dans les deux directions. L'éligibilité est
évaluée indépendamment pour LONG et SHORT. Un symbole peut donc être conservé
pour LONG uniquement, SHORT uniquement, ou pour les deux côtés.

## Accès dans l'IHM

1. Ouvrir **Diagnostic ML**.
2. Sélectionner un batch ternaire contenant des artefacts per-symbol.
3. Dans **Per-Symbol / Per-Sector — Métriques**, ouvrir le bloc
   **Bons candidats per-symbol par direction**.
4. Cliquer sur **Préparer la sélection**.
5. Vérifier les compteurs et les trois tableaux LONG uniquement, SHORT
   uniquement et LONG+SHORT.
6. Cliquer sur **Télécharger les bons candidats (.txt)**.

Le calcul n'est pas lancé automatiquement au chargement de la page. Un batch
peut contenir des milliers de fichiers `metrics.json`; leur relecture à chaque
interaction Streamlit dégraderait fortement la page.

Si le batch est encore `running`, le résultat est un snapshot des symboles déjà
matérialisés. Le bouton **Actualiser la sélection** recalcule le snapshot.

Le répertoire d'artefacts n'est pas supposé être toujours `artifacts/models`.
La page résout d'abord le `--artifacts-dir` conservé dans `metadata_json`, puis
utilise une découverte bornée sous `artifacts/*` pour les anciens batches.

## Périmètre exact évalué

Pour chaque symbole ordinaire du répertoire du batch :

1. `config.json` détermine le modèle champion effectivement sélectionné ;
2. `selected_forecast_horizon` détermine l'horizon retenu ;
3. `metrics.json` fournit le walk-forward correspondant à ce couple
   champion/horizon ;
4. les folds de ce seul chemin sont évalués.

Le sélecteur d'horizon général de la page Diagnostic ML ne modifie pas cette
sélection. Cela évite de choisir a posteriori le meilleur horizon visible dans le
tableau. Pour LightGBM et CatBoost, les chemins attendus sont respectivement :

```text
baseline_lightgbm.horizons.h<selected>.walk_forward
baseline_catboost.horizons.h<selected>.walk_forward
```

Pour le LSTM, le payload walk-forward du champion est lu depuis le chemin
canonique enregistré dans `metrics.json`.

Les dossiers techniques commençant par `_`, par exemple `__GLOBAL__` ou les
caches mutualisés, sont exclus.

## Validité d'un fold pour un côté

Un fold LONG ou SHORT est valide si :

```text
F1 du côté disponible
ET support réel du côté >= 15 observations
```

Le support explicite est utilisé lorsqu'il existe. Sinon il est estimé sans
information future supplémentaire :

```text
support_side = round(test_rows × true_side_pct / 100)
```

Un excellent F1 obtenu sur quelques observations n'est donc pas considéré comme
une preuve suffisante.

## Deux niveaux de sélection

La page propose un sélecteur local **Niveau de sélection**. Il ne modifie ni
`config.yaml`, ni le batch, ni les artefacts : il change uniquement la vue des
candidats dans Diagnostic ML.

Les deux niveaux sont indépendants : DISCOVERY n'est pas nécessairement un
sur-ensemble de STRICT, car il supprime le minimum bloquant mais relève la
médiane exigée de 0,40 à 0,45. Un symbole très régulier entre 0,40 et 0,45 peut
donc être STRICT sans être HIGH POTENTIAL.

### STRICT / STABLE

LONG et SHORT utilisent exactement les mêmes gates :

| Gate | Condition |
|---|---:|
| Folds valides | `>= 3` |
| Support réel | `>= 15` par fold valide |
| F1 médian | `>= 0.40` |
| F1 minimum | `>= 0.20` |
| Fold passant | `F1 >= 0.35` |
| Taux de folds passants | `>= 60 %` |

Le minimum à `0.20` empêche qu'une moyenne élevée masque un effondrement sur un
régime. Le taux de passage demande que la performance ne soit pas concentrée
sur un seul fold.

Ces seuils sont des gates d'ingénierie et non une preuve de rentabilité. Le F1
doit toujours être confronté au taux d'action, à la calibration et au backtest
OOS de la cascade.

### DISCOVERY / HIGH POTENTIAL

Ce niveau sert à construire l'univers d'un prochain entraînement approfondi. Il
privilégie une performance directionnelle centrale élevée sans éliminer un
symbole à cause d'un seul régime défavorable :

| Gate | Condition |
|---|---:|
| Folds valides | `>= 3` |
| Support réel | `>= 15` par fold valide |
| F1 directionnel médian | `>= 0.45` |
| Fold passant | `f1_side >= 0.35` |
| Taux de folds passants | `>= 60 %` |
| F1 minimum | non bloquant ; alerte si `< 0.20` |

`f1_side` signifie exclusivement `f1_long` pour une candidature LONG et
`f1_short` pour une candidature SHORT. `f1_macro` ne participe à aucun des deux
niveaux.

## Classification exclusive

Après évaluation indépendante des deux côtés, le symbole reçoit exactement une
classe :

| Classe | LONG stable | SHORT stable | Présence dans le fichier |
|---|---:|---:|---|
| `LONG_ONLY` | oui | non | liste LONG_ONLY |
| `SHORT_ONLY` | non | oui | liste SHORT_ONLY |
| `LONG_SHORT` | oui | oui | liste LONG_SHORT |
| `REJECTED` | non | non | aucune liste |

Les listes sont exclusives. Un symbole `LONG_SHORT` n'est pas dupliqué dans
`LONG_ONLY` ou `SHORT_ONLY`.

## Pourquoi `f1_macro` et `f1_flat` ne sont pas des gates

En mode ternaire :

```text
f1_macro = moyenne(f1_short, f1_flat, f1_long)
```

Dans la cascade Oracle, le modèle per-symbol sert surtout à départager LONG et
SHORT après détection d'une amplitude extrême. Un bon modèle directionnel peut
avoir un `f1_flat` faible et rester utile. Inversement, un bon `f1_macro` peut
masquer un côté SHORT ou LONG inutilisable.

`f1_macro` et `f1_flat` restent des diagnostics, mais ne décident pas de
l'éligibilité directionnelle.

## Format du fichier

Le téléchargement UTF-8 contient trois sections et des symboles séparés par une
virgule sans espace :

```text
[LONG_ONLY]
AAPL,MSFT

[SHORT_ONLY]
XYZ

[LONG_SHORT]
AMD,NVDA
```

Les commentaires d'en-tête enregistrent le batch, l'heure UTC de génération et
les seuils employés. Les sections historiques `[LONG_ONLY]`, `[SHORT_ONLY]` et
`[LONG_SHORT]` restent les listes STRICT pour préserver le contrat existant. Le
fichier ajoute :

```text
[DISCOVERY_LONG_ONLY]
[DISCOVERY_SHORT_ONLY]
[DISCOVERY_LONG_SHORT]
```

Une section sans candidat reste présente avec une ligne vide. Le téléchargement
contient toujours les deux niveaux, quel que soit le niveau actuellement affiché
dans la page.

L'union utilisable pour constituer l'univers de l'entraînement final est :

```text
LONG_ONLY ∪ SHORT_ONLY ∪ LONG_SHORT
```

## Audit disponible dans la page

Trois onglets présentent les listes exclusives directement dans l'écran. Les
tableaux LONG et SHORT sont triés par F1 médian du côté concerné, puis par F1
minimum et nombre de folds valides. Le tableau LONG+SHORT est trié par son
`directional_f1_floor`, défini comme :

```text
directional_f1_floor = min(median_f1_long, median_f1_short)
```

Cette priorité empêche qu'un côté excellent masque un second côté simplement
acceptable. Les tableaux affichent notamment :

- symbole, champion et horizon sélectionnés ;
- classification directionnelle ;
- nombre de folds valides de chaque côté ;
- médiane, minimum, dispersion et taux de passage F1 de chaque côté ;
- support réel cumulé utilisé par côté.

Le service conserve également dans son DataFrame d'audit la dispersion F1, le
support total, la source du payload et les raisons compactes de rejet.

## Limites et contrat d'utilisation

Le téléchargement sélectionne un **univers candidat pour réentraînement**. Il
ne modifie aucun batch, artefact, modèle servi ou table SQL.

Le fichier n'est pas automatiquement consommé par le prédicteur ou le backtest.
Si un symbole `LONG_ONLY` est ensuite tradé en SHORT, la sélection perd son sens.
Une évolution distincte doit persister et appliquer les droits
`eligible_long`/`eligible_short` lors de la prédiction ou du gate de backtest.

Après l'entraînement final, les gates doivent être recalculés sur les nouveaux
artefacts : une éligibilité obtenue pendant le screening n'est pas définitive.

Enfin, sélectionner les meilleurs résultats parmi des milliers de symboles crée
un biais de sélection multiple. Une confirmation sur une période temporelle
totalement hors sélection reste requise avant une utilisation en production.

## Sources de vérité

- `ihm/services/ml_artifacts.py` : résolution champion/horizon, stabilité et format ;
- `ihm/pages/ml_diagnostics.py` : préparation, aperçu et téléchargement ;
- `modelFactory/tabular_baseline.py` : métriques walk-forward tabulaires ;
- `modelFactory/trainer.py` : walk-forward LSTM et orchestration multi-horizon ;
- `modelFactory/db_registry.py` : persistance des métriques agrégées et complètes.

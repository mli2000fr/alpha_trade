# Trajectoire tick de prix, spread et liquidité après Oracle

## Statut

**Découverte et confirmation terminées — piste `NO_GO`.**

Cette expérience réutilise les ticks du run
`signed-flow-temporal-20260907234204-0e94ac` sans nouvel appel API. Elle est
distincte de la famille signed-flow : aucun côté agresseur et aucun déséquilibre
bid/ask n'entre dans ses features.

Code : `modelFactory/directional_data_research/tick_price_liquidity_audit.py`.

Artefact :
`artifacts/research/eroya_directional/tick-price-liquidity-20260907235552/`.

## Contrat

Population : 200 événements Oracle OOF sélectionnés sans outcome, dont 182
séquences complètes et 159 tails H20. Les labels corrigés sont joints après la
construction des features.

Features directionnelles à signe préfixé momentum positif :

- rendement tick sur 30 minutes ;
- rendement tick sur 5 minutes ;
- dernier prix contre VWAP 30 minutes ;
- position de clôture dans le range 30 minutes.

Features d'amplitude à signe positif préfixé :

- volatilité réalisée 30 minutes ;
- range haut-bas 30 minutes ;
- spread NBBO médian en bps ;
- logarithme du nombre de trades ;
- logarithme du nombre de quotes.

Les neuf tests partagent une correction Bonferroni. Chaque signal exige N,
AUC, corrélation, stabilité sur au moins 70 % des semestres et p-value corrigée
inférieure à 0,05.

## Résultats directionnels

| Feature | AUC D1/D10 | Spearman rendement | Semestres AUC > 0,50 | p corrigée | Verdict |
|---|---:|---:|---:|---:|---|
| rendement 30 min | 0,46 | -0,09 | 3/7 | 1,00 | `NO_GO` |
| position dans le range | 0,45 | -0,11 | 3/7 | 1,00 | `NO_GO` |
| clôture contre VWAP | 0,45 | -0,13 | 3/7 | 1,00 | `NO_GO` |
| rendement 5 min | 0,43 | -0,16 | 2/7 | 1,00 | `NO_GO` momentum |

Le momentum attendu est rejeté. Les quatre signes négatifs suggèrent toutefois
une lecture d'épuisement/retournement : une faiblesse très tardive précéderait
plus souvent un tail LONG. Cette lecture est **postérieure au résultat** et ne
peut pas être validée sur ces 200 événements en inversant simplement le score.

## Résultats amplitude

| Feature | AUC extrême | Spearman amplitude | Semestres AUC > 0,50 | p corrigée | Verdict |
|---|---:|---:|---:|---:|---|
| volatilité réalisée | 0,55 | +0,08 | 5/7 | 1,00 | `NO_GO` |
| nombre de trades | 0,55 | +0,18 | 5/7 | 1,00 | `NO_GO` |
| nombre de quotes | 0,54 | +0,14 | 3/7 | 1,00 | `NO_GO` |
| spread médian | 0,49 | -0,07 | 4/7 | 1,00 | `NO_GO` |
| range 30 min | 0,47 | 0,00 | 4/7 | 1,00 | `NO_GO` |

La volatilité et l'activité ont le sens économique attendu mais leur preuve est
insuffisante et non significative après multiplicité. Elles ne doivent pas être
ajoutées à l'Oracle sur cet échantillon.

## Confirmation disjointe de l'épuisement

Une confirmation disjointe a ensuite été exécutée pour **une seule hypothèse
primaire** :

```text
score exhaustion H20 = - rendement des 5 dernières minutes
```

Le sens contrariant a été fixé avant la nouvelle collecte. Toutes les dates
déjà vues ont été exclues, ce qui est plus strict qu'une exclusion des seuls
couples date/symbole. Une seule observation Oracle a été tirée par nouvelle
date via un hash déterministe.

Artefact valide :
`artifacts/research/eroya_directional/close-exhaustion-confirm-20260908000547-0e94ac/`.

| Mesure | Résultat | Gate |
|---|---:|---:|
| dates sélectionnées | 400 | disjointes de la découverte |
| observations avec label | 375 | — |
| tails H20 | 319 | >= 300 : passé |
| AUC du score `-return_5m` | **0,490** | >= 0,53 : échec |
| Spearman avec rendement futur | **+0,005** | >= 0,03 : échec |
| p-value unilatérale | **0,627** | < 0,05 : échec |
| semestres AUC > 0,50 | **4/7 = 57 %** | >= 70 % : échec |

Les AUC semestrielles sont 0,40, 0,52, 0,42, 0,52, 0,49, 0,56 et 0,51 de
2022H1 à 2025H1. Aucun sous-régime stable ne justifie une réouverture.

### Incident de sélection détecté avant résultat

Une première tentative, dossier
`close-exhaustion-confirm-20260908000135-0e94ac`, a été interrompue à 120/400.
La règle « une observation par date » retenait alors le ticker
alphabétiquement premier, ce qui concentrait artificiellement la collecte sur
`AA`. Le run n'a créé aucun `report.json`, n'a produit aucune métrique et ne
constitue pas un artefact valide.

Le correctif choisit le symbole intra-date par hash `date|symbol`. Son contrôle
avant relance donne 400 dates, 124 symboles et au maximum dix observations par
symbole. Un test unitaire empêche le retour à l'ordre alphabétique.

## Décision finale

L'inversion contrariante du premier échantillon ne se réplique pas. Fermer :

- momentum tick direct ;
- score d'épuisement `-return_5m` ;
- signed-flow simple et accéléré ;
- ajout immédiat de volatilité, activité ou spread à l'Oracle.

Aucune feature, aucun modèle, aucun seuil et aucune table applicative ne sont
modifiés. Une nouvelle expérience microstructure devra apporter une donnée
distincte et une hypothèse enregistrée avant lecture des outcomes ; redécouper
encore les mêmes trente minutes serait du data mining.

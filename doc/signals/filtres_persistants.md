# Filtres persistants de rang et de prix

## Objet

Les filtres persistants exigent qu’un état survive plusieurs observations avant
d’autoriser un candidat. Ils cherchent à distinguer un signal durable d’un pic,
ou à attendre un dip/reclaim après un classement élevé.

## Dimensions du contrat

- horizon de rang ;
- seuil d’entrée dans la population top/tail ;
- nombre de jours de persistance ;
- amplitude de baisse/dip ;
- ratio de reclaim et attente maximale ;
- comportement si une observation manque ;
- disponibilité PIT des rangs/prix.

Le Persistent Rank DIP possède des paramètres backtest dédiés dans la
configuration et l’IHM. Ils ne doivent pas être supposés identiques au live.

## Machine d’état conceptuelle

```text
hors population → candidat persistant → dip observé → reclaim éventuel → éligible
       ↑                 |                    |
       └──── reset si seuil/persistance rompue┘
```

La formule exécutable et l’ordre quotidien font foi. Le backtest doit reproduire
les transitions sans regarder les jours futurs.

## Validation

Mesurer fréquence, délai, turnover, trades filtrés, coût d’opportunité et
stabilité par période. Comparer à la baseline sans filtre avec le même contrat
d’exécution. Voir [expériences filtres](../experiences/filtres_et_direction.md)
et [recherche persistent dip](../research/persistent_dip.md).


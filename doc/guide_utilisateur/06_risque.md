# Page Risk — décisions, contraintes et portefeuille cible

## Rôle

Le moteur de risque transforme les intentions issues du ranking/screener en
décisions et cibles compatibles avec les contraintes. La page est une vue
d’audit de ce calcul. Elle ne doit pas être utilisée pour inférer un ordre déjà
envoyé.

## Sélectionner le bon run

Toujours sélectionner explicitement le run lié au pipeline et au batch analysés.
Deux runs proches peuvent partager une date tout en différant par capital,
positions initiales, compte, gates ou configuration. Le run est l’unité d’audit.

## Décisions de risque

Chaque ligne doit être lue comme une transformation : intention initiale,
décision, taille finale et motifs. Les trois issues principales sont :

- acceptation : la cible reste admissible, éventuellement après calcul de taille ;
- réduction : le trade subsiste mais une ou plusieurs contraintes plafonnent la
  taille ;
- rejet : aucune cible d’entrée n’est transmise pour cette intention.

Le bloc de synthèse sectorielle permet de voir une contrainte de concentration
qui ne serait pas évidente ligne par ligne. Le bloc des motifs agrège rejets et
réductions ; revenir aux lignes pour comprendre ordre et cumul des règles.

## Gates et alertes

Une alerte informe ; un gate modifie la décision. Selon la règle, un contexte
peut conduire au cash-only, à une réduction, à un blocage ou à une autre
politique. Lire la conséquence persistée plutôt que déduire le comportement du
libellé de l’alerte.

Le régime de marché est une entrée potentielle du risque, mais sa page dédiée ne
remplace pas le résultat effectivement appliqué au run.

## Portefeuille cible

Le portefeuille cible est l’état souhaité après application des règles. Les
quantités doivent être interprétées relativement aux positions initiales et au
capital du run. L’exécution calcule ensuite les différences et subit les
contraintes broker, prix, fractionnement et fills.

Contrôles : exposition brute/net, cash, poids unitaires, secteurs, nombre de
positions, sens, contraintes de compte et cohérence avec les décisions.

## Shadow compare

Le mode shadow compare confronte une politique de référence et une politique
alternative sans assimiler l’alternative à une décision live. Comparer la
population commune, les motifs, les tailles et les impacts agrégés. Une
différence est un objet de diagnostic, pas automatiquement une amélioration.

## Post-mortem

Le post-mortem explique a posteriori la distribution des décisions et certains
effets du run. Il doit rester causalement séparé de la décision prise : ne pas
réécrire le motif initial avec une information future.

## Escalade

Bloquer le passage à l’exécution si le run ne correspond pas au contexte, si les
positions initiales sont incohérentes, si un gate critique n’est pas compris, si
le portefeuille cible viole une contrainte attendue ou si les motifs ne
permettent pas de reproduire la transformation.

Voir [Gestion du risque](../09_risque_et_portefeuille.md) et les documents spécialisés
du [module risque](../risk/README.md).

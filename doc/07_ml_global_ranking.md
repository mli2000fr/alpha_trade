# ML — Global Ranking

> Point d'entrée détaillé :
> [dossier technique Global Ranking](ml/global_ranking/README.md).

## Finalité

`modelFactory/global_ranking.py` classe les titres entre eux à une date donnée. Il remplace le classifieur global ternaire historique pour le stacking/ranking. Sa question est relative : « quels titres sont les meilleurs dans l'univers du jour ? »

## Contrat

- horizons indépendants : H3, H5, H10, H15 et H20 ;
- cible principale : rendement futur excédentaire vs SPY, transformé en vingtile 0 à 19 ;
- groupes de ranking : date de trading ;
- modèle principal : LightGBM LambdaRank ;
- fallback : CatBoost RMSE sur rang continu [0,1] ;
- sortie : percentile cross-sectionnel `global_rank_H` dans [0,1] ;
- métrique centrale : IC de rang de Spearman, pas F1.

## Préparation

Les features sont calculées par symbole puis concaténées. La cible future est décalée à l'intérieur de chaque symbole, ce qui empêche une contamination entre titres. Les features cross-sectionnelles transforment momentum, volatilité, RSI, distances aux moyennes, volume, gaps et autres variables en rangs du jour.

Les neutralisations sectorielles soustraient la médiane du secteur. Pour certaines fondamentales, le code utilise un z-score robuste basé sur la médiane et la MAD, borné pour limiter les outliers.

## Exclusions

Les variables globales identiques pour tous les titres à une date (certaines séries SPY/VIX/MOVE/régime) sont blacklistées du ranking : elles peuvent expliquer le marché dans le temps, mais pas ordonner des symboles le même jour. Le sentiment est également exclu du ranking global par défaut dans ce chemin, car sparse et traité ailleurs.

## Walk-forward

Chaque fold entraîne uniquement sur le passé et prédit une fenêtre future. Les prédictions OOS sont persistées avec batch, horizon, date, symbole et rang. La qualité doit être examinée par fold, période, régime, décile et stabilité des top picks, pas uniquement par moyenne globale.

## Synthèse production

Le batch configuré et `live_horizon` déterminent le rang utilisé pour synthétiser les prédictions consommables. Pour les configurations historiques B25, H20 peut être gelé même si la metadata du batch indique un autre « best horizon ». Ce choix explicite empêche qu'une réévaluation change silencieusement le contrat live.

## Diagnostics recommandés

- IC quotidien médian et distribution ;
- gradient de rendement par quantile ;
- stabilité des top N ;
- couverture de l'univers et biais sectoriel ;
- performance par période et régime ;
- comparaison contre ranking aléatoire, momentum simple et baseline ;
- sensibilité aux coûts et à la capacité ;
- reproductibilité seed/fingerprint.

## Erreurs d'interprétation

- un rang élevé n'est pas une probabilité de gain ;
- un bon IC ne garantit pas qu'un portefeuille concentré reste rentable après coûts ;
- un rang OOS ne peut être reconstruit avec l'univers futur complet ;
- l'horizon du ranking n'est pas nécessairement la durée exacte de détention ;
- Global Ranking et Oracle Extreme répondent à deux questions différentes.

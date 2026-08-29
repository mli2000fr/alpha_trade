# 2 — Univers, données et features

## Construction de l’univers

`train_global_ranking_wf` reçoit une liste de symboles, résout la dernière date
de barres et la profondeur d’entraînement, puis charge l’univers en une table
commune. La configuration peut plafonner le nombre de symboles via
`global_ranking_max_symbols`.

Deux modes de plafonnement existent :

- sélection par liquidité moyenne ;
- sélection stratifiée par déciles lorsque
  `global_ranking_selection_stratified` est active.

Le groupe sectoriel peut ensuite filtrer l’univers sur `all`, `cyclical` ou
`defensive`. Le mapping repose sur des mots-clés de secteurs GICS ; les valeurs
non reconnues tombent dans `other` et ne rejoignent pas automatiquement les
deux groupes spécialisés.

## Filtre de liquidité dans chaque fold

Un premier plafonnement global ne suffit pas pour garantir la disponibilité
historique. Dans chaque fold, le code recalcule l’éligibilité à partir du nombre
de séances train et du volume moyen observé dans la partie train. Le minimum de
séances vaut le maximum entre la moitié du `min_train_size` et 60. Le seuil de
volume vient de la configuration, avec fallback interne lorsque l’attribut
n’existe pas.

Ce calcul dans le train évite d’utiliser la liquidité future pour décider qu’un
symbole était éligible. Le code journalise les symboles exclus et avertit si
moins de la moitié de l’univers subsiste dans un fold suffisamment large.

## Familles de features

Le modèle part des features produites par `compute_features`, enrichies par
`build_cross_sectional_features` et leur fusion. Le contrat peut inclure :

- OHLCV, rendements, momentum, volatilité et indicateurs techniques ;
- rangs cross-sectionnels des features brutes ;
- signaux sectoriels et sector-neutral ;
- z-scores fondamentaux par secteur, robustes via médiane/MAD et bornés à ±5 ;
- screener, short score, sentiment, fondamentaux, facteurs et volume selon les
  flags du dataset ;
- benchmark et features relatives ;
- sous-ensemble directionnel lorsque ce mode est demandé.

Les commentaires d’en-tête anciens disent que les macros globales sont
blacklistées. Le comportement exact doit être lu dans
`_get_ranking_feature_columns`, car il tient compte des flags et des familles
actuelles. Les métadonnées sauvegardent les `include_*` nécessaires pour
reproduire l’inférence.

## Rangs cross-sectionnels de features

Une liste dédiée `_XS_RANK_SOURCE_FEATURES` contient momentum multi-horizons,
volatilités, RSI, distances aux moyennes, mean-reversion, rendements, volume,
range/gap/VWAP et dynamiques temporelles. Pour chaque date :

```text
source feature → percentile intra-date → <source>_xs_rank
```

Certaines forces relatives ne reçoivent pas un second rang lorsque leur rang
serait exactement identique à celui du momentum source. Cette suppression évite
des doublons parfaits.

## Neutralisation sectorielle des features

Pour les sources éligibles, la médiane du secteur à la date est soustraite. Sans
mapping secteur, la valeur neutre est utilisée selon le chemin. Pour les
fondamentales sectorielles, le code calcule `(x - médiane) / MAD`, protège une
MAD trop petite et borne le résultat.

## Valeurs manquantes et parité

Lors de la prédiction, une feature absente est créée à `0.5` si son nom ressemble
à un rang, sinon à `0.0`. C’est un mécanisme de continuité, pas une preuve de
qualité. Le manifeste et les logs d’audit permettent de mesurer ces situations.

Le benchmark est rechargé à l’inférence si nécessaire afin d’éviter que les
features relatives deviennent silencieusement nulles. Cette étape est
essentielle à la parité entraînement/prédiction.

## Contrôles recommandés

- effectif par date et fold ;
- secteurs manquants ou classés `other` ;
- distribution des `_xs_rank` et proportion exacte à `0.5` ;
- features constantes ou dupliquées ;
- présence du benchmark sur toute la fenêtre ;
- couverture de chaque famille `include_*` ;
- concordance de l’ordre de features avec le manifeste.


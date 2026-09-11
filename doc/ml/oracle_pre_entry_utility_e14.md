# E14 — Cible économique pré-entrée après Oracle

## Statut

`FAIT_NO_GO_OR_BLOCKED` — les modèles détectent une faible information
économique OOF, mais aucune politique ne produit un lift portefeuille robuste et
statistiquement significatif. Aucun changement du serving, du backtest ou du
live n'est autorisé.

Artefact canonique :
`artifacts/research/oracle_pre_entry_utility/oracle-pre-entry-utility-20260911162146`.

## Question de recherche

E13 prédisait correctement le motif `trailing_stop`, sans améliorer le PnL.
E14 remplace ce label mécanique par deux cibles directement économiques :

1. rendement net PROD attendu après commissions et slippage ;
2. probabilité que ce rendement net soit négatif.

```text
Oracle TOP20 OOF
  -> variables pré-entrée
  -> tête régression : E[rendement net PROD]
  -> tête classification : P(perte nette)
  -> veto économique ou reranking
  -> capacité 8 et lifecycle PROD inchangés
```

L'objectif primaire pré-enregistré est un veto des 20 % de plus faible utilité
prévue, suivi du classement Oracle original. Les veto 10/30 %, le reranking
utilité, le reranking faible probabilité de perte et l'hybride égalitaire
Oracle/utilité sont diagnostiques.

## Contrat OOF/PIT

La population et l'horloge sont identiques à E13 :

- 37 659 événements Oracle OOF dédupliqués ;
- 3 118 entrées rejetées par le filtre de gap PROD 3 % ;
- 34 541 trajectoires lifecycle disponibles ;
- 32 314 événements prédits OOF ;
- premier fold ignoré faute de passé purgé ;
- 13 folds évalués entre 2019-01-04 et 2025-01-08 ;
- un label train n'est accepté que si sa sortie est strictement antérieure au
  début du fold test.

Les features sont celles d'E13 : Oracle, rendements passés, volatilité/ATR,
drawdown, position dans le range, volume, ADV, prix et gap J→J+1, ainsi que
leurs rangs cross-sectionnels. Elles sont toutes connues au close J ou à l'open
J+1. Aucune capitalisation actuelle ni snapshot tradable dégradé n'entre dans
l'apprentissage.

## Construction des cibles

### Utilité nette attendue

Un `CatBoostRegressor` prédit le rendement net réellement obtenu par le
lifecycle PROD. Pour limiter l'influence des queues extrêmes, le target train
est winsorisé aux quantiles 1 % et 99 % calculés séparément sur chaque train.
Les bornes test ne sont jamais utilisées.

### Probabilité de perte

Un `CatBoostClassifier` prédit `P(net_return < 0)`. La pondération des classes
est recalculée uniquement sur le train. Cette tête permet de distinguer une
espérance faible d'une probabilité élevée de perte.

Les deux modèles utilisent 300 itérations, profondeur 5, learning rate 0,03 et
quatre threads. Les imputations et seuils 10/20/30 % proviennent exclusivement
des prédictions train de chaque fold.

## Qualité des scores économiques

| Mesure | Résultat |
|---|---:|
| IC Spearman utilité OOF global | +0,0364 |
| IC utilité quotidien moyen | +0,0047 |
| Dates avec IC quotidien positif | 50,12 % |
| IC OOF du score de non-perte | +0,0592 |

L'IC utilité est positif dans 12 folds sur 13, mais varie fortement : `-0,0636`
en 2021H2, environ `+0,20` en 2020, puis seulement `+0,007` à `+0,086` depuis
2023. La moyenne quotidienne presque nulle montre que l'information globale ne
se transforme pas régulièrement en classement cross-sectionnel quotidien.

### Déciles d'utilité prévue

| Décile | Rendement PROD moyen | Taux de perte | Taux de trailing |
|---:|---:|---:|---:|
| 0, utilité minimale | +0,433 % | 49,20 % | 45,98 % |
| 1 | +0,089 % | 51,01 % | 48,62 % |
| 5 | -0,103 % | 51,22 % | 48,13 % |
| 7 | +0,345 % | 42,62 % | 38,81 % |
| 8 | +0,420 % | 38,75 % | 34,17 % |
| 9, utilité maximale | +1,162 % | 30,60 % | 25,50 % |

Le décile supérieur est nettement meilleur, mais la relation n'est pas
monotone dans les déciles intermédiaires. Le décile inférieur reste positif,
ce qui rend un veto dur moins naturel qu'un reranking.

## Résultats portefeuille

| Politique | Trades | Rendement moyen | Moyenne/date | Perte | Trailing | Q05 | Delta/date |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline Oracle | 1 886 | +0,328 % | +0,360 % | 36,90 % | 33,35 % | -16,52 % | — |
| Utilité veto 10 % | 1 837 | +0,241 % | +0,136 % | 37,45 % | 33,42 % | -16,60 % | -0,207 % |
| **Utilité veto 20 %** | **1 821** | **+0,352 %** | **+0,149 %** | **36,74 %** | **32,56 %** | **-16,62 %** | **-0,188 %** |
| Utilité veto 30 % | 1 806 | +0,396 % | +0,302 % | 37,04 % | 32,78 % | -16,71 % | -0,058 % |
| Perte veto 20 % | 1 894 | +0,389 % | +0,326 % | 36,22 % | 32,79 % | -16,61 % | -0,029 % |
| Utilité seule en ranking | 1 674 | +0,389 % | +0,275 % | 39,73 % | 34,47 % | -14,58 % | -0,081 % |
| Faible perte en ranking | 1 680 | +0,336 % | +0,204 % | 36,61 % | 30,89 % | -15,60 % | -0,144 % |
| Oracle/utilité 50/50 | 1 803 | +0,456 % | +0,460 % | 37,10 % | 32,17 % | -15,57 % | +0,063 % |

Le veto primaire a un IC95 du delta journalier de
`[-0,545 % ; +0,132 %]`. Il échoue malgré une moyenne par trade légèrement
supérieure, parce qu'il modifie la chronologie de capacité et perd des cohortes
favorables. Le Q05 se dégrade également.

L'hybride 50/50 est le seul diagnostic qui améliore simultanément la moyenne
par date et le Q05. Son IC95 du delta `[-0,330 % ; +0,413 %]` recouvre cependant
largement zéro. Il n'améliore que 7 semestres sur 14 et détériore notamment
2019H2, 2020H1/H2, 2023H2 et 2025H1/H2. Il n'est donc pas promu et ses poids ne
doivent pas être optimisés sur ce résultat.

## Variables dominantes

Importance moyenne de la tête utilité :

1. ATR% : 13,56 % ;
2. prix logarithmique : 5,35 % ;
3. probabilité Oracle : 5,23 % ;
4. drawdown 20 séances : 4,68 % ;
5. rendement 20 séances : 4,60 % ;
6. gap signé : 4,40 %.

La tête probabilité de perte est encore plus dominée par l'ATR% : 25,56 %.
Comme dans E13, une part du signal apprend la géométrie du lifecycle. La cible
économique réduit ce biais sans le supprimer.

## Investabilité

Les snapshots tradables `full` ne couvrent que 53 dates. Sur les données
`degraded`, la baseline vaut +0,098 % moyen et le veto primaire +0,088 % : aucune
amélioration. Cette sensibilité ne peut pas servir de validation production.

## Gates primaires

| Gate | Résultat |
|---|---|
| IC utilité global positif | PASS |
| IC utilité quotidien positif | PASS marginal |
| Couverture ≥ 70 % | PASS |
| Delta journalier positif | FAIL |
| Borne basse IC95 du delta > 0 | FAIL |
| Taux de perte non dégradé | PASS |
| Q05 non dégradé | FAIL |
| Lift positif sur ≥ 70 % des semestres | FAIL |
| Univers tradable PIT strict complet | FAIL |

Verdict : `NO_GO_OR_BLOCKED`.

## Conclusion

Les features OHLCV pré-entrée contiennent une faible information sur l'utilité
future, mais pas assez stable pour transformer le TOP20 Oracle en politique
tradable. E14 ferme les veto économiques 10/20/30 % et interdit un sweep des
poids hybrides sur les mêmes folds.

La suite la plus justifiée est de revenir au problème structurel mis en évidence
par E12 : comparer quelques contrats de lifecycle pré-enregistrés, avec nested
walk-forward et sans toucher à la sélection Oracle. Il faut notamment distinguer
la valeur d'un trailing immédiat de celle d'une activation après progression
positive. Cette future expérience doit rester séparée de l'optimisation 2026.

## Reproduction

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oracle_pre_entry_utility --oracle-gate artifacts/models/model-factory-20260909051302-323684/_oracle_oof_gate.parquet --iterations 300 --bootstrap-samples 2000 --log-level INFO
```

Tests : `tests/test_oracle_pre_entry_utility.py` avec les suites E12/E13.


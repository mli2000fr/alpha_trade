# E13 — Veto pré-entrée après Oracle

## Statut

`FAIT_NO_GO_OR_BLOCKED` — le score de risque est prédictif du type de sortie,
mais le veto n'améliore pas économiquement le portefeuille OOF. L'historique
tradable PIT strict reste par ailleurs incomplet.

Artefact canonique :
`artifacts/research/oracle_pre_entry_veto/oracle-pre-entry-veto-20260911155716`.

Le rapport `oracle-pre-entry-veto-20260911155249` est exploratoire et
supplanté. Son veto quotidien sur tout le pool Oracle ne touchait que 4,7 % des
trades finalement sélectionnés. Le schéma 2 apprend donc le seuil absolu sur le
train purgé de chaque fold et l'applique sans modification au test suivant.

## Hypothèse

E12 a montré que le lifecycle PROD retire en moyenne 2,12 points au rendement
H20 et que les trailing stops perdent 10,93 % en moyenne. E13 teste si une
information disponible avant l'entrée permet d'éviter les futurs trailing
stops sans dégrader la valeur économique du portefeuille.

```text
Oracle TOP20 OOF
  -> signal dédupliqué par symbole
  -> variables connues au close J / open J+1
  -> risque OOF de futur trailing stop
  -> veto des 10 %, 20 % ou 30 % les plus risqués
  -> priorité Oracle, capacité 8, réallocation après sortie réelle
  -> lifecycle PROD inchangé
```

Le veto primaire de 20 % est fixé avant le run canonique. Les variantes 10 % et
30 % sont diagnostiques et ne peuvent pas être choisies après lecture du test.

## Population et horloge

- Gate : `_oracle_oof_gate.parquet` du batch
  `model-factory-20260909051302-323684`.
- 37 659 événements Oracle dédupliqués.
- 3 118 entrées rejetées par le gap PROD de 3 %.
- 34 541 chemins lifecycle disponibles après ce filtre.
- 32 314 observations dotées d'un score de risque strictement OOF.
- Premier fold Oracle ignoré : aucun historique antérieur purgé n'existe pour
  entraîner E13.
- 13 folds suivants évalués, de 2019-01-04 à 2025-01-08.
- Un événement d'entraînement n'est admis que si sa `exit_date` est strictement
  antérieure au début du fold évalué. Le label H20 du train ne chevauche donc
  pas la période test.

## Variables autorisées

Toutes les variables sont disponibles au plus tard au moment de décider
l'entrée :

- probabilité et percentile Extreme Oracle OOF ;
- rendements passés 1, 5 et 20 séances ;
- volatilité réalisée 20 séances ;
- ATR20 calculé au close J, rapporté au close J ;
- drawdown et position dans le range des 20 dernières séances ;
- volume du signal rapporté à sa médiane 20 séances ;
- ADV20 et prix du signal en logarithme ;
- gap signé et absolu entre le close J et l'open J+1, observable avant
  l'exécution à l'open ;
- rang cross-sectionnel quotidien de chacune de ces variables.

Les capitalisations actuelles, secteurs reconstruits a posteriori et snapshots
tradables dégradés ne sont pas des features du modèle. Ils ne satisfont pas la
preuve PIT exigée pour apprendre le veto.

## Modèle et politiques

Un CatBoost mutualisé binaire prédit `P(future trailing_stop)`. Ses paramètres
sont figés : 300 itérations, profondeur 5, learning rate 0,03, pondération des
classes calculée sur le train et quatre threads.

Pour chaque fold, le modèle calcule ses scores sur le train puis fixe les
quantiles de risque 90/80/70 %. Ces seuils sont appliqués tels quels au test du
fold. La politique primaire retire les scores supérieurs au quantile train de
80 %. Le taux effectivement rejeté peut donc différer de 20 % en cas de drift ;
il varie ici de 0,4 % à 32,0 % selon le fold.

Deux familles sont conservées dans le rapport :

- `daily_veto_*` : rang de risque parmi tous les événements Oracle du jour ;
- `absolute_oof_veto_*` : seuil appris sur le train purgé, politique canonique.

Après veto, le portefeuille est reconstruit chronologiquement avec huit places,
priorité au score Oracle, aucune anticipation des sorties intraday et
réallocation à partir de la séance suivante.

## Pouvoir prédictif du risque

L'AUC OOF globale vaut `0,6259`. Tous les folds évalués restent au-dessus de
0,56 ; le meilleur atteint 0,713. Les déciles confirment une séparation réelle :

| Décile de risque | Taux de trailing | Rendement PROD moyen |
|---:|---:|---:|
| 0, risque minimal | 21,84 % | +1,162 % |
| 1 | 29,00 % | +0,994 % |
| 2 | 36,61 % | +0,243 % |
| 7 | 52,77 % | +0,006 % |
| 8 | 54,50 % | +0,198 % |
| 9, risque maximal | 58,14 % | +0,120 % |

Le score identifie donc correctement la probabilité du motif `trailing_stop`.
Ce motif n'est toutefois pas équivalent à une perte certaine : même le décile
le plus risqué conserve un rendement moyen légèrement positif avant capacité.

## Résultats portefeuille

| Politique | Trades | Rendement moyen | Moyenne par date | Trailing | Q05 | Delta journalier vs baseline |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 1 886 | +0,328 % | +0,360 % | 33,35 % | -16,52 % | — |
| Daily veto 10 % | 1 893 | +0,330 % | +0,235 % | 33,17 % | -16,31 % | -0,122 % |
| Daily veto 20 % | 1 865 | +0,337 % | +0,347 % | 33,08 % | -16,28 % | -0,016 % |
| Daily veto 30 % | 1 842 | +0,290 % | +0,312 % | 33,06 % | -16,53 % | -0,054 % |
| OOF absolu 10 % | 1 880 | +0,295 % | +0,249 % | 33,40 % | -16,60 % | -0,108 % |
| **OOF absolu 20 %** | **1 874** | **+0,357 %** | **+0,306 %** | **32,82 %** | **-16,55 %** | **-0,052 %** |
| OOF absolu 30 % | 1 867 | +0,313 % | +0,259 % | 33,05 % | -16,65 % | -0,096 % |

Pour la politique primaire, l'IC95 du delta journalier est
`[-0,185 % ; +0,087 %]`. Le petit gain de moyenne par trade ne survit donc ni à
l'agrégation temporelle, ni au bootstrap. Le trailing baisse de seulement 0,53
point absolu, loin de la réduction relative minimale de 20 % pré-enregistrée.
Le Q05 se détériore légèrement.

La stabilité temporelle échoue également. Le veto 20 % aide notamment 2019H1,
2021H2 et marginalement 2022H2, mais détériore 2022H1, 2023H2, 2024H1,
2024H2 et 2025H1. Seulement huit semestres sur quatorze sont positifs ou nuls,
en dessous du gate de 70 % de lifts strictement positifs.

## Ce que le modèle apprend réellement

L'importance moyenne est dominée par :

1. ATR% : 26,48 % ;
2. volatilité 20 séances : 6,35 % ;
3. probabilité Oracle : 4,36 % ;
4. drawdown 20 séances : 4,14 % ;
5. prix : 3,76 %.

Le lien ATR/trailing est en grande partie mécanique : un faible ATR produit un
trailing en pourcentage plus serré et donc davantage de sorties de ce type.
E13 prédit bien la mécanique de sortie, mais pas une erreur directionnelle ou
une perte évitable suffisamment stable pour améliorer le portefeuille.

## Sensibilité tradable

La couche `full` ne couvre que 53 dates de la population scorée. La sensibilité
`degraded` couvre 1 670 dates :

- baseline : 576 trades, +0,098 % moyen, 50,87 % de trailing ;
- veto primaire : 454 trades environ selon la réallocation, +0,216 % moyen,
  47,36 % de trailing.

Cette amélioration apparente n'est pas promouvable : l'IC95 recouvre zéro et la
qualité `degraded` ne garantit pas une reconstruction historique exacte.

## Gates et verdict

| Gate primaire | Résultat |
|---|---|
| Couverture portefeuille ≥ 70 % | PASS |
| Delta journalier positif | FAIL |
| Borne basse IC95 du delta > 0 | FAIL |
| Réduction relative du trailing ≥ 20 % | FAIL |
| Q05 non dégradé | FAIL |
| Lift positif sur ≥ 70 % des semestres | FAIL |
| Univers tradable PIT strict complet | FAIL |

Verdict : `NO_GO_OR_BLOCKED`. Le modèle et ses veto restent research-only. Ils
ne doivent pas être intégrés au batch, au serving, au backtest IHM ou au live.

## Conclusion et suite autorisée

E13 ferme la piste « prédire le motif de sortie puis le transformer directement
en veto ». La prochaine expérience ne doit pas balayer davantage de seuils sur
ce même score. Une suite défendable doit changer la cible économique : prédire
la perte nette ou l'utilité conditionnelle après coûts, avec comparaison à une
simple adaptation du stop à l'ATR, et conserver un test temporel intact.

Avant toute promotion, il reste indispensable de reconstruire les snapshots
tradables historiques en qualité `full`.

## Reproduction

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oracle_pre_entry_veto --oracle-gate artifacts/models/model-factory-20260909051302-323684/_oracle_oof_gate.parquet --iterations 300 --bootstrap-samples 2000 --log-level INFO
```

Tests : `tests/test_oracle_pre_entry_veto.py` et
`tests/test_oracle_monetization_bridge.py` — 16 tests ciblés.


# P-MATH-1 — relations cross-asset lead-lag sur résidus

## Question de recherche

P-MATH-0 a montré que les 84 variables d'état connues ne séparent pas de façon
stable D1 et D10 dans le pool Oracle. P-MATH-1 teste une information différente :
le mouvement récent d'autres actions contient-il une avance exploitable sur le
sens futur d'un candidat Oracle ?

Cette expérience est indépendante du serving. Elle ne modifie ni les modèles en
production, ni les tables, ni le backtest.

## Population et cibles

- batch Oracle de référence et horizon H20 ;
- pool Oracle OOF TOP20 exactement identique à P-MATH-0 ;
- tâches gelées : `D1_VS_D10`, `D10_VS_REST`, `D1_VS_REST` ;
- folds walk-forward 504/126/126, pas 126, au plus 12 folds récents ;
- `oracle_available_date < val_start` pour le train.

Les rendements futurs et les déciles ne servent jamais à construire le graphe.

## Construction causale du signal

Pour chaque fold :

1. calculer les rendements journaliers sur `adj_close` ;
2. estimer, sur le train seulement, les bêtas marché SPY et secteur ;
3. produire le résidu de chaque titre avec ces coefficients figés ;
4. choisir au plus 96 leaders d'après leur seule couverture historique ;
5. mesurer les corrélations leader à J−k → suiveur à J pour k=1,2,3,5 ;
6. couper le train en deux moitiés chronologiques ;
7. retenir une relation uniquement si son signe est identique dans les deux
   moitiés, avec au moins 126 observations et |corrélation| ≥ 0,05 ;
8. conserver au plus cinq arêtes par suiveur.

Le poids est conservateur : signe commun multiplié par la plus petite des deux
corrélations absolues. La pression est :

```text
pression(i,J) = somme[w(j,k→i) × résidu(j,J-k)] / somme[|w(j,k→i)|]
```

Il n'existe aucun lag 0. Une modification du rendement du leader à J ne peut
donc pas modifier la pression du suiveur à J.

## Comparaisons OOS

Chaque fold mesure trois variantes :

- pression seule ;
- témoin logistique sur les variables P-MATH-0 ;
- même témoin augmenté de la pression lead-lag.

Les métriques principales sont l'AUC de la pression, le delta d'AUC incrémental,
sa stabilité entre folds et le gain de rendement signé du décile le plus
confiant. Pour D1/reste, le rendement signé vaut l'opposé du rendement brut.

## Gates pré-enregistrées

Un GO demande simultanément :

- AUC médiane pression ≥ 0,53 ;
- delta d'AUC médian ≥ +0,01 ;
- delta positif dans au moins 67 % des folds ;
- gain médian de rendement signé du top décile ≥ +0,25 %.

Un échec ne doit pas être réparé en ajustant les seuils sur la période de test.

## Exécution

Smoke :

```powershell
python -u -m modelFactory.oracle_lead_lag_pmath1 --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2016-01-01 --end-date 2025-12-31 --max-symbols 50 --max-folds 2 --log-level INFO
```

Run complet : retirer `--max-symbols` et `--max-folds`.

Les sorties sont `report.json`, `fold_metrics.csv` et `stable_edges.csv` dans
`artifacts/research/pmath1_cross_asset_lead_lag/`.

## Résultat complet — NO_GO

Artefact :
`artifacts/research/pmath1_cross_asset_lead_lag/pmath1-full-20260916-v2`.

Le run couvre 582 700 événements, 1 764 dates, 1 472 symboles et neuf folds
OOS de janvier 2021 à juillet 2025. La pression couvre environ 93–94 % des
observations évaluées. Chaque fold retient entre 11 440 et 12 143 arêtes :
l'échec ne provient donc ni d'un graphe vide ni d'un manque de couverture.

| Tâche | AUC pression médiane | AUC témoin | AUC augmenté | Delta AUC médian | Folds delta positif | Lift économique médian |
|---|---:|---:|---:|---:|---:|---:|
| D1 vs D10 | 0,4956 | 0,5005 | 0,4999 | +0,00007 | 7/9 | +0,073 % |
| D10 vs reste | 0,4998 | 0,5088 | 0,5089 | +0,00001 | 5/9 | −0,052 % |
| D1 vs reste | 0,4977 | 0,5308 | 0,5314 | +0,00004 | 5/9 | −0,024 % |

Les quatre gates échouent pour D10/reste et D1/reste. D1/D10 ne passe que la
condition formelle de fréquence de deltas positifs, mais leur amplitude est
négligeable et les gates AUC, delta minimal et rendement échouent.

Les lags sont tous représentés — 28,35 % des arêtes à J−1, 25,02 % à J−2,
24,71 % à J−3 et 21,92 % à J−5. La persistance Jaccard des arêtes entre folds
adjacents varie de 0,08 à 0,41. Même lorsqu'une structure de corrélation
résiduelle est détectée dans le train, elle ne contient pas d'information OOS
sur D1/D10.

### Décision

`NO_GO_INCREMENTAL_LEAD_LAG`. Ne pas intégrer la pression au modèle, au
serving ou au backtest. Ne pas balayer les lags, le nombre de leaders ou le
seuil de corrélation sur les mêmes folds : le signal brut est centré sur 0,50
et l'apport incrémental est cent fois inférieur au minimum pré-enregistré.

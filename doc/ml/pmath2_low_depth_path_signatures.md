# P-MATH-2 — signatures de trajectoire de faible profondeur

## Hypothèse

P-MATH-0 n'a pas trouvé de séparation stable dans l'état ponctuel J et
P-MATH-1 a rejeté le graphe cross-asset linéaire. P-MATH-2 teste une autre
représentation : l'ordre des mouvements sur les 20 séances terminant à J.

Le test ne réutilise pas le graphe P-MATH-1. Il ne dépend ni de leaders, ni de
seuils de corrélation, ni d'une donnée future.

## Chemin observé

Pour chaque événement Oracle OOF TOP20, le chemin J−19…J comporte quatre
canaux d'incréments :

1. temps normalisé, 1/20 par séance ;
2. rendement ajusté du titre ;
3. rendement ajusté de SPY ;
4. rendement médian contemporain du secteur.

Au moins 18 rendements du titre sur 20 doivent être disponibles. Les rendements
manquants acceptés sont représentés par zéro après le contrôle de couverture.
Le secteur est construit quotidiennement sans labels et sans observation
postérieure à J.

## Signature tensorielle

La signature tronquée d'un chemin contient ses intégrales itérées. Avec quatre
canaux :

- profondeur 1 : 4 coordonnées, essentiellement les déplacements cumulés ;
- profondeur 2 : 4 + 16 = 20 coordonnées, dont les termes ordonnés A→B ;
- profondeur 3 : 4 + 16 + 64 = 84 coordonnées.

La profondeur 2 est l'expérience primaire. La profondeur 3 est confirmatoire :
elle ne doit pas servir à choisir post-hoc la variante la plus favorable.
Le calcul est exact pour un chemin linéaire par morceaux via l'identité de
Chen ; aucune bibliothèque externe ni approximation aléatoire n'est utilisée.

## Protocole OOS

- batch `model-factory-20260909051302-323684`, Oracle H20 ;
- même pool, mêmes cibles et mêmes folds que P-MATH-0/P-MATH-1 ;
- train protégé par `oracle_available_date < val_start` ;
- Logistic L2 après winsorisation et standardisation apprises sur le train ;
- comparaison `STATE_J`, signature seule et `STATE_J + signature` ;
- tâches D1/D10, D10/reste et D1/reste.

Gates pré-enregistrées pour la profondeur 2 : AUC signature ≥ 0,53, delta AUC
médian ≥ +0,01, delta positif dans au moins 67 % des folds et lift médian du
rendement signé du top décile ≥ +0,25 %.

## Commandes

Smoke :

```powershell
python -u -m modelFactory.oracle_path_signatures_pmath2 --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2016-01-01 --end-date 2025-12-31 --max-symbols 50 --max-folds 2 --log-level INFO
```

Le run complet retire `--max-symbols` et `--max-folds`. Les artefacts sont
écrits sous `artifacts/research/pmath2_path_signatures/`. Aucun SQL, serving ou
backtest n'est modifié.

## Résultat complet — NO_GO

Artefact : `artifacts/research/pmath2_path_signatures/pmath2-full-20260916`.

Le run complet couvre 582 700 événements, 1 764 dates, 1 472 symboles et neuf
folds OOS. La couverture des chemins est de 100 %. L'échec ne vient donc pas
d'un historique incomplet.

### Profondeur 2 primaire

| Tâche | AUC signature | AUC témoin | AUC augmenté | Delta AUC | Folds delta positif | Lift économique |
|---|---:|---:|---:|---:|---:|---:|
| D1 vs D10 | 0,4996 | 0,5010 | 0,5091 | −0,0046 | 3/9 | −0,361 % |
| D10 vs reste | 0,4932 | 0,5030 | 0,5063 | +0,00003 | 5/9 | +0,145 % |
| D1 vs reste | 0,5115 | 0,5293 | 0,5248 | +0,0016 | 6/9 | −0,140 % |

Les quatre gates échouent sur les trois tâches.

### Profondeur 3 confirmatoire

| Tâche | AUC signature | AUC augmenté | Delta AUC | Folds delta positif | Lift économique |
|---|---:|---:|---:|---:|---:|
| D1 vs D10 | 0,5116 | 0,5140 | −0,0046 | 4/9 | +0,529 % |
| D10 vs reste | 0,5098 | 0,5093 | −0,0017 | 4/9 | +0,171 % |
| D1 vs reste | 0,5199 | 0,5277 | +0,0064 | 6/9 | −0,073 % |

D1/reste est la seule indication partielle : la profondeur 3 ajoute +0,0064
d'AUC médiane dans 6/9 folds. Elle reste toutefois sous les gates AUC 0,53 et
delta +0,01, et son lift économique est négatif. Les gains économiques isolés
des deux autres tâches coexistent avec un delta AUC négatif et ne sont pas
stables : ils ne justifient aucune promotion.

### Décision

`NO_GO_INCREMENTAL_PATH_SIGNATURE`. Ne pas intégrer ces signatures, ne pas
augmenter la profondeur et ne pas chercher une fenêtre favorable sur les mêmes
folds. La prochaine expérience doit changer la cible statistique — distribution
conditionnelle/quantiles — plutôt qu'ajouter une représentation du même chemin.

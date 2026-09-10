# P0g — Impact directionnel du nouvel univers Oracle dynamique

## Objectif

P0f a montré que l'univers quotidien PIT dynamique améliore nettement la
détection d'amplitude de l'Oracle. P0g vérifie une question distincte :

> la population TOP20 issue de ce meilleur Oracle rend-elle D1 et D10 plus
> séparables par les features directionnelles déjà disponibles ?

Le test est volontairement limité au meilleur témoin historique non contextuel.
Il ne recherche ni seuil, ni feature, ni hyperparamètre. Les variantes E1/E2 ne
sont ouvertes que si ce témoin franchit d'abord les gates directionnels.

## Source et contrat

- Oracle : `model-factory-20260909051302-323684`
- Univers Oracle : `pit_dynamic_bars`
- Prédictions Oracle : exclusivement OOS, traçables par `fold_start`
- Gate : TOP20 quotidien de `proba_extreme`
- Cible : D1 = SHORT, D10 = LONG ; D2–D9 hors entraînement
- Modèle : CatBoost mutualisé, sans contexte symbole ni secteur
- Features : profil directionnel partagé existant, 84 numériques
- Walk-Forward : 504/126/126, pas 126, maximum 14
- Hyperparamètres figés : 600 itérations max, profondeur 6, learning rate 0,03
- Serving : désactivé

Commande exécutée :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.shared_directional --oracle-batch-id model-factory-20260909051302-323684 --start-date 2016-01-01 --end-date 2025-12-31 --target decile_direction --horizons 20 --context-mode none --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 14 --iterations 600 --depth 6 --learning-rate 0.03 --log-level INFO
```

Artefact :

```text
artifacts/models/shared_directional/shared-direction-20260909075129-323684
```

## Compatibilité du cache OOF

Le premier lancement a détecté que les entraînements Oracle autonomes ne
créaient pas `_oracle_oof_gate.parquet`. Le harnais directionnel dépendait
historiquement d'un bundle pour produire ce fichier.

Le correctif reconstruit désormais le cache manquant depuis
`oracle_extreme_predictions`, avec les gardes suivantes :

- filtrage strict par `batch_id` ;
- `fold_start` obligatoire pour qu'une ligne soit admissible ;
- exclusion des éventuelles prédictions de serving sans origine OOF ;
- recalcul du percentile et du TOP20 par date ;
- persistance du cache et de ses diagnostics pour les relances.

Pour ce batch, 2 908 295 lignes ont été lues et aucune ligne non-OOF n'a été
trouvée. Le cache contient 582 700 événements TOP20 sur 1 764 dates. L'univers
quotidien varie de 1 301 à 2 027 titres, avec une médiane de 1 688.

## Résultat global

| Mesure | Résultat P0g |
|---|---:|
| Population TOP20 Oracle | 582 700 |
| Symboles TOP20 | 1 472 |
| Dates Oracle | 1 764 |
| Folds directionnels valides | 9 |
| Lignes D1/D10 évaluées OOS | 179 605 |
| AUC D10 contre D1 | **0,4904** |
| IC directionnel quotidien | **−0,0147** |
| TOP LONG : D10 | 46,88 % |
| TOP LONG : D1 | 53,12 % |
| Rendement moyen TOP LONG | +0,69 % |
| Médiane TOP LONG | −5,82 % |
| TOP SHORT : D1 | 50,82 % |
| TOP SHORT : D10 | 49,18 % |
| Rendement signé TOP SHORT | −1,43 % |

Le rendement moyen LONG positif ne constitue pas un signal exploitable : sa
médiane est fortement négative, le décile contient davantage de D1 que de D10
et l'IC quotidien est négatif. Le côté SHORT perd également après inversion du
signe.

## Stabilité Walk-Forward

| Fold | Test | AUC | IC quotidien | LONG signé | SHORT signé |
|---:|---|---:|---:|---:|---:|
| 0 | 2021-01-05 → 2021-07-06 | 0,501 | −0,075 | +1,31 % | −3,38 % |
| 1 | 2021-07-07 → 2022-01-03 | 0,453 | −0,040 | −3,86 % | +1,05 % |
| 2 | 2022-01-04 → 2022-07-06 | 0,486 | +0,016 | −2,65 % | +1,75 % |
| 3 | 2022-07-07 → 2023-01-04 | 0,539 | +0,015 | +5,09 % | −6,24 % |
| 4 | 2023-01-05 → 2023-07-07 | 0,439 | −0,075 | +2,50 % | −5,96 % |
| 5 | 2023-07-10 → 2024-01-05 | 0,456 | −0,031 | −0,86 % | −2,40 % |
| 6 | 2024-01-08 → 2024-07-09 | 0,500 | +0,011 | +0,21 % | +0,05 % |
| 7 | 2024-07-10 → 2025-01-07 | 0,496 | +0,016 | +2,22 % | −2,39 % |
| 8 | 2025-01-08 → 2025-07-11 | 0,592 | +0,027 | +2,05 % | +3,94 % |

Le dernier fold est favorable, mais il ne suffit pas à promouvoir le modèle :
quatre folds seulement dépassent ou égalent approximativement 0,50 en AUC, les
rendements changent de signe et l'agrégat reste inférieur au hasard. Utiliser
le seul fold 2025 pour choisir une règle créerait une sélection a posteriori.

## Comparaison avec le témoin historique

Le témoin sans contexte entraîné sur l'ancien Oracle obtenait environ AUC
0,503 et IC quotidien +0,004. P0g obtient AUC 0,490 et IC −0,015 malgré une
population beaucoup plus grande. Le nouvel univers améliore donc l'amplitude,
mais pas la séparabilité directionnelle avec les features existantes.

## Décision

Statut : `FAIT_NO_GO_DIRECTION`.

Les campagnes lourdes `signed_return` et `dual_threshold` ne sont pas relancées :
le témoin préfixé n'a franchi aucun gate et ne montre pas un accident limité à
une seule période. Répéter toutes les anciennes variantes sur la population
élargie augmenterait le coût et le risque d'optimisation sans hypothèse nouvelle.

P0f reste `GO_RECHERCHE` pour l'amplitude. Toute nouvelle piste de direction
doit apporter une information PIT réellement nouvelle ou une cible différente,
pas seulement réentraîner les mêmes features sur davantage de symboles.


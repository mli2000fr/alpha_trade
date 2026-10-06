# Sprint 10-C — Global ranking signé CN_A et test conditionnel Oracle

## Question

Le Sprint 10-B a confirmé un signal d'**amplitude** CN face à une baseline
ATR, sans distinguer D1 de D10. Le Sprint 10-C teste une autre hypothèse :
un modèle global entraîné sur le **décile de rendement réel par date** peut-il
ordonner les titres de D1 à D10 ? Il est entraîné sur tout l'univers PIT CN,
puis évalué (1) sur l'univers entier et (2) uniquement parmi les TOP20
Oracle **déjà prédits OOS**. Il ne reçoit jamais le score Oracle comme
feature d'entraînement.

Ce test appartient à la recherche, pas au serving. Un classement réussi
serait encore insuffisant pour trader : entrée réalisable, T+1, limites CN,
lots, liquidité et frais restent hors de cette étape.

## Pré-enregistrement et absence de fuite

Le [protocole YAML](../../config/research_cn/sprint10c_global_ranking.yaml)
est figé avant la campagne complète. Il impose les mêmes 8 tests semestriels
2022H1–2025H2, les mêmes quatre horizons et la même purge de labels que le
Sprint 10-B. Les cibles valides ont `oracle_decile` de 1 à 10 ; le modèle
apprend `oracle_decile - 1`. LightGBM et CatBoost sont ici deux **régressions
ordinales pointwise**, dont les sorties sont ensuite classées par date. Ce
ne sont pas des politiques d'exécution, ni un entraînement LambdaRank/YetiRank.

Les 33 features numériques/flags sont celles du protocole Oracle du Sprint
10-B, toutes connues avant J. La baseline signée est `relative_return_20`
(momentum du titre moins benchmark). Le plafond d'entraînement est 600 000
lignes déterministes par fold ; validation et test ne sont pas échantillonnés.
L'early stopping ne consulte que la validation. Les labels de train doivent
être connus avant sa première décision ; les labels de validation avant la
première décision du test.

Le pool Oracle utilise, pour **chaque horizon et chaque date OOS**, la
moyenne à poids égaux des deux scores Oracle LightGBM/CatBoost du Sprint
10-B. On retient ses TOP20 **sur la population entière du jour, avant de
filtrer les labels invalides**. Les deux modèles Oracle sont déjà figés et
leurs prédictions sont contrôlées par SHA. Ce choix d'ensemble est une
nouvelle hypothèse de recherche, pas une confirmation indépendante de
l'Oracle : les périodes OOS 2022–2025 ont déjà servi à l'étudier.

## Mesures et gate

Sur l'univers entier : IC de Spearman par date, D10 dans le TOP10, D1 dans
le BOTTOM10, contamination opposée (D1 classé en haut ou D10 en bas),
rendements moyens et spread de prix. Dans le pool Oracle TOP20 : mêmes
mesures mais avec les 20 % les mieux et les 20 % les moins bien classés du
pool. Les comparaisons modèle/baseline sont faites sur **exactement les mêmes
lignes avec label valide et baseline disponible**. La couverture est publiée.

La métrique principale pré-enregistrée est la moyenne des deux précisions
conditionnelles : D10 en haut et D1 en bas du pool Oracle. Le GO recherche
exige :

1. au moins 60 séances évaluables par semestre ;
2. au moins 95 % des trajectoires mûres correctement labellisées ;
3. amélioration dans au moins 6 des 8 semestres ;
4. au moins **+2 points** de précision symétrique conditionnelle face au
   momentum relatif ;
5. borne basse du bootstrap mensuel strictement positive, avec correction
   Bonferroni pour 4 horizons × 2 modèles (alpha 0,05/8).

L'IC, le spread, la composition par board/année/régime de breadth et les
erreurs de sens sont des diagnostics complémentaires. Aucun seuil ne doit
être déplacé après lecture des folds. Le secteur historique PIT reste absent
et n'est pas simulé avec une classification actuelle.

## Exécution et provenance

Le [moteur par fold](../../modelFactory/cn_global_ranking_walk_forward.py),
le [lanceur reprenable](../../dataIntegrityEngine/cn_sprint10c_campaign.py)
et l'[agrégateur](../../modelFactory/cn_global_ranking_aggregate.py)
conservent modèles, prédictions OOS Parquet, dates de purge, hashes du code,
des labels et des prédictions Oracle. Ils refusent les artefacts divergents
et ne modifient aucune table métier.

```powershell
F:\projets\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint10c_campaign
F:\projets\.venv\Scripts\python.exe -m modelFactory.cn_global_ranking_aggregate --require-complete
```

Le rapport final est sous `artifacts/cn/ranking/sprint10c/`.
`INCOMPLETE` n'autorise aucun verdict. Même un éventuel `GO_RESEARCH_ONLY`
ne choisit pas automatiquement un horizon/modèle pour le live : après
l'observation des résultats 10-B et 10-C, une confirmation sur des données
CN plus récentes ou une période indépendante reste nécessaire.

## Résultats de la campagne complète

Les **64 folds attendus sont terminés et vérifiés** : 4 horizons × 2 modèles ×
8 semestres. L'agrégation stricte ne signale aucun fold manquant ; le statut
est `COMPLETE_RESEARCH_ONLY`. Les huit combinaisons franchissent le gate
pré-enregistré **face au momentum relatif** : amélioration de la précision
symétrique supérieure à 2 points, 8 semestres positifs sur 8 et borne basse
du bootstrap mensuel positive même après correction pour huit hypothèses.
Cela ne signifie ni que les deux directions sont bonnes, ni que le classement
est prêt pour une décision de trading.

Voici les résultats LightGBM **dans le pool Oracle TOP20 OOS**. Les pourcentages
D10 et D1 sont des précisions conditionnelles parmi les 20 % extrêmes
sélectionnés *au sein de ce pool*, et non des taux de réussite de trades.

| Horizon | Précision symétrique modèle / momentum | D10 dans le haut modèle / momentum | D1 dans le bas modèle / momentum | IC moyen global modèle / momentum |
| --- | ---: | ---: | ---: | ---: |
| H5 | 26,10 % / 19,71 % | 16,04 % / 18,37 % | 36,16 % / 21,04 % | +0,093 / −0,057 |
| H10 | 25,93 % / 18,15 % | 15,46 % / 16,07 % | 36,41 % / 20,22 % | +0,110 / −0,071 |
| H15 | 25,88 % / 17,38 % | 15,25 % / 14,92 % | 36,51 % / 19,85 % | +0,117 / −0,080 |
| H20 | 25,49 % / 16,90 % | 15,04 % / 14,19 % | 35,94 % / 19,62 % | +0,118 / −0,083 |

Le gain symétrique H20 est de **+8,59 points** ; sa borne basse de bootstrap
avec correction familiale est **+6,66 points**. Le même déséquilibre entre
branches apparaît avec CatBoost. Les mesures couvrent environ 0,91 à
0,94 million de lignes labellisées dans le pool selon l'horizon, et près de
950 séances OOS. Les comparaisons sont appariées sur les mêmes observations.

**Interprétation par branche :** le signal substantiel est l'identification
de D1 dans le bas du classement. À H20, la précision D1 atteint 35,94 %
contre 19,62 % pour le momentum. La branche D10 dans le haut n'apporte
aucun gain convaincant : elle est moins bonne que le momentum à H5 et H10,
et ne le dépasse que de 0,33 et 0,86 point à H15/H20. Les huit semestres
positifs concernent la *moyenne symétrique*, dominée par D1 ; ils ne
constituent pas huit validations de la branche D10. Même le classement modèle
place encore, à H20, **18,15 % de vrais D1 dans son haut** et **13,07 % de
vrais D10 dans son bas**. Une politique LONG D10 ou SHORT D1 n'est donc pas
validée par cette étude.

Les rendements moyens de prix des groupes LightGBM haut/bas sont
respectivement +1,17 %/−2,38 % à H20. Ils sont calculés sur des trajectoires
réalisées, sans coûts ni simulation des contraintes de négociation ; le
spread arithmétique +3,55 % **n'est pas un rendement de stratégie**.
L'hypothèse D1 pourrait inspirer un veto de risque sur les achats, mais
elle ne justifie pas à elle seule une vente à découvert réalisable sur CN_A.

## Sensibilité exploratoire : réversion plutôt que momentum

Après lecture des résultats, l'IC négatif du momentum relatif a motivé un
diagnostic **post-hoc** avec son score inversé, une baseline élémentaire de
réversion. Le calcul lit les prédictions OOS déjà sauvegardées, ne réentraîne
aucun modèle et ne modifie **pas** le gate pré-enregistré. Le
[rapport de sensibilité](../../artifacts/cn/ranking/sprint10c/posthoc_reversed_momentum_diagnostic.json)
est explicitement marqué `POST_HOC_DIAGNOSTIC_NOT_A_GATE`.

| Horizon | Précision symétrique modèle / réversion | D10 dans le haut modèle / réversion | D1 dans le bas modèle / réversion |
| --- | ---: | ---: | ---: |
| H5 | 26,10 % / 25,50 % | 16,04 % / 17,11 % | 36,16 % / 33,89 % |
| H10 | 25,93 % / 25,41 % | 15,46 % / 16,38 % | 36,41 % / 34,44 % |
| H15 | 25,88 % / 25,06 % | 15,25 % / 15,79 % | 36,51 % / 34,33 % |
| H20 | 25,49 % / 24,45 % | 15,04 % / 15,08 % | 35,94 % / 33,83 % |

Ainsi, l'avantage symétrique sur cette baseline plus pertinente se réduit
à **0,5–1,0 point**, et la réversion fait légèrement mieux sur D10 à tous
les horizons. Comme elle a été choisie en voyant les résultats, on ne peut
ni la déclarer gagnante par un test confirmatoire sur ces mêmes données, ni
ignorer la fragilité qu'elle révèle. La conclusion opérationnelle est donc
**NO-GO promotion en serving et NO-GO signal LONG autonome**, malgré le
`GO_RESEARCH_ONLY` face à la baseline pré-enregistrée.

Avant une nouvelle décision, il faut pré-enregistrer la réversion parmi
les baselines, obtenir des dates CN indépendantes de cette campagne et
tester séparément D10, D1/veto et les contraintes d'exécution. Aucun
backtest portefeuille ni aucun flux live n'a été modifié par le Sprint 10-C.

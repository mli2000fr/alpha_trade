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

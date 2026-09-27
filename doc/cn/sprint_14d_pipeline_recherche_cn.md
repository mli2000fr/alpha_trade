# Sprint 14-D — Pipeline CN_A de recherche

État au 27 septembre 2026 : l'écran Pipeline permet de lancer **un fold Oracle ou Global Ranking CN_A à la fois**. Il entraîne le modèle sélectionné sur la fenêtre antérieure du protocole gelé, puis écrit ses prédictions hors échantillon (OOS) pour un semestre 2022–2025. Il ne s'agit pas d'un entraînement de modèle de production ni d'une prédiction future.

## Chemin opérateur

1. Dans Pipeline, choisir le marché **CN_A — recherche uniquement**. Les contrôles et commandes US disparaissent.
2. Choisir `oracle` ou `ranking`, H5/H10/H15/H20, un semestre OOS inscrit dans le protocole et `lightgbm` ou `catboost`.
3. Vérifier la commande affichée puis lancer le fold. Les journaux et l'historique sont séparés des runs US.
4. Le suivi se rafraîchit toutes les 5 secondes ; le journal affiche immédiatement le démarrage, puis un signal de vie environ toutes les 30 secondes. La barre indique des **jalons observés**, et non un pourcentage du temps ou une estimation de fin.
5. Après `COMPLETED`, ouvrir le rapport et les prédictions dans le répertoire propre à ce run. `COMPLETED` signifie que le calcul a abouti, **pas** que la qualité OOS est suffisante ni qu'un déploiement est autorisé. Comparer aux agrégats pré-enregistrés dans Diagnostic ML.

Le chemin effectif est `Pipeline CN_A → préflight → ihm.services.cn_fold_worker → modelFactory.cn_oracle_walk_forward` ou `modelFactory.cn_global_ranking_walk_forward → model + predictions.parquet + report.json`. Le worker ne modifie pas les algorithmes gelés : il émet seulement les signaux de vie et jalons visibles dans le journal. Les sorties vont sous `artifacts/ihm_pipeline_runs/cn-research-fold/<id>/artifacts/` ; un nouveau lancement ne réécrit pas les artefacts de la campagne historique. Aucun modèle n'est promu au serving, aucune ligne de prédiction n'est insérée en base et aucun ordre n'est envoyé.

## Contrat de données et de séparation

- Marché exigé : `CN_A` ; alias exigé : `cn_primary` ; la route doit viser `alpha_trade_cn`. Ces modules de fold lisent les artefacts de recherche CN, sans connexion SQL ni écriture en base lors du lancement.
- Le protocole Oracle est `config/research_cn/sprint10b_oracle.yaml` ; celui du Ranking est `config/research_cn/sprint10c_global_ranking.yaml`. Le formulaire lit les horizons, semestres et modèles de ces protocoles ; il ne permet pas de saisir un univers ou des options US arbitraires.
- Le préflight Oracle contrôle l'audit des labels, le code producteur et les hashes des panels/labels CN 2018–2025. Si la provenance a changé, le lancement échoue fermé.
- Le préflight Ranking ajoute la présence et l'intégrité des **deux** prédictions Oracle OOS de campagne pour le même horizon/semestre, issues des modèles LightGBM et CatBoost. Le Ranking calcule son TOP20 sur leur moyenne, sans sélectionner les extrêmes sur les labels futurs.
- Un seul fold CN géré par cette page peut être en cours. Son historique est filtré par la clé `cn:research_fold`. Le bouton Arrêter concerne uniquement ce run.
- Le modèle et les prédictions produites restent dans un dossier propre à la page. Ils ne remplacent ni le batch canonique CN de recherche, ni les batchs US, ni les fichiers consommés par le replay Sprint 14-C.

## Limites explicites et prochain gate

Il n'existe pas encore de commande CN de **prédiction future** indépendante des folds OOS. Le formulaire ne l'invente pas. La période maximale testable par ces commandes est 2025H2 ; les labels du semestre test servent seulement à l'évaluation, jamais à l'entraînement de ce fold. Pour ouvrir une prédiction future, il faudra un contrat distinct : entraînement final gelé, registre de modèles servables, date d'arrêt des features PIT, contrôle de maturité des labels, batch de prédiction sans labels futurs, écriture CN dédiée et validation OOS non inspectée. Le statut économique Sprint 13-C reste `NO_PRODUCTION_GO_INSPECTED_OOS` ; pas de trading live CN.

## Vérification

Tests ciblés : `tests/test_sprint14d_cn_fold_ui.py` et `tests/test_sprint14c_cn_replay_ui.py`. Ils couvrent notamment la route CN, les paramètres hors protocole, les sorties confinées, la dépendance Oracle du Ranking et l'interdiction d'un lancement CN concurrent. Aucun entraînement lourd n'est déclenché automatiquement par ces tests.

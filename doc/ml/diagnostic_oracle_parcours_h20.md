# Diagnostic ML — Oracle Extreme parcours H20

Adaptation du **15 octobre 2026**. Page **Analyse & Recherche → Diagnostic ML**,
marché US. Aucun entraînement, backfill de prédictions, calcul de label ou ordre
n'est déclenché par l'ouverture de cette vue.

## Anomalie corrigée

Le détecteur historique reconnaissait `enable_oracle_model`, pas
`oracle_path_model_only`. Les trois modèles parcours avaient déjà des scores
dans `oracle_extreme_predictions`, mais la page les déclarait sans période
Oracle et affichait des blocs Global Ranking/per-symbol sans rapport avec leur
contrat. Les métadonnées sous forme de dictionnaire étaient aussi mal décodées.

La page reconnaît maintenant les métadonnées CLI/config et les artefacts
`<batch>/oracle_path/protocol.json`, y compris dans une racine d'artefacts
personnalisée. Le tableau des batches distingue **Parcours H20** des autres.
Un modèle parcours incomplet/corrompu reste dans sa vue propre, avec une erreur
ou une progression : il ne retombe pas silencieusement sur le diagnostic terminal.

## Périodes : deux sources séparées

Le bouton **« Périodes de prédictions du batch »** et la vue dédiée présentent :

| Source | Signification |
| --- | --- |
| Prédictions SQL | Dates réellement persistées pour ce `batch_id` dans `oracle_extreme_predictions`. Elles ne constituent pas à elles seules une évaluation sur des mouvements futurs arrivés à maturité. |
| Tests OOF du training | Dates effectivement présentes dans les fichiers `oracle_path/folds/*/oof.parquet`, issus des fenêtres test Walk-Forward. Ce ne sont pas les bornes générales de training ni une promesse de couverture SQL. |

Chaque ligne indique première/dernière date, séances distinctes, symboles et
nombre de lignes. Les deux périodes ne sont jamais fusionnées. Une agrégation
SQL vide ne devient plus `NaT → NaT`. Une table/connexion manquante est signalée,
pas assimilée à un modèle non entraîné.

La filiation SQL est contrôlée par date/symbole/batch, fold, empreinte des poids,
profil, cible `oracle_path_extreme20`, horizon 20 et disponibilité exacte du modèle
avant la décision. Les champs terminaux de ces scores doivent rester NULL.
Une discordance affiche une erreur plutôt qu'une qualification de serving.
Cette vérification ne recalcule pas les features ni le score de chaque ligne.

Les deux agrégations SQL utilisent un instantané `REPEATABLE READ` cohérent,
important pendant une prédiction écrivant par tranches. Elles ne sont pas mises
en cache cinq minutes. Rafraîchir la page ou cliquer de nouveau pour voir
l'avancement ; le lecteur ne modifie pas les jobs en cours.

## Métriques et rapport propres au parcours

La cible reste le **TOP20 % de l'amplitude absolue maximale entre J+1 et J+20**
depuis le close ajusté J, hausse ou baisse, et non le rendement final de J20.
L'interface affiche :

- AUC OOF d'amplitude et précision du TOP20 % prédit ;
- proportion du véritable TOP20 % parmi les **10, 20 et 50 premiers titres** ;
- amplitude maximale réalisée moyenne de ces sélections ;
- nombre de folds et de features, choix LightGBM/CatBoost/automatique ;
- détail des folds test et du champion de chacun ;
- comparaison OOF des deux algorithmes si les deux figurent au rapport ;
- couverture, exclusions de trajectoires et liste des features.

Les proportions de précision sont des fractions affichées en pourcentage ; les
amplitudes archivées sont déjà en points de pourcentage. Ne pas les multiplier
une deuxième fois par 100. **10 titres ne signifie pas TOP10 %.**

Les métriques proviennent du rapport d'entraînement, après contrôle du contrat,
du profil, des poids, des fichiers OOF et de leur couverture. Les disponibilités
train/validation doivent précéder les fenêtres suivantes. Les périodes OOF sont
lues dans les données, pas inventées depuis `test_start/test_end`.

Le téléchargement propose le **rapport Oracle parcours**, sans générer le rapport
historique terminal. Les blocs Global Ranking, F1 per-symbol, répartition D1/D10
terminale et bouton de construction des anciens labels ne sont pas exécutés pour
ce modèle. Les vues historiques et le bundle LONG/SHORT conservent leur chemin.

**Une amplitude maximale n'est pas un gain réalisable.** Ce modèle n'apprend pas
LONG/SHORT. Sa précision n'est pas le taux de trades gagnants. La vue rappelle
aussi le biais d'univers statique et les réserves sur les prix ajustés actuels.

## Chargement et validation

Le contrôle des artefacts est mis en cache deux minutes, avec une clé comprenant
tailles/horodatages du protocole, profil, rapport, progression, poids et OOF de
chaque fold. Un changement de fichier invalide ce cache. Aucune matrice complète
de features ni recalcul de modèle n'est requis pour afficher les périodes.

**66 tests ciblés réussis**, comprenant un test Streamlit de la page, clic du
bouton des périodes, absence d'appels aux diagnostics terminaux, cas vides,
artefacts corrompus, schéma OOF incorrect, connexion/filiation manquante et
non-régression des anciens diagnostics et du serving LightGBM/CatBoost.

Vérification en lecture seule sur les trois campagnes
`model-factory-20261014113215-437ed1`, `model-factory-20261014113226-102eca` et
`model-factory-20261014113232-bc35a7` : **14 folds, 173 features**, périodes SQL
et OOF retrouvées, filiation des scores SQL cohérente à l'instant du contrôle.
Les périodes SQL peuvent continuer à grandir si un autre job prédit en parallèle.
Preuve datée : `artifacts/research/oracle_path_diagnostics/20261015-v1/report.json`.

Sources : `ihm/pages/ml_diagnostics.py`,
`ihm/services/oracle_path_diagnostics.py`,
`ihm/components/oracle_path_diagnostics.py` et
`tests/test_oracle_path_diagnostics.py`. Aucun modèle, score, label, réglage de
risque, batch ou table n'a été modifié par cette correction d'affichage.

## Bundle parcours + per-symbol — 6 novembre 2026

La page affiche désormais un bloc **Modèles per-symbol LONG / SHORT** pour
les bundles compatibles. Ces branches sont stockées sous
`oracle_path/directional/manifest.json` et ne doivent pas être cherchées
uniquement dans le registre SQL des anciens modèles per-symbol.

Après validation du contrat et des SHA-256 de tous les poids, le bloc expose :

- nombres de modèles LONG et SHORT (un modèle par titre, année et direction) ;
- couverture et titres absents par année d'utilisation ;
- détail des dates d'entraînement/calibration, nombre d'observations, fichiers
  et empreintes, filtrable par année/direction et téléchargeable en CSV ;
- motifs de non-entraînement, regroupés par année/direction et exportables.

Le manifeste et les poids directionnels participent à l'invalidation du cache.
Des compteurs de rapport différents du manifeste vérifié invalident la vue.
La page ne désérialise pas les poids et ne calcule aucune nouvelle performance.
La première correction ne disposait pas d'AUC par titre : les compteurs ne
sont pas une mesure de fiabilité directionnelle. Le complément suivant ajoute
ces mesures, avec séparation explicite des jeux d'évaluation.

Contrôle réel de `model-factory-20261106203103-91b063` : **6 588 poids présents,
zéro manquant**, soit 3 294 LONG et 3 294 SHORT. Couverture par direction :
**1 595 titres en 2024**, **1 699 en 2025**, sur 1 790 ; aucun modèle qualifié
2020–2023, pour insuffisance d'historique/classes selon les critères gelés.
Le compteur global « 1 terminé » concerne le bundle entier, pas un seul titre.
Le chargement du vrai batch dans la vue corrigée réussit ; **27 tests ciblés**
passent, dont affichage Streamlit, modèles manquants/corrompus et compteurs.

Preuve du contrôle :
`artifacts/operations/ml_training_bundle_audit/model-factory-20261106203103-91b063/20261106-v1/report.json`.

## Métriques et périodes per-symbol — complément du 6 novembre 2026

La section per-symbol propose désormais AUC, exactitude au seuil 0,5,
exactitude équilibrée, précision parmi les scores ≥0,5, fréquence positive
des labels et Brier. Les jeux **entraînement**, **calibration**, **test hors
échantillon** et **test sans chevauchement** restent distincts. L'entraînement
et la calibration ne constituent pas des tests indépendants. Une AUC non
calculable (jeu vide ou une seule classe) reste vide.

Le label est le résultat net de la stratégie propre à la branche : ouverture
J+1, SL du contrat (5 % pour ce batch), sans TP/trailing, sortie open11.
L'exactitude au seuil 0,5 n'est pas le taux gagnant du portefeuille Winner,
ni l'évaluation du futur filtre TOP10 % Oracle. La phase sans chevauchement
est fixée sur l'indice du calendrier global modulo11 ; ses échantillons
annuels par titre sont petits et ne certifient pas un avantage stable.

Les prochains entraînements conservent automatiquement ces diagnostics par
modèle, les prédictions test et une copie du benchmark utilisé. Pour un ancien
batch, `modelFactory.oracle_path.evaluate_directional` reconstruit les mesures
sans `.fit`, ordre, replay de portefeuille, téléchargement ou écriture SQL.
Les barres des titres sont les chunks d'origine vérifiés par SHA-256 ; les
poids et leurs dates sont conservés. Si le benchmark d'origine n'était pas
archivé, SPY est relu en SQL, figé dans le diagnostic et cette limite est
affichée. Cela ne certifie pas une disponibilité historique PIT des révisions.

Complément réellement terminé pour `model-factory-20261106203103-91b063` :

- 6 588 modèles évalués sur leurs jeux disponibles, 1 790 titres examinés ;
- test 2024 : **1 594 titres par direction**, 241 séances du 02/01/2024 au
  13/12/2024, 384 111 observations LONG et autant SHORT ;
- `KYOCY` possède des modèles 2024 mais aucune observation de test qualifiée ;
- aucun test 2025 dans ces archives arrêtées fin 2024, malgré les modèles
  annuels destinés à 2025 ; aucune performance 2025 n'est inventée ;
- AUC médiane par titre en test 2024, toutes fenêtres : LONG **0,50167**,
  SHORT **0,50661** ; sans chevauchement : **0,50000 / 0,50427**. Ce diagnostic
  porte sur les historiques des titres, sans conditionnement au TOP Oracle.

Les résultats sont sous `oracle_path/directional/diagnostics/report.json`,
avec benchmark, progress et fichiers `oos-*.parquet`. Le manifeste de training
et les poids d'origine ne sont pas modifiés. La page valide les liens vers
le protocole/manifeste, les modèles et les empreintes des fichiers de test.
Les résultats incohérents ne sont pas affichés comme qualifiés.

Dans **Périodes de prédictions du batch**, les lignes per-symbol LONG et
SHORT en SQL sont affichées même quand elles sont vides, avec un motif clair.
Les scores NULL ne comptent pas comme des prédictions. Les tests per-symbol
ont leurs propres lignes, séparées de l'OOF Oracle et des scores SQL servis.
Pour ce batch, les deux tables SQL de prédiction sont encore vides : aucun
ML Predict n'a été lancé par cette réparation.

Vérification : **53 tests ciblés réussis**, reconstruction réelle terminée en
252 secondes et affichage Streamlit vérifié avec les vraies données LONG/SHORT.
Preuves complémentaires dans le dossier d'audit du batch :
`metrics-tests.xml`, `enriched-periods.json`, `metrics-summary.json` et
`enriched-streamlit-validation.json`.

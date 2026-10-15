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

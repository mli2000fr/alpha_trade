# Oracle Extreme parcours : choix H10 / H15 / H20

Évolution du 30 octobre 2026. La page Pipeline permet maintenant de choisir
l'horizon du modèle parcours, à côté du choix LightGBM / CatBoost / automatique.

## Depuis la page Pipeline

1. Cocher **🔮 Oracle Extreme parcours — modèle séparé**.
2. Choisir **Horizon — Oracle Extreme parcours** : H10, H15 ou H20.
3. Choisir l'algorithme, l'univers et les dates d'entraînement.
4. Lancer **9. ML Train**. Chaque horizon nécessite son propre modèle et un
   nouveau batch : un modèle H20 existant ne devient pas H10 en changeant le menu.
5. Dans **10. ML Predict**, sélectionner le batch entraîné correspondant.
   La prédiction lit l'horizon dans le contrat de ce modèle. Elle n'utilise pas
   un menu d'entraînement conservé dans la session pour réinterpréter ses poids.

Le filtre options utilise toujours le modèle désigné par sa configuration et
le batch `us_pipeline` conserve `options_directional_filter.default_oracle_batch_id`.
Le simple choix d'un nouvel horizon d'entraînement ne remplace pas ce batch
de production. Pour utiliser un nouveau modèle dans le batch, il faut ensuite
y renseigner explicitement son nouvel identifiant.

## Ce que signifie l'horizon

Un seul classifieur d'amplitude, sans direction apprise : identifier le véritable
TOP20 % des maxima absolus de mouvement sur **toute** la fenêtre future, depuis
le cours ajusté de clôture J.

| Modèle | Fenêtre de la cible | Disponibilité conservatrice du label |
|---|---|---|
| H10 | HIGH/LOW de J+1 à J+10 | J+11 |
| H15 | HIGH/LOW de J+1 à J+15 | J+16 |
| H20 | HIGH/LOW de J+1 à J+20 | J+21 |

Les indices J+n désignent des séances officielles, pas des jours calendaires.
Un pic atteint dès J+3 ne rend pas le label disponible avant la fin de sa
fenêtre. Les folds walk-forward et leur purge utilisent l'horizon sélectionné ;
les dates de disponibilité restent strictement antérieures aux validations/tests.
Les contrôles de couverture, prix, identité et provenance restent en place.

Ce n'est ni le rendement du seul dernier jour, ni une cible TP avant SL.
Les maxima réalisés ne sont pas des gains de trading garantis ou capturés.

**La détention Winner reste indépendante.** Choisir Oracle H10 ne change pas
`winner_pyramiding.horizon_sessions: 20` et ne vend pas automatiquement après dix
séances. La sortie Winner continue de suivre son contrat figé à l'entrée.

## Configuration et commandes

```yaml
oracle_path:
  horizon: 20  # 10, 15 ou 20 ; défaut de l'IHM et du CLI en entraînement.
  training_backend: auto
```

Le choix fait dans l'IHM est transmis explicitement par `--oracle-horizon`.
Extrait de commande d'entraînement :

```text
--oracle-path-model-only --oracle-horizon 10 --oracle-path-backend lightgbm
```

Le CLI sans horizon explicite en mode parcours utilise `oracle_path.horizon`.
ML Predict sans horizon explicite utilise celui de l'artefact choisi. Une demande
explicite incompatible est refusée avant lecture des features et écriture des scores.

## Contrats et compatibilité

Les modèles restent sous `artifacts/models/<batch>/oracle_path/`, avec cibles
distinctes `oracle_path_extreme10/15/20`, modes `oracle_path_h10/h15/h20`, protocole
signé, profils et checkpoints isolés. Un changement d'horizon interdit la reprise
d'un batch existant. La sélection de l'algorithme est inchangée.

Les constantes et paramètres historiques par défaut restent H20 pour les anciens
appels et scripts de recherche. Les artefacts H20 existants restent lisibles,
sans réécriture de leurs fichiers ni migration de données.

Les prédictions utilisent toujours `oracle_extreme_predictions` et
`oracle_path_prediction_lineage`, dont les colonnes cible et horizon distinguent
les contrats par batch. Aucune nouvelle colonne SQL n'est nécessaire. Les labels
terminaux restent NULL pour les scores d'amplitude ; le lecteur vérifie la
filiation contre le contrat exact, y compris au risque et au replay Winner.
Le filtre options et les diagnostics reprennent aussi ce contrat, sans accepter
une ligne H20 pour un modèle H10 ou inversement.

## Vérification

Tests locaux sur données synthétiques : vrais petits entraînements LightGBM
H10/H15/H20, limites de fenêtre et maturité J+H+1, folds causaux, lecture des
artefacts, prédiction et cible/horizon de la filiation, refus de mélange et de
reprise incompatible. Tests Streamlit : sélection des trois horizons et commande
générée. Tests existants LightGBM/CatBoost/automatique et H20 conservés.

Aucun entraînement de production, backtest économique, téléchargement fournisseur,
ordre ou migration SQL n'a été lancé par cette évolution. Le modèle H20 actuel
du filtre options n'a pas été remplacé.

### Correctif de lecture des sources daily — 30 octobre, run H10

Le premier run `model-factory-20261030212542-b7329f` (2019-01-01 à 2026-10-29)
s'est arrêté sur `Duplicate price dates: A`, avant tout checkpoint de tranche.
Certaines séances d'octobre contiennent une ligne EODHD et une ligne SIP.
Le lecteur des features appliquait déjà la priorité de source configurée,
mais `oracle_path.labels.load_bars` lisait les deux lignes pour les cibles.

Le lecteur des cibles utilise désormais `common.daily_bar_sources.select_daily_bars`
avant calcul et archivage : ligne complète du fournisseur préféré, alternative
uniquement en l'absence du préféré. Aucun mélange OHLC/volume, remplissage ou
suppression en base ; les doublons internes à un fournisseur restent refusés.
Les contrôles de stabilité d'identité/provenance et de qualité des parcours
sont conservés.

Vérification en lecture seule des 25 premiers titres de ce run : 48 322 lignes
uniques et 47 808 parcours qualifiés H10 ; aucun doublon date/titre. Pour A,
1 959 lignes EODHD et 9 lignes SIP complémentaires. **43 tests réussis**, dont
quatre régressions de source, les horizons et les tests historiques du parcours.
L'entraînement de production n'a pas été relancé pendant ce contrôle.

### Dates du bouton de prédiction historique — 30 octobre

Le run H10 terminé `model-factory-20261030213826-eda503` a été entraîné sur
2019-01-01–2026-10-29. Son premier fold causal est daté du **2 juillet 2021**,
avec labels de training disponibles au 30 décembre 2020 et de validation au
1er juillet 2021. Prédire dès janvier 2019 avec ce fold serait anticipatif.

Le bouton historique reprenait les dates globales du training. Il affiche
désormais deux dates propres à la prédiction des modèles parcours, conservées
par modèle, et propose un début au moins égal au premier fold causal. Les
choix ultérieurs sont conservés et la plage effectivement demandée est visible
dans la commande. Les dates T1 ne sont pas changées. L'auto-détection est résolue
avant ce contrôle et le batch correspondant est fixé dans la commande.

Une plage inversée ou un contrat invalide bloque le bouton. Le CLI ne tronque
pas silencieusement une plage explicite trop ancienne : il refuse toujours,
mais indique maintenant le début minimal compatible et la raison. Le sélecteur
de modèle historique affiche aussi le véritable badge H10/H15/H20.

113 tests réussis : bornes des folds, absence d'inférence avant disponibilité,
dates de prédiction indépendantes du training, conservation du choix manuel,
auto-détection, vrais widgets Streamlit et régressions de la page Pipeline.
Le modèle réel a été relu pour confirmer le 2 juillet 2021. Aucune nouvelle
prédiction SQL ni aucun réentraînement n'a été lancé par cette correction.

### Raccordement Winner — 31 octobre

La page Backtesting propose désormais le formulaire Winner dédié : Oracle
parcours H10/H15/H20, TOP-N, capital, frais et levier, mêmes règles Winner
de confirmation et de détention. Les rapports sont lisibles dans l'IHM.
Le filtre CALL/PUT + OI du pipeline est désormais proposé et activé selon
la configuration ; aucune OI historique n'est inventée. Le délai SIP configuré
de quinze minutes est reproduit sur les signaux et les achats, au prix ultérieur.
Le replay reprend les contrôles natifs avec observations factorielles réellement
archivées ; aucun historique PIT n'est inventé et les manques sont visibles.
Le chemin d'exécution/watcher existant a été vérifié par tests simulés ;
les restrictions PAPER des filtres options/LLM restent en place.
[Mode d'emploi et limites](../operations/winner_backtest_live_20261031.md).

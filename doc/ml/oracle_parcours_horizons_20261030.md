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

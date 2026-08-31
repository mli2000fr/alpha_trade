# Qualité, couverture et fallbacks ML

## Objet

La couverture mesure la part de la population/date pour laquelle le système peut
produire ou retrouver une prédiction admissible. Elle doit être distinguée de
la performance du modèle et de la disponibilité d’un fichier d’artefact.

## Niveaux de couverture

```text
univers PIT
 → lignes possédant les données/features requises
 → symboles/horizons couverts par un artefact compatible
 → prédictions calculées sans erreur
 → prédictions disponibles à l'as-of
 → prédictions effectivement consommées après gates/fallbacks
```

Un taux global peut cacher des trous concentrés sur un secteur, une période ou
les nouveaux entrants. Les diagnostics doivent donc fournir dénominateur,
numérateur, dates manquantes et exemples de lignes.

## Sources de manque

- univers historique incomplet ou résolution PIT impossible ;
- historique de prix/features trop court ;
- date de publication postérieure à l’as-of ;
- artefact absent, illisible ou incompatible avec les features ;
- modèle per-symbol indisponible et fallback global non autorisé ;
- gate drift/qualité fermé ;
- erreur de prédiction ou d’écriture DB ;
- batch demandé ne contenant pas la famille attendue.

## Fallbacks

Un fallback est une politique métier explicite, pas une réparation silencieuse.
Selon la chaîne, il peut choisir un modèle global, une composante non-ML, une
valeur neutre ou bloquer la sélection. Chaque sortie doit conserver le mode de
sélection et le modèle réellement servi.

L’ordre de fallback doit être documenté et testé. Un fallback améliore la
disponibilité mais peut modifier la distribution et rendre une comparaison de
performance hétérogène.

## Gates de couverture

Le backtesting diagnostique la couverture de `model_predictions` et peut exiger
un ratio minimal. En production, les gates doivent éviter qu’un portefeuille
soit construit sur un sous-univers accidentel. Le seuil seul ne suffit pas : une
couverture de 90 % peut être inacceptable si les 10 % absents sont un secteur
entier.

## Audit recommandé

Pour chaque batch et période : couverture par jour, symbole, secteur, horizon et
mode servi ; âge des prédictions ; raisons de manque ; taux de fallback ; part
des candidats sélectionnés affectée. Comparer train, backtest et production
avec le même dénominateur.

Voir [features et labels](features_et_labels.md),
[orchestration](orchestration_train_predict.md) et
[guide ML](../guide_utilisateur/05_ml_predictions.md).


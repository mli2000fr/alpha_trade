# Capital, sizing, levier et fractionnement

## Du risque unitaire à la cible

Le sizing combine capital/equity, risque accepté, distance au stop, volatilité,
conviction, limites de position/secteur/portefeuille et capacités du compte.
Chaque plafond peut réduire la taille issue de la formule précédente.

## Petit capital

Avec un petit capital, le fractionnement réduit l’erreur d’arrondi mais ne
supprime ni minimum broker, liquidité, coûts fixes, concentration ni buying
power. Les anciens scénarios « 2000 EUR » sont des exemples historiques et non
des valeurs actives ou recommandations.

## Levier

Le levier augmente exposition, drawdown potentiel et sensibilité aux gaps. Il
doit être plafonné par les règles de portefeuille et compatible avec le compte.
Une stratégie profitable sans levier ne justifie pas automatiquement le levier
maximal ; analyser stress, séquence de pertes et appels de marge.

## Fractional trading

Les préférences peuvent distinguer backtest et exécution. La simulation doit
reproduire arrondis et minimums du contexte testé. En production, contrôler les
contraintes réellement appliquées dans la page Exécution.

Voir [sizing et levier](sizing_et_levier.md),
[contraintes portefeuille](contraintes_portefeuille.md) et
[guide Risk](../guide_utilisateur/06_risque.md).


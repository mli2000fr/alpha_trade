# Fondamentaux

## Sources et capitalisation : contrats distincts

La page historique concerne principalement les fondamentaux US. Le batch
market_cap_sync est composite SEC primaire puis Yahoo/Finnhub en fallback.
La commande modelFactory.fundamental_features --provider sec reconstruit les
faits/features SEC : ce n'est pas une simple collecte de market cap actuelle
sur une fenêtre J−10/J. Publication, disponibilité et prix doivent être alignés.
La collecte n'impose pas le filtre : market_cap.policy=liquidity_only actuellement.

FR INPI et consensus Yahoo sont suspendus pour droits/prudence ; leur ancien
corpus/quarantaine n'est pas un feu vert ML. Une page générique n'autorise pas
l'import US dans alpha_trade_fr. [Catalogue](../operations/catalogue_batchs_actuel.md).

La page affiche couverture, symboles éligibles, dernière mise à jour et providers. Elle peut prévisualiser puis lancer un fetch par univers/provider avec option overwrite, suivre les logs et arrêter le traitement.

Toujours prévisualiser l’univers et le quota. `overwrite` ne corrige pas automatiquement une convention ou une date de disponibilité erronée. Après le run, contrôler mis à jour/échecs, provider, fraîcheur et logs téléchargeables.

Les onglets détaillent symboles, distributions sectorielles et recherche. PE, ROE, croissance et capitalisation demandent des conventions homogènes. Pour ML/backtest, utiliser la date où l’information était disponible, pas seulement la période financière. Une valeur affichée aujourd’hui peut avoir été révisée.

Une absence de ligne peut signifier symbole non éligible, provider indisponible, TTL encore valide ou échec. Diagnostiquer avant de remplir par une valeur neutre.


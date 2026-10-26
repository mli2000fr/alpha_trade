# Audit des pertes : correction de l'horloge intrabar

23 octobre2026. Le contrôle du nouveau test SL3/TP7/TR3 montre une erreur dans
l'interprétation de l'audit descriptif v1 : le moteur natif inscrit une sortie
STOP intrabar à la FIN de la bougie, pas à son début. La courbe et les PnL
historiques n'ont pas changé ; les diagnostics MFE/post-stop doivent être
recalculés avec cette convention, avant toute interprétation.

V1 conservée immuable mais remplacée par
`artifacts/research/us_winner_loss_diagnostics/20261023-v2`. Adaptateur distinct,
pas de modification des scripts/sources historiques scellés, ni du moteur live.
Les sondes d'entrée restent identiques : elles ne lisent aucun prix futur.

Pour STOP : MFE/MAE certains excluent la bougie dont la FIN égale l'heure de
sortie. Cette bougie seule fournit la borne supérieure ambiguë. Les deux
clôtures d'un faux départ doivent être strictement antérieures à une sortie
intrabar. La première bougie entièrement post-stop COMMENCE à l'heure de sortie,
pas cinq minutes plus tard. Le délai est mesuré depuis l'heure réelle inscrite.
Pour STOP_GAP/HORIZON_OPEN : convention d'ouverture inchangée, pas de high futur.

Seules ces bornes/observations rétrospectives changent. Même126pertes,173clôtures,
179achats, six ouverts, mêmesR=7 %, catégories, features, filtre de couverture,
coûts et limitesPIT/OST. Contrôle scalaire séparé corrigé ; pas de nouvelle règle,
optimisation de seuil, entraînement, backtest économique, SQL ou téléchargement.

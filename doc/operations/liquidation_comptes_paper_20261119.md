# Liquidation des trois comptes PAPER — 19 novembre 2026

Demande explicite : vendre tous les titres de tous les comptes pour repartir
sans position. Aucune remise à zéro du solde monétaire ou suppression de
l'historique n'a été réalisée.

Comptes vérifiés dans le registre : `default`, `test1`, `test2`, tous PAPER.
La liquidation a été conduite sous les verrous canoniques des trois comptes.

| Compte | Vente supplémentaire demandée | Quantité | Prix moyen USD | Confirmation broker |
| --- | --- | ---: | ---: | --- |
| default | Aucune position restante | — | — | Positions vides |
| test1 | ASX | 8 | 30,55875 | filled, 2026-11-19T20:57:04.158211149Z |
| test1 | IONS | 101 | 27,21 | filled, 2026-11-19T20:57:07.769147877Z |
| test2 | Aucune position restante | — | — | Positions vides |

Les stops ont été annulés et leur statut terminal confirmé avant les ventes.
Les sorties market DAY ont été réservées puis journalisées dans l'OMS natif,
avec des identifiants stables et sans répétition aveugle des soumissions.
Les deux plans détenus sont CLOSED après réconciliation des remplissages.
Les autres plans actifs sans position ont été annulés afin d'empêcher leurs
achats différés. Deux anciens intents UNKNOWN restent conservés dans
l'historique des plans terminaux : la recherche par identifiant broker ne
retrouve aucun ordre et aucune position ne leur correspond. Aucun statut
broker fictif n'a été écrit pour ces intentions historiques.

Le premier passage a été suspendu avant vente pour examiner ces intentions
anciennes. Après les ventes, une liste broker momentanément retardée montrait
encore IONS partiellement rempli, tandis que la lecture exacte de l'ordre
confirmait les 101 vendus. Le contrôle final utilise les réponses par
identifiant exact. Aucune deuxième vente du même lot n'a été soumise.

État final confirmé des **trois** comptes : aucune position, aucun ordre ouvert,
aucune campagne Winner active. Les services de protection et la configuration
des futurs batchs restent en place ; cette action ne désactive pas les futurs
cycles de trading.

Reçus conservés :

- `artifacts/operations/user_flatten_all_paper/20261119-final/test1-after.json` :
  les identifiants et prix des deux ventes exécutées ;
- `artifacts/operations/user_flatten_all_paper/20261119-verified/report.json` :
  contrôle final des trois comptes et des plans ;
- `artifacts/operations/q051_watcher_fix/20261119T202238Z/user-flat-verified.json` :
  contrôle indépendant après libération des verrous.

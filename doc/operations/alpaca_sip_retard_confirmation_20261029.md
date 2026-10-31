# Vérification SIP retardé — compte principal, 29 octobre 2026

Demande utilisateur : vérifier l'accès SIP avec quinze minutes de retard pour
envisager la confirmation Winner sans abonnement temps réel. Test fournisseur
en lecture seule, pendant la séance US. Aucune modification de configuration,
écriture SQL, sélection, ordre ou redémarrage de watcher.

Sept GET de l'endpoint `/v2/stocks/bars`, compte `default`, flux explicite `sip`,
bougies `5Min`, prix bruts, symboles AAPL/TXG/SDGR. Début du test :
2026-10-29 19:49:45 UTC, soit 20:49:45 Paris. Même fenêtre récente, seule la
borne `end` change à chaque requête. TLS vérifié ; aucun secret archivé.

| Âge de la borne de fin au départ de la requête | HTTP |
| --- | ---: |
| 0 | 403 |
| 14 minutes | 403 |
| 14 minutes 59 secondes | 403 |
| 15 minutes exactes | 403 |
| 15 minutes 1 seconde | 200 |
| 16 minutes | 200 |
| 20 minutes | 200 |

Message des refus : `subscription does not permit querying recent SIP data`.
Les requêtes acceptées contiennent des bougies sur les trois symboles, sans
pagination ni troncature. Le seuil observé est compatible avec une exclusion
des quinze dernières minutes ; ne pas promettre une frontière stable à la
seconde. Le temps de transport, l'horloge du serveur et la granularité de
l'en-tête HTTP Date ne permettent pas une mesure plus précise ici. Une marge
de requête de seize minutes est prudente ; un seul passage n'est pas une
garantie de disponibilité continue.

## Bougies terminées, et non simple timestamp de début

L'heure d'une bougie désigne son début. L'API renvoie aussi une dernière bougie
dont l'intervalle nominal se termine après la borne demandée. Cette dernière
ligne est exclue de l'interprétation ; elle n'est pas déclarée qualifiée
comme une bougie complète disponible au cutoff.

Pour les requêtes à 15 minutes 1 seconde et à 16 minutes, la dernière bougie
complète conservée couvre **20:25–20:30 Paris**. À réception vers 20:49:47,
sa fin a donc environ **19 minutes 47 secondes**. Les barres de cinq minutes
ajoutent un effet d'arrondi à la frontière des quinze minutes.

## Conséquence pour Winner

L'accès SIP retardé est confirmé sur ce compte. L'actuelle confirmation
Winner demande cependant des bougies terminées depuis au plus 60 secondes
et une quote récente avant une entrée confirmée. Ce test n'active ni ne
contourne ces contrôles.

Une variante retardée devrait disposer d'un cutoff d'observation distinct de
l'heure de décision/exécution, d'un lookback assez long pour deux confirmations,
et d'une politique de prix/ordre réellement exécutable à l'heure courante. Elle
ne doit pas acheter fictivement au prix de la bougie ancienne. Les signaux,
prix de la veille et barres de confirmation restent qualifiés au bon cutoff.
Le rendement de cette variante n'a pas été mesuré dans ce test d'accès.

Preuves :
`artifacts/operations/alpaca_sip_delay_probe/20261029T194945728629Z/report.json`
et réponses brutes par requête dans le même dossier.
Script : `scripts/operations/probe_alpaca_sip_delay_20261029.py`.

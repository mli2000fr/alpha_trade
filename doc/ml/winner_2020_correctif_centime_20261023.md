# Winner 2020 : écart d'un centime et reprise ciblée

Le 23 octobre 2026, le profil `SL5_TROFF_H5_TP20` s'arrête après 104 comptes
2020 terminés en x1 : audit scalaire 10,73 contre moteur 10,74. La tolérance
stricte reste inchangée. Aucun rapport terminé ni snapshot n'est remplacé.

## Diagnostic et correction bornée

Le runtime reconstitue le prix d'un fragment depuis le notionnel cumulé :
`(quantité * prix_moyen - notionnel_déjà_comptabilisé) / quantité_fragment`.
Même au premier fill intégral, cette opération peut transformer 11,30 en
11,300000000000002 (exemple : 12 actions). Le stop 5 % est alors arrondi à
10,74 au lieu des 10,73 obtenus par le contrat Python `round(11.3*.95,2)`.
Ce n'est pas une absence de bougie ni un assouplissement acceptable de l'audit.

Reproduction réelle : **CNK, 48 actions à 11,30 USD le 22 septembre 2020 à
15:15 UTC**. Prix reconstitué 11,300000000000002 ; sortie STOP le 23 septembre
à 15:20 UTC. TP identique 13,56 ; seul le stop diffère d'un centime. Les 104
comptes terminés contiennent 13 539 BUY_FILL, sans changement de niveau initial
SL/TP entre formule d'origine et conservation du prix réellement exécuté.

L'adaptateur versionné conserve exactement le prix moyen du broker pour un
premier fill intégral du replay IOC. Quantités, frais, calendrier, cash,
protections et formule d'arrondi restent natifs. Les fills partiels ne sont
pas qualifiés par ce correctif : refus explicite, pas de formule improvisée.
Les sources natives et les protocoles scellés utilisés par les autres runs
ne sont pas modifiés. Il s'agit d'un correctif process-local de recherche,
pas d'une modification déjà déployée au watcher de production.

Diagnostic réel, fills et trades sont conservés sous
`artifacts/research/us_winner_2020_cent_repair/20261023-v1/diagnosis`.
Validation isolée du profil défaillant sous `validation`, avant toute reprise.
Manifestes source et rapports conservés dans `amendment.json` et
`preserved-2020.json`. Tous les BUY_FILL antérieurs sont contrôlés, y compris
les positions encore ouvertes ; si leurs niveaux de protection changeraient,
la reprise conservatrice est refusée. Les rapports passés restent historiques.

## Reprise

Module `scripts.research.us_winner_2020_cent_repair_20261023`, phase `resume`.
Verrou annuel 2020 partagé avec le superviseur pour exclure un second worker.
Les comptes scellés sont vérifiés et sautés. Seuls les profils non terminés
sont rejoués, annotés avec le hash de l'amendement. Aucun ordre, appel API,
entraînement, écriture SQL ni nouvelle collecte.

Suivi de l'année dans le dossier original `year-2020.json`. Le superviseur
principal continue les autres années : son tableau `errors` peut conserver
l'incident historique même après la reprise externe. `resolution.json`
n'est créé qu'après 300 comptes 2020 validés. Un bilan global ne doit pas
ignorer une erreur sans ce reçu de résolution. L'erreur antérieure n'est pas
effacée et les échecs `failure.json` sont des traces historiques si un rapport
scellé a ensuite été produit.

Cette correction pourra concerner d'autres années/profils si le même cas
numérique survient ; ne pas déclarer les autres runs corrigés sans validation
et raccordement explicites. Une harmonisation native/live après les runs
scellés reste un chantier distinct.

# Résultats — entrée directe J+1 contre confirmation Winner, août2026

Quatre nouveaux comptes terminés et audités le25 octobre2026, sans nouvelle
collecte, SQL, GPT/DeepSeek, entraînement ou ordre réel.
[Protocole figé](gpt_veto_direct_open_aout_2026.md).

TOP20 d'août2026, même cohorte237/420, portefeuille4000USD partagé, demi-position,
cap1x, SL7 sans TP/trailing, sortie open21, frais8pb/jambe et risque natif.
L'entrée devient l'ouverture officielle J+1, sans cassure ni confirmation5m ;
aucune nouvelle tentative après refus à cette ouverture. Les protections et
le dimensionnement restent natifs. Ce n'est pas une comparaison passant
simultanément de demi-position à pleine position.

## Les quatre résultats directs

| Mesure | Sans veto | Veto1–3 | Veto1–4 | Veto1–5 |
| --- | ---: | ---: | ---: | ---: |
| Capital final USD | 3856,40 | 3831,55 | 3941,83 | 3933,41 |
| Rendement net | −3,59 % | −4,21 % | −1,45 % | −1,66 % |
| DD maximal5m | −13,85 % | −13,88 % | −11,16 % | −11,36 % |
| Achats et trades clôturés | 21 | 21 | 17 | 19 |
| Gagnants / perdants | 3 / 18 | 2 / 19 | 2 / 15 | 3 / 16 |
| Taux gagnant | 14,29 % | 9,52 % | 11,76 % | 15,79 % |
| PnL gagnants USD | +188,10 | +185,52 | +214,61 | +226,20 |
| PnL perdants USD | −331,71 | −353,97 | −272,78 | −292,79 |
| Solde net USD | −143,60 | −168,45 | −58,17 | −66,59 |
| Gain moyen gagnant USD | +62,70 | +92,76 | +107,30 | +75,40 |
| Perte moyenne perdante USD | −18,43 | −18,63 | −18,19 | −18,30 |
| Capital brut moyen utilisé USD | 1450,33 | 1377,43 | 1224,86 | 1289,41 |
| Frais USD | 9,03 | 8,98 | 7,41 | 8,13 |
| Positions ouvertes restantes | 0 | 0 | 0 | 0 |

Les PnL par trade incluent leurs frais. Ne pas soustraire une deuxième fois
la ligne frais du solde net. Les avis GPT invalides ou sans score restent
sans veto comme dans les témoins ; aucun achat SHORT.

## Comparaison à filtre identique

| Filtre | Rendement Winner confirmé | Rendement direct | Écart de capital direct moins Winner |
| --- | ---: | ---: | ---: |
| Sans veto | −1,45 % | −3,59 % | −85,66USD |
|1–3 | −1,45 % | −4,21 % | −110,51USD |
|1–4 | +0,49 % | −1,45 % | −77,61USD |
|1–5 | −0,78 % | −1,66 % | −35,40USD |

La suppression de la confirmation améliore légèrement les taux gagnants
clôturés, mais **pas le rendement dans ces quatre comptes**. Elle ne résout
donc pas le problème sur ce mois. Le veto1–4 reste le moins perdant des
nouveaux comptes directs ; aucun n'est bénéficiaire.

Attention à la censure : toutes les entrées directes J+1 ont eu le temps de
sortir avant fin septembre, alors que Winner conserve4–5 positions ouvertes.
Le capital final Winner comprend leur valorisation ; son taux gagnant ne
comprend pas ces positions non clôturées. La comparaison des seules fréquences
gagnantes ne permet pas d'établir une supériorité de l'entrée directe.

## Contrôles et portée

11 tests passent : ouverture exacte, garde des opérations, refus sans retry,
réadmission d'un signal récent, filtres identiques, stop dès la première
bougie et sortie open21.78 achats et78 sorties indépendamment contrôlés sur
les quatre comptes ; ce ne sont PAS78 paris indépendants, les comptes se
recouvrent. Cash, frais, stocks finaux, PnL et DD réconciliés, aucune lacune
de couverture admise. Sources et tous les fichiers vérifiés après calcul.
Les109 achats des témoins ne changent pas de niveau SL7 avec la convention
de prix moyen exact utilisée pour éviter les dérives binaires au centime.

Un mois précédemment observé, GPT rétrospectif non PIT, seuils testés après
résultats précédents, univers/secteurs actuels et couverture future J..J+40 :
résultat exploratoire non indépendant. Prix OHLC5m, pas preuve d'exécution
réelle à l'enchère d'ouverture. Aucun réglage de production modifié.

Rapport complet :
`artifacts/research/us_winner_gpt_veto_august_2026/20261025-direct-open-v1/report.json`.

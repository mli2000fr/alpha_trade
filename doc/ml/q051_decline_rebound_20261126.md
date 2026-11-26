# Q051 témoin TOP10 — baisse préalable puis début de reprise

## Protocole figé

Demande du 26 novembre 2026. Référence exacte :
`artifacts/research/us_q051_classic_top10/20261115-v1/cases/TOP10`, capital final
15 237,79 USD, +280,94 %, DD maximal intraday −40,45 %, 1 471 trades et 35,62 %
gagnants. Le témoin est intégralement rejoué avant de conclure sur le filtre.

Période 2021–1 octobre 2026, 4 000 USD continus, six modèles annuels causaux.
TOP10 % Oracle H10 (179/1 790) → TOP10 LONG per-symbol, score >0,50 et AUC de
calibration ≥0,50. Le nouveau filtre intervient **après** ce classement. Aucun
remplissage : un titre exclu ne fait pas entrer le onzième du classement.

Le filtre se calcule à la clôture J, sur les cours journaliers ajustés split
hérités de la référence. Vingt séances de baisse sont observées de J−22 à J−2 :
`close(J−2) / close(J−22) − 1 ≤ −10 %`. Les deux dernières séances servent à
observer la reprise, sans utiliser une nouvelle baisse après le signal Oracle.
Les 23 clôtures doivent être présentes et positives ; aucun remplissage des
données absentes. Le signal reste causal même si les cours après J changent.

Quatre cas, sans optimisation de seuil après observation :

| Cas | Règle supplémentaire | Sélections avant risque |
| --- | --- | ---: |
| REFERENCE | Aucune | 9 890 |
| DECLINE_ONLY | Baisse de 10 % sur les vingt séances finissant J−2 | 3 131 |
| REBOUND_1 | Baisse précédente et clôture J > clôture J−1 | 1 506 |
| **REBOUND_2 (principal)** | Baisse précédente, J−1 > J−2 et J > J−1 | **722** |

Aucune des 9 890 sélections ne manque d'historique pour ce calcul. Le dernier
signal de décembre appartient à l'année d'entrée suivante pour les comptages.
Les sélections ne sont pas les achats : risque, capital et positions déjà
détenues restent traités par le moteur natif.

## Conditions inchangées

Entrée à l'ouverture J+1, sans confirmation intraday, position complète et
actions entières. SL5 %, aucun TP, aucun trailing, dix séances détenues puis
sortie à l'ouverture de la onzième. Risque d'entrée 1,25 %, poids maximal20 %,
achats plafonnés1× avec capacité margin2×, 20 positions, ligne minimale50 USD,
frais8pb par achat et vente, financement inchangé. Sans B4/DD15, vol20, régime,
facteurs, corrélation, filtre options ou LLM. Même règles de répétition et de
blacklist que le témoin, mêmes dividendes et mêmes archives de prix.

Les seuls nouveaux champs de configuration absents de l'archive sont les deux
TIF PAPER (`paper_entry_time_in_force`, `paper_exit_time_in_force`). Aucun code
de backtest ne les utilise : leur absence de l'archive est explicitement admise,
sans changer un paramètre de simulation. Tous les champs historiques effectifs
sont comparés ; les 1 443 clôtures du compte témoin doivent être reproduites.

## Exécution et vérification

Pilote : `scripts/research/us_q051_decline_rebound_20261126.py`.
Archives : `artifacts/research/us_q051_decline_rebound/20261126-v2`.
La première préparation v1 n'a lancé aucune simulation : elle a refusé les
nouveaux TIF PAPER, initialement comparés à des champs inexistants dans l'archive.
Cette tentative et sa raison restent consignées séparément.

Suivi : `progress.json` global et `cases/<cas>/progress.json`. Les signaux,
indicateurs calculés, configurations, empreintes de sources et données,
comptes annuels, trades, frais et courbes sont conservés. Les résultats terminés
et validés sont inscrits dans l'historique de l'IHM.

Huit tests du filtre passent, dont invariance aux données futures, distinction
baisse/reprise, seuil inclusif, absence de remplissage et ordre original.
Les prix intraday sont revérifiés par empreinte à leur lecture. Chaque variante
rejoue le portefeuille complet, pas une suppression des trades de référence.

Aucun entraînement, nouvelle prédiction, téléchargement, appel LLM, écriture SQL,
ordre ou paramètre de production modifié. La période a déjà servi à beaucoup
d'expériences : le résultat reste exploratoire, même avec des modèles annuels
causaux. Univers rétrospectif et couverture 5m partielle/repli OHLC hérités.
Le calcul est revu par le même assistant ; aucune revue humaine indépendante.

Cette expérience diffère d'E10 (baisse **après** Oracle, entrée retardée openJ+2,
H20) et des anciennes règles de retour à la moyenne intraday : elle teste une
trajectoire **antérieure** au signal dans les TOP10 LONG de Q051 H10.

## Résultats

**TERMINÉ / CONTRÔLES PASS / NO_GO DE CES RÈGLES PAR RAPPORT AU TÉMOIN.**
Les 1 443 clôtures du témoin et les 1 471 trades (titres, dates, quantités,
prix, frais et P&L) sont reproduits, avec zéro écart de capital.

| Variante | Capital final USD | Rendement | DD max intraday | Trades | Gagnants | Exposition moyenne |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q051 témoin TOP10 | 15 237,79 | +280,94 % | −40,45 % | 1 471 | 35,62 % | 88,72 % |
| Baisse préalable seule | 7 937,66 | +98,44 % | −42,38 % | 827 | 36,03 % | 60,44 % |
| Baisse puis une clôture en hausse | 5 207,96 | +30,20 % | −41,75 % | 625 | 36,16 % | 47,20 % |
| **Baisse puis deux clôtures en hausse** | **3 969,86** | **−0,75 %** | **−42,60 %** | **401** | **34,16 %** | **30,29 %** |

Le cas principal conserve 722 signaux sur 211 titres ; 401 trades sur 203 titres
sont effectivement clôturés. Il a 137 gagnants et 264 perdants. Capital engagé
moyen 984,61 USD, contre 7 187,51 USD pour le témoin ; coûts 374,50 contre
2 741,00 USD. Son profit factor réalisé est 0,995, contre 1,183. Le gain moyen
des gagnants passe de +11,83 % à +9,90 % du notional d'entrée, la perte moyenne
de −5,19 % à −5,03 %. Le filtre coupe donc des occasions favorables sans
améliorer le taux gagnant du cas principal ni son drawdown cumulé.

Les moyennes en pourcentage par trade ne reconstituent pas le rendement du
compte : quantités, capitaux disponibles, chronologie, coûts et positions encore
ouvertes diffèrent. Les capitalisations finales sont valorisées, sans liquidation
artificielle au 1 octobre ; respectivement 10/7/6/3 positions restent ouvertes.

### Rendements annuels du portefeuille continu

| Année | Témoin | Baisse seule | Une clôture | Deux clôtures |
| --- | ---: | ---: | ---: | ---: |
| 2021 | +8,45 % | +3,49 % | −14,61 % | −26,09 % |
| 2022 | −2,13 % | −26,51 % | −27,87 % | −16,16 % |
| 2023 | +83,23 % | +44,19 % | +38,24 % | +13,01 % |
| 2024 | +34,14 % | +30,45 % | +20,92 % | +15,09 % |
| 2025 | +35,38 % | −0,45 % | +0,82 % | +23,33 % |
| 2026 au 1 octobre | +7,87 % | +39,33 % | +25,41 % | −0,14 % |

La version stricte perd notamment davantage que le témoin en 2021–2022 puis
capte beaucoup moins de la hausse de 2023. Une exposition moindre ne garantit
pas un DD moindre : l'enchaînement des pertes et la sélection des titres comptent.
Ce constat écarte ces seuils et cette définition ; il ne prouve pas que toute
forme de retournement soit inexploitable. Aucun seuil n'a été recherché après
lecture de ces résultats et aucun filtre n'est ajouté en production.

![Capital et drawdowns comparés](../../artifacts/research/us_q051_decline_rebound/20261126-v2/capital-comparison.png)

Le panneau inférieur montre le DD aux clôtures. Les valeurs du tableau sont les
DD mesurés sur les marques intraday et les replis OHLC hérités de la référence.

### Livraison et contrôles

Rapports détaillés : `comparison.csv`, `annual-comparison.csv`,
`capital-curves.csv`, `comparison.json`, `results.md`. Les huit tests du filtre
et le contrôle scalaire des 9 890 signaux passent ; les 3 324 trades sont
contrôlés (sélection à J, entrée J+1, durée H10, open11, frais/P&L), ainsi que
le capital composé sans remise à zéro annuelle.

La publication utilise `scripts/research/report_q051_decline_rebound_20261126.py`,
puis `scripts/research/validate_q051_decline_rebound_20261126.py`. Un défaut
du générateur initial utilisait `qty` alors que le CSV natif nomme la colonne
`quantity`. Le rapporteur distinct corrige ce nom et inclut les dividendes à
recevoir dans la réconciliation ; ni les sources figées, ni les inputs, ni les
sorties économiques des replays ne sont modifiés ou rejoués.

Les quatre cas sont disponibles dans l'historique Backtest sous les IDs
`20261126_q051_rebound_reference`, `20261126_q051_rebound_decline_only`,
`20261126_q051_rebound_rebound_1`, `20261126_q051_rebound_rebound_2`.
Le filtre reste un protocole de recherche ; aucun profil opérationnel n'est changé.

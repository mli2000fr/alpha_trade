# TOP10 Oracle : liquidité, gaps et parcours TP20/SL7

## Conclusion

**Calcul terminé, exploratoire, aucun filtre promu.** Une forte liquidité
quotidienne et l'absence de gros gaps récents ne suffisent pas à améliorer
régulièrement la réussite TP20 avant SL7 sur les TOP10 archivés de 2024–2026.
Le problème du parcours est réel : de nombreux titres finissent dans le bon
sens, mais auraient touché leur stop auparavant. Cette observation future ne
constitue pas un signal utilisable à l'entrée.

La comparaison small/mid/large **n'est pas testable proprement sur ces trois
années avec les capitalisations présentes**. Ne pas utiliser une capitalisation
actuelle, ou après la baisse, pour classer rétrospectivement une entrée.

## Périmètre et protocole figé

- Modèles annuels Oracle **parcours** : 2024 `model-factory-20261014113215-437ed1`,
  2025 `model-factory-20261014113226-102eca`,
  2026 `model-factory-20261014113232-bc35a7`.
- Dix rangs d'amplitude originaux chaque séance, sans GPT, consensus ni
  reclassement par résultat futur ; pas de remplacement hors TOP10.
- Analyse LONG et SHORT **séparément**, sans prétendre que l'Oracle choisit la
  direction. Entrée à l'ouverture de J+1, TP20/SL7 ancrés au prix d'entrée.
- Vingt séances **incluant la séance d'entrée** ; à défaut de barrière, mesure
  à la clôture de la vingtième. Pas de trailing.
- Gap défavorable franchissant le stop : sortie à l'ouverture, donc perte
  possiblement supérieure à 7 %. TP exécuté à sa limite, sans bonification de gap.
- Si haut et bas franchissent les deux barrières le même jour, stop d'abord,
  avec indicateur d'ambiguïté ; l'ouverture d'une séance ultérieure peut résoudre
  l'ordre. Sensibilité excluant les cas ambigus fournie.
- Chaque couple date/titre est une **occasion indépendante**, potentiellement
  répétée et chevauchante. Ce n'est pas un portefeuille, ni des achats répétés
  réellement autorisés ; pas de rendement économique, frais, emprunt ou levier.
- Prix EODHD split-adjusted archivés, OHLC non remplis, calendrier complet,
  identité constante ; événements d'identité connus exclus si pertinents.
- Années déjà examinées auparavant : aucun nouveau holdout indépendant.

Indicateurs connus au plus tard à J, calculés sur vingt séances consécutives :

1. `adv20` : moyenne de `close × volume`, proxy de montant échangé, pas profondeur
   bid/ask ou garantie d'exécution ; seuil fixe **20 millions USD**.
2. `past_gap20` : plus grand écart absolu ouverture/clôture précédente sur vingt
   séances ; seuil fixe **7 %**, strictement inférieur pour être retenu.
3. ATR20/close : diagnostic complémentaire, sans optimisation d'un seuil.

Quatre bras : tous ; ADV20 ≥20 M$ ; gap20 <7 % ; les deux conditions.
Ces seuils sont ceux de cette expérience, **pas des seuils optimaux démontrés**.
Chaque date a le même poids pour la mesure principale ; les comptes par
occasion sont aussi fournis. Différences appariées sur les mêmes dates,
intervalles descriptifs par blocs de vingt séances, sans correction de tests
multiples, et sous-échantillon toutes les vingt dates. Pas de significativité
ou de causalité proclamée à partir de ces explorations.

## Couverture

| Année | Occasions TOP10 demandées | Occasions évaluables, par sens | Séances évaluables | Capitalisations admissibles |
|---|---:|---:|---:|---:|
| 2024 | 2 520 | 2 520 | 252 | 0 |
| 2025 | 2 500 | 2 500 | 250 | 0 |
| 2026 | 1 870 | 1 658 | 167 | 0 |

Total : **6 678 occasions**, chacune évaluée LONG et SHORT, soit 13 356 lignes.
En 2026 : douze entrées rejetées dans l'archive à J et deux cents occasions dont
la fenêtre n'est pas mature au 30 septembre. Aucun ajout de cours téléchargé.
Dernière décision mature : **1er septembre 2026**. Les queues de 2024/2025 sont
disponibles dans les archives jusqu'en janvier/février de l'année suivante.

Export SQL strictement en lecture seule : 554 observations de capitalisation,
183 symboles, dates du 9 au 28 septembre 2026. Critères : sources existantes
Finnhub/EODHD, réception avant le début UTC de J, disponibilité ≤J, ancienneté
≤45 jours. **Aucune ne précède une occasion mature de cette étude.** Ni les
valeurs Yahoo, ni des faits SEC de capitalisation non qualifiés, ni les calculs
du 18 octobre ne sont réintroduits pour combler les trous.

## Résultat des filtres

Pourcentage atteignant **TP20 avant SL7**, moyenne par date. Ce n'est pas le
pourcentage de trades rentables : une expiration peut être positive sans TP.

| Année | Sens | Sans filtre | ADV20 ≥20 M$ | Gap récent <7 % | Les deux | Occasions conservées, les deux |
|---|---|---:|---:|---:|---:|---:|
| 2024 | LONG | 21,39 % | 20,72 % | 21,55 % | 21,12 % | 35,00 % |
| 2025 | LONG | 29,84 % | 31,25 % | 28,20 % | 29,86 % | 32,32 % |
| 2026 | LONG | 27,03 % | 26,84 % | 25,43 % | 26,71 % | 38,72 % |
| 2024 | SHORT | 11,67 % | 11,65 % | 11,55 % | 12,30 % | 35,00 % |
| 2025 | SHORT | 14,32 % | 12,90 % | 15,62 % | 14,48 % | 32,32 % |
| 2026 | SHORT | 18,06 % | 19,24 % | 15,00 % | 18,59 % | 38,72 % |

Les dates où aucun titre ne passe le filtre restent comptabilisées dans sa
couverture, mais n'ont pas de taux conditionnel de TP. Ne pas interpréter la
différence brute des colonnes comme une comparaison économique appariée.
Les différences appariées et leurs intervalles sont dans `filters.csv`.

Tous les intervalles appariés du filtre **combiné** incluent zéro. Le gain
liquidité seul en SHORT 2026 (+1,18 point apparié) ne se retrouve pas en 2025
(−1,42 point). Le filtre de gaps en SHORT fait aussi changer le signe de son
effet suivant l'année. Il n'y a donc pas de protection directionnelle stable
à intégrer sur cette base.

Même constat avec le classement des dix titres à chaque date : AUC LONG
liquidité **0,471 / 0,514 / 0,461** ; petits gaps
**0,538 / 0,466 / 0,517** ; faible ATR relatif
**0,548 / 0,490 / 0,449**, pour 2024/2025/2026. Les orientations ne sont pas
inversées après observation des pertes pour fabriquer un résultat favorable.

## Direction correcte ne signifie pas parcours gagnant

| Année | LONG finissant en hausse à vingt séances | Dont stop touché avant toute sortie TP | Part des haussiers stoppés |
|---|---:|---:|---:|
| 2024 | 1 322 | 496 | 37,52 % |
| 2025 | 1 407 | 579 | 41,15 % |
| 2026 | 895 | 466 | 52,07 % |

Parmi les occasions atteignant au moins +20 % à un moment quelconque du
parcours, **19,55 % / 26,50 % / 40,05 %** avaient déjà touché le stop avant de
profiter de ce mouvement. Les valeurs contiennent la convention conservatrice
OHLC ; les cas ambigus sont rares et la sensibilité est fournie. Les replis
avant le meilleur extrême sont explicatifs : la barre du pic elle-même est
exclue du calcul de repli antérieur, son ordre intraday étant inconnu.

Ce résultat **ne justifie pas de supprimer ou d'élargir le stop** : des titres
perdants peuvent aussi continuer à baisser. Aucun nouveau SL n'est optimisé ici.

## Limites et décision

- Pas de conclusion « small caps imprévisibles » : absence de capitalisations
  historiques admissibles sur ce périmètre mature.
- Faible montant échangé ≠ petite capitalisation. En 2026 le groupe ADV20 <5 M$
  n'a que 42 observations sur deux titres : HPK 37, DNNGY 5. Il serait trompeur
  d'en faire une généralité sur toutes les petites entreprises.
- Fort chevauchement des occasions, concentration par symbole, univers courant
  survivant et prix rétrospectivement ajustés. Les intervalles par blocs ne
  règlent pas tous les biais de sélection ni la dépendance par émetteur.
- Les plus gros gaps au-delà du SL sont listés dans
  `largest-gap-stop-cases.csv`. Leur prix/événement n'a pas fait l'objet d'une
  nouvelle validation indépendante : ne pas les présenter comme des pertes
  d'exécution certifiées ni comme des preuves de manipulation.
- Cette étude ne mesure pas l'efficacité propre de GPT ou du consensus.
- Aucun modèle entraîné/modifié, aucune écriture SQL, aucun téléchargement
  fournisseur/LLM, aucun ordre ou batch modifié.

**Décision : conserver les protections de données/liquidité opérationnelles,
mais ne pas ajouter ces filtres comme détecteurs de direction rentables.**
Un éventuel test économique nécessiterait un nouveau GO et un avantage plus
stable ; il n'est pas lancé ici.

## Reproduction et livrables

Script : `scripts/research/us_top10_liquidity_gap_audit.py`.
Tests ciblés et régression SHORT : **22 tests passent**.
Résultat final : `artifacts/research/us_top10_liquidity_gap/20261019-v2/`.
Le premier calcul `v1` est conservé ; `v2` explicite le cutoff conservateur des
capitalisations et ajoute les diagnostics/concentrations, sans nouveaux appels
SQL. Les classements et parcours ne sont pas changés.

```powershell
python -u -m scripts.research.us_top10_liquidity_gap_audit --phase prepare --output artifacts/research/us_top10_liquidity_gap/NOUVEAU_DOSSIER --cap-archive artifacts/research/us_top10_liquidity_gap/20261019-v1/capitalizations.json
python -u -m scripts.research.us_top10_liquidity_gap_audit --phase run --output artifacts/research/us_top10_liquidity_gap/NOUVEAU_DOSSIER
```

`prepare` exige un dossier neuf et fige les règles/empreintes avant les calculs.
`run` ne demande pas de connexion SQL. `caps-readonly` est la phase séparée
optionnelle d'export de capitalisations ; elle ne doit jamais écrire en base.

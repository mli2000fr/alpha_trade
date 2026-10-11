# Oracle H20 corrigé — audit des dix premiers titres

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Conclusion

Audit terminé le 7 octobre 2026, sans nouvel entraînement ni écriture SQL.
Le TOP10 signifie **dix titres chaque séance**, pas les 10 % de l'univers et
pas les dix plus grands mouvements connus dans le futur.

Le TOP10 corrigé conserve une forte concentration descriptive en extrêmes :
59,85 % de capture historique OOF et 55,26 % sur la période externe.
Cependant, les corrections ne démontrent pas une amélioration de ce classement :
capture historique de 61,17 % à 59,85 %, externe de 55,74 % à 55,26 %.
Il ne faut pas revenir aux calculs mathématiquement défectueux pour retrouver
les anciens chiffres. La qualité numérique et la performance prédictive sont
deux questions distinctes.

**Le filtre ATR n'ajoute rien aux dix premiers titres corrigés dans cet audit** :
les sélections Oracle seul et Oracle TOP20 ∩ ATR TOP20, puis dix premiers scores
Oracle, sont exactement identiques sur toutes les dates testées. Cela ne
contredit pas les résultats sur l'ensemble TOP20 %, où l'intersection modifie
effectivement la sélection.

Ce résultat ne démontre ni la direction ni un rendement de portefeuille.

## 1. Sources et périmètre

Les prédictions proviennent de l'[expérience appariée des correctifs](oracle_h20_numeric_effect.md).
Chaque bras reçoit ses propres calculs de features et son propre modèle :
on ne compare pas un ancien modèle alimenté artificiellement par des features
corrigées. Même univers de 1 790 titres, mêmes clés observables, ATR et résultats
réalisés identiques entre les bras ; seul le score Oracle peut changer.

| Source | Dates de signal | Séances sélectionnées | Origine des scores |
|---|---|---:|---|
| Historique OOF | 2018-07-05 → 2024-07-09 | 1 512 | 12 folds appariés, 24 modèles déjà entraînés |
| Externe figée | 2025-01-02 → 2026-09-03 | 419 | Dernier modèle de chaque bras, sans refit externe |

2018 et 2024 sont des années partielles. Il n'y a pas de test sur le second
semestre 2024 dans ces archives. Les modèles externes sont ceux du dernier
fold, pas un nouvel entraînement terminal utilisant toute l'année 2024.
2026 a déjà été examinée : ce n'est pas un holdout vierge.

Artefacts d'entrée :

- `artifacts/research/us_concentrated_replay/oracle-h20-numeric-effect-20261007-v1` ;
- `artifacts/research/us_concentrated_replay/oracle-h20-numeric-external-20261007-v1`.

Les labels gardent les déciles de l'univers original du batch de référence,
sans recalcul de la cible sur les seuls 1 790 titres restants.

## 2. Sélection figée, sans information future

Pour chaque date, sur le pool réellement doté d'un score et d'un ATR :

1. **Oracle TOP10 titres** : score décroissant, symbole alphabétique pour les
   ex æquo, conserver les dix premiers.
2. **Intersection puis TOP10 titres** : former Oracle TOP20 % et ATR20 % TOP20 %
   (`ceil(0,20 × taille du pool)` titres chacun), prendre leur intersection,
   conserver les dix premiers **scores Oracle** à l'intérieur.
3. **ATR TOP10 titres** : ATR20 % décroissant, symbole pour les ex æquo,
   conserver les dix premiers. Témoin inchangé entre les bras.

ATR20 % mesure l'ATR normalisé par le prix ; ce n'est pas l'ATR brut en dollars.
L'intersection n'est pas un produit numérique score Oracle × ATR.
Aucun classement par amplitude réalisée, aucun filtrage des rendements négatifs,
aucune substitution d'un résultat inconnu par le titre suivant.
Ce n'est pas non plus l'application des contraintes de tradabilité, de risque
et de disponibilité de capital du portefeuille live.

Les trois politiques sélectionnent exactement dix titres sur chaque séance
de cet audit. Tous les TOP10 corrigés passent déjà la double porte TOP20 %.
Le bras ancien ne présentait que de très rares différences historiques entre
Oracle seul et intersection ; il est également identique en externe.

## 3. Définition des chiffres

Le rendement observé est celui du label H20, depuis le cours de référence de
la date du signal jusqu'à son échéance, **pas depuis une entrée exécutable à J+1**.

- Capture réelle extrême : moyenne du flag `oracle_extreme10` des sélections
  évaluables, puis moyenne des séances évaluables.
- D1 et D10 : proportions dans les déciles réels 1 et 10, pas les signes seuls.
- Amplitude : valeur absolue du rendement H20 ; une baisse de 50 % compte autant
  qu'une hausse de 50 % dans la fréquence `|R| ≥ 50 %`.
- Médiane : médiane de toutes les observations date/titre évaluables de la période.
- Hausses/baisses : rendement H20 strictement positif/négatif. Quelques rendements
  nuls expliquent que leur somme puisse être inférieure à 100 %.

Les fréquences et amplitudes moyennes du rapport pondèrent chaque séance
évaluable de façon égale. Les observations H20 se chevauchent et un même titre
peut être sélectionné plusieurs jours : elles ne sont pas des trades indépendants.

Le contrat historique du flag extrême inclut `rank >= 0,90`, tandis que le
décile est `ceil(rank × 10)`. Une frontière exactement à 0,90 peut donc être
flaggée extrême tout en étant D9 : capture et D1+D10 peuvent différer légèrement.

## 4. Résultat avant/après, Oracle TOP10 titres

| Période | Capture avant → corrigée | Amplitude moyenne avant → corrigée | Médiane corrigée | Hausses corrigées | Baisses corrigées |
|---|---:|---:|---:|---:|---:|
| Historique OOF | 61,17 → 59,85 % | 21,28 → 20,91 % | 14,35 % | 52,47 % | 47,09 % |
| 2025 | 55,12 → 54,28 % | 16,97 → 16,82 % | 13,13 % | 53,92 % | 45,92 % |
| 2026 au 3 septembre | 56,67 → 56,73 % | 18,02 → 18,53 % | 14,98 % | 52,74 % | 47,14 % |
| Externe complète | 55,74 → 55,26 % | 17,39 → 17,51 % | 13,82 % | 53,44 % | 46,41 % |
| 2026Q1 | 48,69 → 49,84 % | 16,37 → 17,14 % | 14,27 % | 59,34 % | 40,33 % |

Ce sont des caractéristiques des titres sélectionnés, pas des rendements nets
du capital. Une amplitude moyenne de 17,51 % n'est **pas un gain de 17,51 %**.

| Période corrigée | D1 réel | D10 réel | `|R| ≥ 20 %` | `|R| ≥ 50 %` |
|---|---:|---:|---:|---:|
| Historique OOF | 27,55 % | 32,30 % | 36,18 % | 7,24 % |
| 2025 | 24,72 % | 29,56 % | 31,60 % | 3,76 % |
| 2026 au 3 septembre | 26,85 % | 29,88 % | 36,67 % | 5,00 % |
| Externe complète | 25,57 % | 29,69 % | 33,64 % | 4,26 % |
| 2026Q1 | 17,54 % | 32,30 % | 34,75 % | 3,11 % |

Début 2026, la sélection contient davantage de D10 que de D1, mais ne révèle
pas à J lesquels seront D10. Il est impossible de conclure que le portefeuille
LONG serait gagnant, compte tenu des entrées, chemins, stops, coûts et contraintes.

### Incertitude avant/après

Bootstrap descriptif apparié des différences quotidiennes : 1 000 réplications,
blocs contigus de 20 séances, seed 42. Aucune optimisation des seuils.

| Source | Différence de capture | Intervalle descriptif 95 % | Différence amplitude moyenne | Intervalle descriptif 95 % |
|---|---:|---:|---:|---:|
| Historique OOF | −1,318 point | [−2,310 ; −0,189] | −0,371 point | [−0,861 ; +0,092] |
| Externe figée | −0,478 point | [−2,010 ; +0,622] | +0,112 point | [−0,407 ; +0,549] |

Le recul de capture historique est plus net que celui du TOP20 % ; l'intervalle
descriptif exclut zéro. En externe, les intervalles incluent zéro : pas de gain
stable démontré. Ces intervalles ne constituent pas une preuve causale ni une
correction complète des dépendances par symbole/régime ou des nombreux tests antérieurs.

## 5. Stabilité annuelle du TOP10 corrigé

| Année | Séances | Capture avant → corrigée | Amplitude moyenne corrigée | Hausses corrigées |
|---|---:|---:|---:|---:|
| 2018 partiel | 124 | 53,71 → 53,58 % | 14,22 % | 46,96 % |
| 2019 | 252 | 65,86 → 65,63 % | 19,62 % | 51,87 % |
| 2020 | 253 | 65,34 → 61,98 % | 34,52 % | 58,34 % |
| 2021 | 252 | 63,73 → 63,25 % | 19,24 % | 52,10 % |
| 2022 | 251 | 60,76 → 61,20 % | 22,32 % | 46,53 % |
| 2023 | 250 | 59,28 → 55,56 % | 16,97 % | 60,08 % |
| 2024 partiel | 130 | 50,54 → 49,54 % | 11,39 % | 45,00 % |
| 2025 | 250 | 55,12 → 54,28 % | 16,82 % | 53,92 % |
| 2026 partiel | 169 | 56,67 → 56,73 % | 18,53 % | 52,74 % |

La baisse de capture historique se concentre notamment en 2020 et 2023.
2022 et 2026 progressent légèrement : aucun bénéfice uniforme par année.

ATR seul est inchangé : capture 57,17 % et amplitude moyenne 19,99 % en OOF ;
50,89 % et 16,22 % en externe. Oracle corrigé reste descriptivement meilleur
que ce témoin, sans pour autant fournir une direction exploitable.

## 6. Couverture, concentration et réserves de qualité

### Résultats disponibles

OOF corrigé : 15 120 sélections, 15 119 évaluables, une manquante ; couverture
99,993 %. Externe corrigé : 4 190 sélections, 4 180 évaluables, dix manquantes,
couverture 99,761 %.

Les dix résultats manquants externes sont ceux du **3 septembre 2026** :
aucun label H20 évaluable dans le snapshot utilisé pour ces titres.
La sélection est archivée et compte dans les 419 séances, mais cette date
n'entre pas dans les moyennes de performance ni dans les 418 différences
quotidiennes évaluables. Aucune imputation à zéro ni substitution.

### Concentration

Les corrections changent environ un quart des sélections date/titre :
73,04 % de conservation historique et 75,39 % externe.
OOF corrigé : 276 titres uniques, les dix plus fréquents représentent 22,18 %
des observations évaluables. Externe : 136 titres uniques, dix plus fréquents
32,70 %. En 2025 seul, cette concentration atteint 48,80 %.

| Titre externe corrigé | Nombre de sélections évaluables |
|---|---:|
| GPRE | 179 |
| SRPT | 178 |
| LMND | 177 |
| MP | 163 |
| TROX | 127 |
| NBR | 117 |
| ANAB | 109 |
| VICR | 109 |
| HPK | 105 |
| NEOG | 103 |

Ces nombres sont des récurrences quotidiennes, pas des trades effectivement
exécutés. Certains titres ont plusieurs fenêtres H20 très corrélées.

Ex æquo : sur 64 séances OOF corrigées, les dix scores sélectionnés sont
identiques entre eux ; l'ordre alphabétique départage ces cas. Ce n'est pas
une preuve de dix niveaux de confiance distincts. En externe, les dix scores
sélectionnés sont distincts sur chacune des 419 séances.

### Prix et très grandes amplitudes

Les facteurs/ratios corrigés ne certifient pas tous les prix ni tous les
ajustements d'opérations sur titres. Le TOP10 corrigé contient encore des
exemples historiques de très forte amplitude (NBR le 2020-05-08 : +496,03 %,
PR le 2020-04-01 : +377,73 %). En externe : MP le 2025-07-09 +124,81 %,
DOCN le 2026-04-14 +112,01 %. Ces exemples sont triés **après sélection**, pour
diagnostic seulement, jamais pour fabriquer les candidats.

Le témoin ATR contient DD autour de juin 2026 avec des rendements proches
de +200 %. Ces queues demandent une qualification des prix/identités et des
ajustements avant un éventuel test économique ; elles ne sont ni certifiées
ni automatiquement classées comme erreurs par cet audit. Aucun nouveau retrait.
La moyenne est donc accompagnée des médianes et fréquences, mais cela ne
remplace pas cette qualification.

## 7. Exemple : les dix premiers du 3 septembre 2026

Dernière date sélectionnée en externe, bras corrigé. Oracle seul et intersection
fournissent exactement cette liste, dans cet ordre. Les scores ne sont pas
des probabilités de hausse ; aucun résultat H20 n'est disponible ici.

| Rang | Titre | Score Oracle |
|---|---|---:|
| 1 | CCOI | 0,897572 |
| 2 | BAND | 0,885936 |
| 3 | DOCN | 0,878355 |
| 4 | SSTK | 0,876904 |
| 5 | MXL | 0,874830 |
| 6 | PENG | 0,861788 |
| 7 | QDEL | 0,860704 |
| 8 | SIMO | 0,859890 |
| 9 | SITM | 0,857167 |
| 10 | VPG | 0,857020 |

## 8. Reproduction et fichiers de sortie

Script : `scripts/research/us_oracle_numeric_top10.py`.
Les empreintes des protocoles et des prédictions sont archivées ; les archives
OOF sont comparées aux sommes SHA-256 des fichiers `done.json`. Les clés,
features observables non traitées et outcomes des deux bras doivent être identiques.

```powershell
python -u -m scripts.research.us_oracle_numeric_top10 --historical artifacts/research/us_concentrated_replay/oracle-h20-numeric-effect-20261007-v1 --external artifacts/research/us_concentrated_replay/oracle-h20-numeric-external-20261007-v1 --output artifacts/research/us_concentrated_replay/oracle-h20-numeric-top10-20261007-v1
```

Répertoire de sortie :
`artifacts/research/us_concentrated_replay/oracle-h20-numeric-top10-20261007-v1`.

- `protocol.json` : paramètres figés et empreinte du script ;
- `report.json` : agrégats, années, Q1, différences, concentration, exemples ;
- `*-selected.parquet` : chaque date/titre, score, rang de sélection et résultats ;
- `*-daily.parquet` : compteurs et métriques de chaque date/politique/bras ;
- `progress.json` : état `COMPLETED`.

Validation : 27 tests ciblés réussis sur les trois scripts de mesure numérique,
dont 12 cas pour ce TOP10. Le lancement ciblé initial a réussi ses assertions
mais échoué au seuil global de couverture pytest (70 % de toute l'application) ;
la relance ciblée avec `--no-cov` passe. La suite complète n'a pas été exécutée.
Tests : taille fixe, absence de tri futur, non-remplacement des labels manquants,
intersection sur tout le TOP20, invariance du témoin ATR, ex æquo, clés uniques,
valeurs finies, seuils inclusifs et appariement des dates.

## Décision

Conserver les calculs corrigés ; ne pas promouvoir ces modèles de recherche
automatiquement. Le TOP10 concentre l'amplitude mais conserve beaucoup de baisses.
Une comparaison économique ultérieure devra reprendre **ces rangs de score**,
qualifier les prix extrêmes et appliquer le contrat exécutable complet : J+1,
capital, sizing, coûts, SL/trailing/TP, liquidité et risque. Elle n'a pas été
lancée dans cette étape. Aucun modèle ni batch existant modifié.

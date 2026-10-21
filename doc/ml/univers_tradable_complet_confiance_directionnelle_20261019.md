# Univers tradable complet : sélection causale de titres/sens historiquement favorables

> Les deux variantes demandées ensuite, **TP10/SL10 et TP10 sans SL**, sont
> terminées dans [un rapport distinct](univers_tradable_tp10_sl10_et_sans_sl_20261019.md).
> Le présent document conserve les résultats de référence TP20/SL7.

## Conclusion

**CALCUL TERMINÉ SUR LES 1 790 TITRES — EXPLORATOIRE, PAS D'UNIVERS PROMU.**

Ce test n'est limité ni au TOP10 ni au TOP20 % Oracle. Chaque titre du fichier
`config/univers_batch/univers_filtred_tradable.txt` est étudié à chaque séance
historique admissible. Le croisement avec le TOP10 est un résultat secondaire,
pas un filtre caché du test principal.

La règle retient davantage de titres ayant des mouvements assez grands pour
atteindre TP20, mais **ne stabilise pas suffisamment leur direction future**.
Le sens choisi donne une moyenne nette par occasion de **−0,33 % en 2025 et
−0,58 % en 2026** ; le contrôle sans chevauchement par titre/sens reste négatif.
Ce ne sont pas des rendements annuels de portefeuille.

Les données comportent aussi une réserve prix/opérations sur titres explicite
en fin de document : aucun résultat économique n'est qualifié pour production.

## Population : le fichier complet, pas seulement les titres Oracle

- Fichier tradable courant figé par empreinte : **1 790 symboles distincts**.
- Archive de prix : 1 793 symboles, dont **les 1 790 demandés**, aucun absent.
- Tous ont au moins une fenêtre qualifiée dans chaque année étudiée.
- Les noms, types d'instruments et critères de tradabilité sont ceux du fichier
  actuel, **pas un univers PIT historique** reconstituant chaque entrée/sortie
  de cotation ou tous les radiés. Ne pas conclure à une couverture exhaustive
  de toutes les actions US historiquement négociables.
- Aucun classement Oracle nécessaire pour entrer dans l'analyse principale.
- 2024 est l'historique initial ; les évaluations futures du filtre commencent
  en 2025, puis continuent en 2026, sans utiliser leurs résultats encore inconnus.

| Année | Couples séance/titre demandés | Fenêtres qualifiées | Titres avec couverture |
|---|---:|---:|---:|
| 2024, historique initial | 451 080 | 451 002 | 1 790 |
| 2025, évaluation | 447 500 | 447 460 | 1 790 |
| 2026, évaluation partielle | 334 730 | 293 574 | 1 790 |
| Total | **1 233 310** | **1 192 036** | **1 790 distincts** |

Chaque fenêtre qualifiée est évaluée LONG et SHORT séparément, soit 2 384 072
observations de parcours, dont **1 482 068 observations de test** 2025–2026.

Exclusions explicites :

- 2024 : 50 historiques causaux incomplets/invalides, 28 parcours futurs invalides.
- 2025 : 40 historiques causaux incomplets/invalides.
- 2026 : 35 800 fenêtres non matures au 30 septembre, 4 646 historiques causaux
  incomplets/invalides, 709 parcours futurs/identités non qualifiés, un cas
  supplémentaire traversant un événement d'identité connu.

Dernière décision 2026 mature : **1er septembre**. Le 30 septembre est la limite
d'observation, pas la dernière date dont on peut connaître vingt séances futures.
Les queues de 2024/2025 jusqu'en janvier/février suivant sont disponibles.

## Protocole inchangé par rapport au test TOP10

Le but est de tester l'extension d'univers, pas de réajuster les seuils :

1. Au premier jour NYSE de chaque mois, examiner les 504 séances passées.
2. Utiliser seulement les fenêtres de vingt séances **entièrement terminées
   avant cette date**. Les sorties rapides n'accélèrent pas l'admission des labels.
3. Par titre/sens, choisir les premières fenêtres chronologiques ne se
   chevauchant pas, sans sélectionner leur point de départ selon le gain.
4. Exiger au moins huit fenêtres ; borne Wilson90 du taux TP supérieure à la
   référence globale passée du même sens ; moyenne nette positive et supérieure
   au global ; moyenne positive et taux TP supérieur au global dans chacune des
   deux moitiés chronologiques de l'historique.
5. Figer ce statut pour le mois suivant, sans relire ses résultats futurs.

Les règles et constantes sont celles de `us_top10_symbol_reliability.py`.
Un test garantit l'identité des adhésions entre l'implémentation accélérée et
la précédente. Aucun seuil optimisé ou modèle directionnel entraîné ici.

Bras conservés : tous LONG ; tous SHORT ; titres qualifiés LONG ; titres
qualifiés SHORT ; choix du seul sens qualifié. Si les deux sens passent,
le dernier bras s'abstient. Les titres absents d'un historique suffisant ne sont
pas automatiquement qualifiés comme mauvais.

Protection : entrée open J+1, **TP20/SL7**, vingt séances incluant l'entrée,
expiration close20, trailing désactivé. Stop-first en collision OHLC non résolue,
ouverture d'abord lorsqu'elle tranche ; gap au-delà du stop exécuté à l'open.

Coûts hypothétiques : commission 1 bp + demi-spread 5 bp + slippage 2 bp par
jambe ; frais de sortie proportionnels au prix de sortie. SHORT : emprunt
supposé de 0,3 %/an, durée `(séance de sortie−1)/252`. Locates, rappels,
indemnités de dividendes et marge réelle non certifiés.

Qualité des observations : vingt et une séances préalables consécutives
incluant J avec OHLC valides EODHD split non remplis, volume positif et identité
stable ; vingt séances futures complètes, identité stable, événements connus
contrôlés. Les archives sont rétrospectivement ajustées : ce contrôle technique
ne certifie pas toutes les opérations sur titres ni un flux réellement reçu à J.

## Résultats sur le fichier complet

Taux TP/SL et occasions gagnantes pondérés par occasion. La moyenne nette
ci-dessous est **par occasion indépendante de capital**, pas un rendement de
portefeuille ; les apparitions successives du même titre se chevauchent encore.

| Année | Bras | Occasions | Titres | TP avant SL | Occasion positive après coûts | Moyenne nette par occasion |
|---|---|---:|---:|---:|---:|---:|
| 2025 | Tous LONG | 447 460 | 1 790 | 6,43 % | 46,19 % | +0,35 % |
| 2025 | Titres qualifiés LONG | 14 579 | 124 | 17,14 % | 41,07 % | +1,01 % |
| 2025 | Tous SHORT | 447 460 | 1 790 | 4,94 % | 39,48 % | −0,83 % |
| 2025 | Titres qualifiés SHORT | 11 798 | 111 | 9,29 % | 29,04 % | −1,99 % |
| 2025 | Sens choisi selon historique | 26 093 | 225 | 13,60 % | 35,71 % | **−0,33 %** |
| 2026 | Tous LONG | 293 574 | 1 790 | 8,80 % | 43,67 % | +0,38 % |
| 2026 | Titres qualifiés LONG | 15 618 | 332 | 16,75 % | 34,98 % | −0,04 % |
| 2026 | Tous SHORT | 293 574 | 1 790 | 5,17 % | 38,77 % | −0,89 % |
| 2026 | Titres qualifiés SHORT | 9 352 | 216 | 10,13 % | 30,92 % | −1,53 % |
| 2026 | Sens choisi selon historique | 24 276 | 490 | 14,23 % | 33,44 % | **−0,58 %** |

**TP avant SL n'est pas identique à trade gagnant** : un titre peut expirer
en gain sans avoir atteint +20 %. Le filtre enrichit les TP mais peut perdre
des petits gains d'expiration et conserver davantage de stops. L'interprétation
« sélectionner davantage d'amplitude sans direction plus fiable » est compatible
avec les résultats, pas une preuve causale du mécanisme.

Même constat pour le signe final : en LONG, la concordance directionnelle
moyenne par date passe de **53,47 à 53,19 % en 2025**, puis de
**51,91 à 48,97 % en 2026** après sélection. Le choix de sens combiné donne
48,63 % / 48,41 % de concordance finale.

Au fil des vingt et une sélections mensuelles, le filtre qualifie **77 à 226
titres par mois** et sélectionne effectivement **525 titres distincts** sur les
deux années. Il ne s'agit donc plus du précédent cas concentré sur MXL.
Couverture du bras combiné : 5,83 % des occasions 2025, 8,27 % en 2026.

## Contrôles sans chevauchement et par période

Les règles de départ restent chronologiques ; aucune recherche du meilleur
décalage de fenêtres. « Sans chevauchement » vaut par titre/sens, pas garantie
d'indépendance entre sociétés, secteurs ou régimes de marché.

| Année | Bras sélectionné | Fenêtres sans chevauchement | TP avant SL | Moyenne nette par fenêtre |
|---|---|---:|---:|---:|
| 2025 | LONG | 841 | 17,60 % | +0,98 % |
| 2025 | SHORT | 687 | 9,75 % | −1,97 % |
| 2025 | Sens choisi | 1 509 | 14,05 % | **−0,35 %** |
| 2026 | LONG | 1 150 | 16,87 % | +0,10 % |
| 2026 | SHORT | 686 | 11,08 % | −1,39 % |
| 2026 | Sens choisi | 1 785 | 14,68 % | **−0,44 %** |

En LONG, le petit résultat positif 2025 ne se reproduit pas clairement en 2026 ;
les différences moyennes appariées face au global incluent zéro dans les
intervalles descriptifs par blocs. En 2026, les occasions LONG sélectionnées du
second semestre ont une moyenne nette **−0,96 %**, contre +0,40 % au premier.
Les SHORT sélectionnés restent négatifs dans les quatre semestres examinés.

Pour les **mêmes couples date/titre** du bras combiné, toujours LONG donnerait
une moyenne nette +1,10 % en 2025 et +0,27 % en 2026, contre −0,33 / −0,58 %
pour le sens choisi : sa capacité de sélection directionnelle n'est pas démontrée.

## Résultat secondaire : sous-univers appris partout, puis croisé avec TOP10

Le TOP10 n'est utilisé **qu'après** l'apprentissage mensuel sur tout le fichier.
Les 4 158 couples date/titre du précédent test 2025–2026 sont tous retrouvés ;
prix, sorties et coûts de ses 8 316 lignes LONG/SHORT sont identiques.

| Année | Règle dans TOP10 | Occasions | Titres | TP avant SL | Moyenne nette par occasion |
|---|---|---:|---:|---:|---:|
| 2025 | TOP10 tous LONG | 2 500 | 87 | 29,84 % | +1,69 % |
| 2025 | Sens choisi via historique complet | 986 | 36 | 22,11 % | −0,33 % |
| 2026 | TOP10 tous LONG | 1 658 | 75 | 27,08 % | +0,49 % |
| 2026 | Sens choisi via historique complet | 775 | 43 | 19,87 % | −1,45 % |

Ces bras n'ont pas la même exposition et ne sont pas des portefeuilles ; le
rapport donne aussi les comparaisons aux mêmes dates et sur les mêmes titres
toujours LONG/SHORT. Sans chevauchement, le bras combiné donne +0,02 % par
fenêtre sur 103 fenêtres en 2025 et −1,52 % sur 87 en 2026. Pas d'amélioration
robuste à promouvoir dans la chaîne Oracle.

## Réserve prix et opérations sur titres

Une analyse mécanique des résultats a isolé **96 lignes sur douze symboles**
avec perte brute supérieure à 75 % du montant d'entrée dans un des sens.
Certaines peuvent être de vrais gaps ; d'autres appellent une qualification
d'ajustement/identité. Exemple KLAC : échelle de prix passant apparemment de
196,65 à 2 048,27, donnant un résultat SHORT théorique −941,58 %. Ce chiffre
n'est **pas une perte de courtier certifiée**, ni utilisable comme PnL validé.

Les lignes sont conservées et signalées dans `large-loss-price-review.csv`,
sans suppression opportuniste des symboles ni correction SQL. Ce contrôle
n'est pas un filtre d'entrée fondé sur le futur.

Parmi les occasions effectivement sélectionnées, seules deux lignes extrêmes
sont concernées, KSS SHORT en 2025 ; aucune en 2026. En omettant ces deux
lignes **uniquement à titre de sensibilité ex post**, moyenne combinée 2025
−0,327 % au lieu de −0,335 % ; 2026 reste −0,581 %. Les adhésions ne sont pas
réapprises : cela ne remplace pas une réparation/qualification complète.

La conclusion « pas d'univers directionnel robuste démontré par cette règle »
reste prudente ; les moyennes après coûts, particulièrement les références
globales et les diagnostics individuels, restent **exploratoires avec réserve
prix/opérations sur titres**. Aucun backtest économique n'est lancé.

## Décision

- Ne pas transformer les 525 titres retenus a posteriori en liste permanente.
- Ne pas déclarer les autres titres imprévisibles ; on a testé une règle
  particulière de confiance historique, pas toutes les méthodes possibles.
- Ne pas annoncer que GPT ou le consensus ont été testés : aucun n'intervient.
- Aucun modèle individuel ou sectoriel entraîné ; ce sont des préférences de
  sens issues des parcours passés, pas un nouveau prédicteur de retournements.
- Ne pas relâcher les seuils après observation des résultats pour obtenir un GO.
- Univers courant survivant, périodes déjà explorées, sélections multiples non
  corrigées et prix rétrospectifs : aucun résultat n'est une preuve prospective.

## Livrables, tests, suivi

Résultat : `artifacts/research/us_tradable_symbol_reliability/20261019-v1/`.

- `protocol.json` : périmètre complet, règles figées et empreintes.
- `parts/` : un fichier par titre, reprise du calcul sans recommencer les autres.
- `price-coverage.csv`, `paths-manifest.json` : couverture et exclusions de chacun
  des 1 790 titres, aucune absence cachée.
- `monthly-memberships.csv/.parquet` : listes mensuelles et motifs par titre/sens.
- `evaluations.parquet`, `selected-occasions.parquet` : toutes les évaluations
  et la sélection effective, pas un fichier d'univers de production.
- `primary-summary.json`, `secondary-top10-summary.json`, `report.json` : résultats.
- `final-audit.json` : empreintes, causalité, absence de doublons et parité TOP10.
- `price-reserve-audit.json`, `large-loss-price-review.csv` : réserve prix.

Script : `scripts/research/us_tradable_symbol_reliability.py`.
**31 tests passent** : huit propres, dix du filtre par titre et treize du parcours.
Parité vectorielle réelle sur les **13 356 lignes** du diagnostic TOP10 original.
La couche accélérée produit exactement les mêmes épisodes et statuts que la
règle précédente sur les tests de contrôle ; mutation de résultats futurs sans
effet sur les adhésions passées.

```powershell
python -u -m scripts.research.us_tradable_symbol_reliability --phase prepare --output artifacts/research/us_tradable_symbol_reliability/NOUVEAU_DOSSIER
python -u -m scripts.research.us_tradable_symbol_reliability --phase build --output artifacts/research/us_tradable_symbol_reliability/NOUVEAU_DOSSIER
python -u -m scripts.research.us_tradable_symbol_reliability --phase run --output artifacts/research/us_tradable_symbol_reliability/NOUVEAU_DOSSIER
```

`prepare` exige un dossier neuf. `build` reprend les titres déjà écrits si leurs
empreintes et le protocole sont inchangés. `progress.json` indique la phase.
**Aucun SQL, appel fournisseur/LLM, entraînement, ordre ou changement de
production**. Le registre des expériences est mis à jour.

# News et prix intraday US — premier test descriptif, 16 octobre 2026

**Suite historique distincte livrée** : [janvier 2026 sur le TOP10 Oracle et les
avis GPT déjà archivés](news_oracle_top10_janvier_2026.md). Ce test utilise 200
sélections et le parcours TP20/SL10 ; il ne remplace pas rétroactivement le
petit descriptif intraday d'octobre ci-dessous.

## Résultat à retenir

**Le calcul est réalisé : aucune relation uniforme et exploitable n'est
démontrée sur cet échantillon.** Ce n'est ni un test économique ni un test de
direction à H20. Il s'agit de mouvements observés autour de la publication.

Sur 27 couples news/titre retenus avant extraction des prix, **10** ont les
fenêtres complètes : cinq textes favorables, deux défavorables et trois mixtes
ou neutres. Les dix cas ne couvrent que **deux dates de publication NY**,
les 14 et 15 octobre. Les montants ci-dessous sont des variations de cours,
pas des gains de portefeuille.

| Tonalité qualitative figée | Cas avec cours | Hausse après publication/ouverture | Mouvement moyen sur les 30 minutes après | Médiane après |
| --- | ---: | ---: | ---: | ---: |
| Favorable | 5 | 3/5 | **−0,5494 %** | +0,0915 % |
| Défavorable | 2 | 1/2, donc une seule baisse sur deux | **+0,0503 %** | +0,0503 % |
| Mixte ou neutre | 3 | Non utilisé comme cible directionnelle | **−0,5168 %** | −0,8496 % |

Trois hausses modestes parmi cinq cas favorables n'empêchent pas une moyenne
négative : les baisses de SNPS et CBRL sont plus importantes. On ne peut pas
transformer « 3/5 » en taux de trades gagnants ou probabilité de réussite.

## 1. Ce que nous avons réellement testé

Nouveau périmètre autorisé : **news dont le sujet est rapproché du symbole**,
sans exiger qu'il s'agisse d'une nouvelle émission primaire d'actions. Le
diagnostic financement précédent reste clôturé ; ses réserves ne sont pas
effacées pour ce test différent.

Source : les 60 corps déjà lus et les 93 associations du dossier
`artifacts/research/us_news_event_qualification/20261016-financing-screen-closure-v2/`.
Ce petit ensemble vient d'une revue enrichie en mots-clés de financement et de
20 témoins précédemment sélectionnés, **pas d'un tirage représentatif de toutes
les news ni du TOP20 Oracle**.

- 63 associations sans rapprochement du sujet exclues.
- Trois associations MSCI exclues en conservant la réserve de réutilisation
  déjà repérée ; pas de nouvelle interprétation juridique.
- **27 couples retenus** : 12 favorables, trois défavorables, 12 mixtes/neutres.
- 10 fenêtres complètes, 15 sans barres valides, deux trop proches d'une borne
  de séance pour la convention retenue. Zéro remplissage ou fallback.

Le rapprochement textuel de sujet n'est pas une certification historique de
l'instrument. CCJ/Cameco conserve notamment sa réserve de métadonnées actuelles
et de double cotation, sans correspondance historique inventée.

### Tonalité : pas des scores FinBERT

Les étiquettes sont une **lecture qualitative rétrospective par le même
assistant**, fixée avant les requêtes de prix. Elles décrivent le texte relatif
à la société, pas le rendement à venir. Elles ne sont ni une probabilité, ni un
score de confiance, ni une seconde revue humaine indépendante.

Exemples : opinion explicite d'achat SNPS/LDOS, commentaire défavorable PRMB,
opinion d'évitement SWKS, stable/hold/mixte conservé sans forcer une direction.
Le ton d'un autre titre d'un article multi-sociétés n'est pas transféré au nôtre.
Les raisons et citations exactes figurent dans le fichier de labels et le cohort.

Lecture SQL de `news_ticker_sentiment` sur **ces 27 couples seulement** :
**zéro ligne présente** au contrôle. Cela ne signifie pas que toute la table
est vide. Aucun FinBERT n'a été relancé, et aucun score d'une projection courante
non liée à la bonne version de texte n'a été utilisé. Ce test ne valide donc
pas les seuils FinBERT `positive_score > 0.9` ou `negative_score > 0.9`.

Les textes peuvent commenter des mouvements déjà observés et avoir été mis à
jour après la publication déclarée. Une version archivée plus tard ne prouve
pas qu'un texte identique existait à cette heure de publication.

## 2. Protocole et fenêtres

Protocole/cohort figés à **18:03:12 Paris le 16 octobre 2026**, avant extraction
des prix et agrégation. Ancien cutoff des news inchangé : 15:48:49 Paris.
Le nouveau cutoff d'observation des cours est explicitement 18:03:12 Paris :
il ne remplace pas la borne des archives de news et ne prétend pas être ancien.

Uniquement barres existantes en base, **Alpaca SIP**, `5m`, prix `raw`, séance
régulière, OHLC cohérents et positifs, volume positif, pas de barre synthétique,
pas de doublon d'horodatage. `observed_at` des barres doit être présent et ne
pas dépasser le nouveau cutoff d'observation. Les cours récupérés tardivement
servent à une description, pas à prouver une disponibilité historique.

Calendrier NYSE officiel sans fallback semaine. Six barres terminées avant et
six après ; la barre contenant une publication hors grille est exclue. Si la
publication est hors séance, la fenêtre avant est la dernière demi-heure de la
séance précédente et la fenêtre après la première demi-heure de la suivante.
Ce n'est donc **pas toujours la demi-heure chronologique entourant la news**.

Quatre mesures distinctes :

| Mesure | Définition |
| --- | --- |
| Avant | Clôture de la dernière barre avant / ouverture de la première barre avant − 1 |
| Après 30 min | Clôture de la dernière barre après / ouverture de la première barre après − 1 |
| Écart entre fenêtres | Ouverture de la première barre après / clôture de la dernière barre avant − 1 |
| Variation reliant les fenêtres | Clôture de la dernière barre après / clôture de la dernière barre avant − 1 |

L'écart entre fenêtres comprend notamment l'overnight pour une annonce hors
séance ; il ne doit pas être assimilé à 30 minutes de réaction ni à un mouvement
capturable après ouverture. Prix bruts : dividendes/actions sur titres non
qualifiés ici, particulièrement pour les écarts nocturnes.

## 3. Tous les cas ayant une fenêtre complète

Variations en pourcentage ; RTH = publication en séance régulière. « Hors »
utilise la convention dernière demi-heure précédente / première suivante.

| Titre | Tonalité | Horaires | Avant | Écart entre fenêtres | Après 30 min | Variation reliant les fenêtres |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| EMR | Favorable | RTH | +0,3703 | +0,0625 | +0,4437 | +0,5065 |
| CCJ | Favorable | RTH | +0,2439 | −0,2920 | +0,0915 | −0,2008 |
| AEP | Favorable | RTH | +0,2223 | +0,0158 | +0,2099 | +0,2257 |
| SNPS | Favorable | Hors | −0,2440 | −0,3801 | −1,9157 | −2,2885 |
| CBRL | Favorable | Hors | +1,5084 | −0,1470 | −1,5765 | −1,7211 |
| SWKS | Défavorable | Hors | −0,1304 | −1,4232 | −0,0861 | −1,5080 |
| PRMB | Défavorable | Hors | −0,3692 | −0,7411 | +0,1867 | −0,5558 |
| TSM | Mixte/neutre | Hors | −0,0349 | −3,4892 | −1,3657 | −4,8073 |
| NTR | Mixte/neutre | Hors | −0,0715 | −1,0160 | +0,6650 | −0,3578 |
| UTHR | Mixte/neutre | Hors | −0,8827 | −0,0497 | −0,8496 | −0,8989 |

### Mouvement déjà présent avant ?

- Favorables : hausse dans la fenêtre avant pour **4/5**, contre **3/5** dans
  la fenêtre après. La moyenne avant est +0,4202 %, après −0,5494 %.
- Défavorables : baisse avant dans **2/2**, après dans **1/2**. Moyennes avant
  −0,2498 %, après +0,0503 %.

Cette observation est compatible avec des commentaires accompagnant une
tendance déjà en cours, mais **ne prouve pas une causalité ni une anticipation**.
Hors séance, la fenêtre avant se situe à la précédente clôture, pas forcément
juste avant publication. La fenêtre de 30 minutes ne montre pas l'heure de début
exacte du mouvement. Les cours déjà cités dans les articles ne sont pas des
prédictions réalisées par notre système.

### Lecture par horaires : descriptive, pas nouveau filtre

Après le premier résultat agrégé, une lecture séparée de **toutes** les deux
catégories horaires est enregistrée. C'est un décompte explicatif postérieur,
pas une validation hors échantillon d'un filtre « trader seulement en séance ».
Aucun label, seuil ou cas n'a été changé et aucune stratégie optimisée.

- Trois favorables en séance : après moyen **+0,2484 %**, 3/3 hausses, mais
  tous sur **la même date** ; hausse également présente avant dans 3/3.
- Deux favorables hors séance : après moyen **−1,7461 %**, zéro hausse sur deux.
- Deux défavorables hors séance : après moyen **+0,0503 %** ; la baisse reliant
  les fenêtres, −1,0319 % en moyenne, provient principalement de l'écart nocturne.

Trois cas d'une seule date ne valident pas une règle horaire. Marché, secteur,
macro, liquidité, autres articles simultanés et sélection de couverture ne sont
pas contrôlés. Aucun p-value/AUC ni intervalle reposant sur une fausse indépendance
des articles n'est présenté.

## 4. Après notre réception réelle : non mesurable ici

Un second panneau applique la même convention autour de
`max(text_available_at, mapping_available_at)` : **0/27 fenêtres complètes**.
Les séances nécessaires à ces réceptions ne sont pas couvertes par les barres
présentes pour ces couples. Aucune collecte supplémentaire n'a été lancée.

Les dix fenêtres complètes autour de la publication se terminaient toutes
**avant notre réception réelle des preuves**. De plus, les labels qualitatifs
de cette étude n'existaient pas historiquement : leur disponibilité est celle
du 16 octobre à 18:03 Paris. Même un panneau de cours après réception complet
ne suffirait pas à prouver une stratégie exécutable utilisant ces labels.

## 5. Conclusion et limites

**Le petit test demandé a bien produit des chiffres**, pas seulement un contrôle
de disponibilité. Il ne démontre ni un avantage directionnel stable ni
l'inutilité des news. Les opinions favorables/défavorables ne donnent pas une
réaction uniforme ; un commentaire peut suivre le prix plutôt que l'anticiper.

Ce résultat ne doit pas être généralisé aux milliers de news, aux scores FinBERT,
au TOP20 Oracle, à H20, ou à une sélection LONG/SHORT. Les trois cas neutres sont
des textes mixtes, pas un échantillon apparié « sans news » ; les anciens témoins
de mots-clés peuvent parfaitement avoir une tonalité favorable ou défavorable.

Pas d'entraînement, filtre live, simulation de gains, adaptation des stops ou
nouvelle règle horaire suite à ces chiffres. Les collectes et scores existants
ne sont pas modifiés. Un test confirmatoire plus large nécessiterait une autre
fenêtre figée et des scores liés aux textes, sans réajuster les labels sur les
mouvements constatés ici.

## 6. Preuves et reproduction

Racine : `artifacts/research/us_news_price_descriptive/20261016-frozen-pilot-v1/`.

- `protocol.json`, `cohort.json`, `preparation_report.json`, `exclusions.json` :
  protocole, étiquettes et périmètre avant extraction.
- `results/report.json` : synthèse des deux panneaux.
- `results/cases.json`, `results/intraday_rows.json` : détails et entrées utilisées.
- `results/current_contextual_sentiment.json` : contrôle local des scores,
  zéro ligne pour ces couples, pas utilisés comme étiquettes.
- `clock_readout.json` : lecture explicite par horaires, signalée postérieure.

Scripts et labels sous `scripts/research/us_news_price_descriptive*20261016*`.
Les résultats et sources sont liés par empreintes. Dossiers immuables, pas
d'écrasement. Les tests couvrent les ratios, gaps, mélange de flux refusé,
dates futures, volume/synthétiques/doublons, citations et lecture horaire.

```powershell
python -u -m scripts.research.us_news_price_descriptive_20261016 --phase prepare --pack artifacts/research/us_news_event_qualification/20261016-financing-screen-closure-v2 --labels scripts/research/us_news_price_descriptive_labels_20261016.json --output artifacts/research/us_news_price_descriptive/NOUVEAU-TEST
python -u -m scripts.research.us_news_price_descriptive_20261016 --phase run --output artifacts/research/us_news_price_descriptive/NOUVEAU-TEST
python -u -m scripts.research.us_news_price_descriptive_readout_20261016 --experiment artifacts/research/us_news_price_descriptive/NOUVEAU-TEST
```

Reproduire dans un dossier neuf implique un **nouveau cutoff d'observation des
cours**, pas une réplication de la base historique exactement identique.
Les fichiers d'entrée du premier test permettent son contrôle sans refaire
de requête. La sélection de textes et les labels restent fixes.

Vérification finale : **81 tests ciblés réussis**, sans accès à la base métier
dans les tests. Aucun paramètre de production modifié.

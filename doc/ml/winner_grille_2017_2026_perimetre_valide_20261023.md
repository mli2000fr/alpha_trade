# Grille Winner : période 02/06/2017–30/09/2026 validée

## Décision et état

Le 23 octobre 2026, l'utilisateur confirme explicitement la période proposée.
2016–01/06/2017 reste une période d'amorçage ; aucun rendement ne sera inventé
pour cette période sans scores causaux. 2017 et 2026 sont des années partielles.
Le signal du vendredi 2 juin 2017 est disponible après clôture : première
entrée possible le lundi 5 juin, pas à l'ouverture du 2 juin.

**Qualification des scores terminée ; préparation des données intraday encore
nécessaire. Aucune grille économique lancée, aucun TOP3 calculé.**

## Scores figés sans lecture des rendements futurs

Script : `scripts/research/us_winner_grid_scores_2017_2026_20261023.py`.
Sortie valide :
`artifacts/research/us_winner_grid_scores_2017_2026/20261023-v2/`.
La tentative v1 a échoué à la sérialisation de dates de fold hétérogènes ; aucun
bilan valide v1. Le format est normalisé en datetime avant écriture v2.

Les seules colonnes lues dans les archives OOF sont date, symbole, score et
fold. Les labels, excursions et rendements terminaux ne sont pas lus.
Contrôle des contrats, poids et empreintes des folds ; disponibilité des
labels train/validation strictement antérieure à chaque date scorée.

Allocation fixée, sans choisir le modèle selon ses performances réalisées :

| Années scorées | Modèle |
| --- | --- |
| 2017–2024 | `model-factory-20261014113215-437ed1` |
| 2025 | `model-factory-20261014113226-102eca` |
| 2026 | `model-factory-20261014113232-bc35a7` |

Sur les dates OOF, utiliser toute la population disponible dans l'archive,
restreinte à l'univers actuel figé de 1 790 titres. Pour les seules dates
entièrement absentes des OOF, utiliser les scores SQL du même modèle, avec
lineage vérifiée (fold canonique, disponibilité, hash poids/profil, cible H20).
Ne pas mélanger quelques scores SQL et OOF à l'intérieur d'une même date.
Égalité des scores départagée par symbole. Classement avant toute qualification
des prix futurs ; ne pas remplacer un titre TOP10 mal couvert par le suivant.

Résultat : **2 345 séances et 23 450 lignes TOP10**, 347 symboles distincts.
1 983 dates issues des OOF, 362 de SQL. Population scorée observée par date :
1 482 à 1 790 titres. Aucun jour attendu sans au moins vingt scores causaux.
Le contrôle minimal des compteurs ne prouve cependant pas, à lui seul, que
tous les titres historiquement éligibles ont été scorés.

| Année | Séances scorées | Lignes TOP10 |
| --- | ---: | ---: |
| 2017, depuis le 2 juin | 147 | 1 470 |
| 2018 | 251 | 2 510 |
| 2019 | 252 | 2 520 |
| 2020 | 253 | 2 530 |
| 2021 | 252 | 2 520 |
| 2022 | 251 | 2 510 |
| 2023 | 250 | 2 500 |
| 2024 | 252 | 2 520 |
| 2025 | 250 | 2 500 |
| 2026, au 30 septembre | 187 | 1 870 |

Contrôles supplémentaires : pas de doublon date/symbole, rangs 1..10 par date,
disponibilité modèle strictement antérieure au signal. Six tests unitaires
passent (nouveaux tests et préparation précédente). Les premières tentatives
pytest ont échoué sur l'accès au dossier temporaire ; la relance avec un
dossier temporaire dédié dans le workspace passe, sans changer la logique.

Lectures SQL dans une transaction READ ONLY ; ni collecte fournisseur,
écriture SQL, entraînement, ordre, ni configuration de production modifiée.

## Données et calcul économique restant à réaliser

Le téléchargement 2018 a été relancé séparément à la demande de l'utilisateur,
sur le même plan `intraday-5dfcdc71cfaf4819ed1b`, sans refresh : 18 679 tranches
déjà traitées conservées, 4 591 à reprendre après un HTTP429. HOV récupéré,
progression constatée à 18 824/23 270, zéro échec courant. Ce compteur est un
snapshot, pas l'état final ; voir `progress.json` et les logs du collecteur.

Avant tout TOP3 économique :

1. Qualifier la couverture SIP raw régulière 5m réellement nécessaire aux
   347 titres, par séance et fenêtres d'attente/détention. Finir le rattrapage
   2018 et distinguer réponses vides, IPO/radiations, identités et vrais trous.
2. Figer daily, secteurs (actuels/non PIT), événements et hypothèses de coûts ;
   expliciter les exclusions de couverture et leur biais, sans reranker.
3. Sceller la grille LONG du runtime Winner, la règle de risque, capital annuel,
   levier effectif plafonné par le risque, coûts et traitement des positions
   ouvertes en fin d'année. Ne pas reprendre l'ancien moteur rapide J+H comme
   équivalent du runtime depuis le fill. Inclure les variantes récentes
   SL3/TP7 ou TP15/TR3/open11 dans la comparaison annoncée.
4. Faire smoke et audit de parité avant le calcul lourd, puis comparaison
   annuelle rendement/DD, taux gagnant, gains/pertes, durées et capital utilisé.
   Vérifier robustesse et voisinage avant de retenir trois profils.

Le nouveau snapshot des scores n'est pas présenté comme une reproduction
exacte de la cohorte 2025/2026 des expériences précédentes : préférence OOF
explicitée, périmètre et qualité devront être comparés et publiés.
Univers actuel survivant et archives disponibles aujourd'hui : pas de preuve
d'univers historique PIT complet. Aucune période déjà examinée ne devient
un holdout indépendant parce qu'on élargit les dates.

# Combinaisons de protections : synthèse des résultats déjà calculés

30 octobre 2026. Lecture des CSV et audits existants uniquement ; aucun nouveau
backtest, entraînement, téléchargement, ordre ou paramètre de production modifié.
**Pas de combinaison universellement validée.** Les périmètres ci-dessous doivent
rester séparés, notamment TOP10/demi-position et TOP20/position complète.

## Grille longue : profils présents sur toutes les périodes calculées

Source : `artifacts/research/us_winner_native_grid_2017_2026/20261023-v1/annual-*.csv`.
La grille est arrêtée par l'utilisateur à 2 588/3 000 comptes : 2018 absente et
2023 partiellement calculée. 188 profils disposent des neuf périodes suivantes :
2017 partiel, 2019–2025, 2026 jusqu'au 30 septembre. Aucun chiffre 2018 inventé.

TOP10 Oracle, LONG, demi-position sans renfort, capital neuf 4 000 USD par année,
plafond d'admission 1x, confirmation Winner, frais 8 pb par jambe, B4/DD15 natif.
Les rendements annuels ne constituent pas un compte continu. Les DD ci-dessous
sont les pires DD des comptes annuels, pas un DD sur dix années réinvesties.

Lecture descriptive, tri effectué maintenant sur les résultats déjà vus :
nombre de périodes positives, puis meilleure pire période et médiane. Ce tri
n'est pas le classement ex ante du protocole initial, ni un TOP3 définitif
de la grille inachevée.

| SL | Trailing | TP | Détention | Périodes positives | Rendement médian par période | Pire rendement par période | Pire DD annuel |
|---|---|---|---|---:|---:|---:|---:|
| 5 % | 15 % | Aucun | H15, sortie open16 | 6/9 | +4,84 % | −3,34 % | −19,07 % |
| 5 % | Aucun | Aucun | H10, sortie open11 | 6/9 | +7,60 % | −9,94 % | −20,58 % |
| 5 % | 20 % | Aucun | H10, sortie open11 | 6/9 | +3,74 % | −10,38 % | −18,06 % |

Le premier est le plus équilibré selon cette lecture des périodes disponibles,
mais perd en 2017, 2022 et 2026. Le deuxième a une médiane supérieure, au prix
d'une pire période et d'un DD plus défavorables. Le troisième réduit un peu le
pire DD annuel, sans dominer les autres critères.

À titre de repère, SL5/sansTP/trailing/H20 n'a que 5/9 périodes positives,
une médiane de +3,54 %, une pire période à −13,16 % et un pire DD annuel à
−23,42 %. SL5/TR15/sansTP/H20 : 5/9, +7,48 %, −8,64 %, −18,98 %.
Ces résultats empêchent de présenter le SL5/H20 comme une solution robuste
sur toutes les périodes, malgré les bons résultats TOP20 dans un autre contrat.

## TOP20 : comparaison contrôlée des stops, compte continu 2020–2024

Source : `artifacts/research/us_winner_sl3_min70/20261025-v1/comparison-sl1-sl3-sl5.csv`.
Capital neuf 4 000 USD, minimum notionnel 70 USD, positions complètes, cap1x,
sans renfort, sans TP/trailing, détention20 séances puis open21, frais inclus.
Pas de remise à zéro annuelle ou de nouvelle liquidation/pause globale. Même
admission historique SL3 conservée dans les trois bras ; ce n'est pas un
redimensionnement intégralement libre à chaque valeur de stop.

| SL | Capital final | Rendement cumulé 5 ans | DD global | Taux gagnant |
|---|---:|---:|---:|---:|
| 1 % | 9 189,83 USD | +129,75 % | −32,98 % | 5,41 % |
| 3 % | 5 579,72 USD | +39,49 % | −54,09 % | 12,86 % |
| 5 % | 13 641,66 USD | +241,04 % | −36,25 % | 21,33 % |

SL5 est la référence rendement/risque la plus convaincante de ce comparatif.
SL1 réduit le DD de seulement 3,27 points tout en abandonnant beaucoup de gain.
SL3 est moins favorable aux deux critères que SL5 dans ce compte. Ces trois
cas ne prouvent rien sur d'autres stops, un TP ou un autre horizon.

## Robustesse et contexte des résultats

L'[audit de robustesse du 21 octobre](oracle_robustesse_grille_20261021.md)
avait trouvé un plateau local SL7/TR15/H20/sansTP, résistant aux frais et à un
retard d'entrée sur 2025/2026. Mais son horizon incluait l'attente depuis Oracle,
sa cohorte était beaucoup plus petite et les gains dépendaient de quelques
contributeurs. Ce n'est pas une validation du même profil dans le runtime de
détention depuis l'entrée utilisé par les grilles plus récentes.

Les pauses DD15 et les sélections mensuelles n'ont pas établi une réduction
fiable du DD historique : les pertes des cycles s'accumulent. Voir le
[comparatif pauses](winner_pause20_bilan_20261026.md) et le
[comparatif mensuel](winner_monthly_cycle15_30_50_100_bilan_20261025.md).

Les grilles sont exploratoires, sur périodes déjà examinées, avec biais de
couverture future, univers survivant et hypothèses de fills. Elles ne certifient
pas la parité broker/live. **Ces combinaisons n'ont pas été validées avec le
nouveau filtre options ni avec options + consensus.** Il faut conserver ces
résultats comme références, pas leur attribuer le rendement d'une combinaison
de filtres qui n'a pas été rejouée.

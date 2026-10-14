# Oracle parcours LightGBM — audit des pertes 2024–2026

## Verdict

Audit terminé le **13 octobre 2026 à 23:54 Paris**, sur les neuf portefeuilles
TOP10/20/50, TP20/SL10 sans trailing. **Toutes les sources sont vérifiées après
calcul**, les PnL sont réconciliés, les chemins des 1 388 positions/cas examinés
sont qualifiés par les contrôles internes. Ces portefeuilles se recouvrent :
ce ne sont pas 1 388 observations indépendantes ni une qualification indépendante
des prix par un deuxième fournisseur.

La difficulté principale est **l'achat LONG de titres dont l'amplitude future
est surtout baissière**, puis la chronologie des contacts TP/SL. Ce n'est pas
principalement une accumulation de hausses de +20 % sorties trop tôt. Les gaps
et les différences de payoffs monétaires pèsent aussi ; l'amplitude détectée ne
garantit ni direction favorable ni profit après risque/exécution.

**26 tests ciblés passent**, dont 14 pour cet audit. Aucun entraînement,
nouveau backtest, SQL, appel courtier/fournisseur, modification de TP/SL ou
promotion live. Le modèle et les neuf portefeuilles originaux sont inchangés.

## Périmètre et méthode

Source : `artifacts/research/us_oracle_path_economic/20261013-v1`.
Résultats : `artifacts/research/us_oracle_path_loss_audit/20261014-v1`.
Le nom du dossier est un identifiant de version ; exécution effective le 13.

LightGBM original, fold figé 2023-01-05, labels de validation disponibles au
plus tard le 2023-01-04. Univers de 1 790 titres, secteurs/industries actuels
acceptés mais non PIT. Capital annuel réinitialisé à 4 000 USD. Pas
d'intersection ATR dans la sélection ; sizing ATR natif conservé.
2026 : décisions jusqu'au 2 septembre, sorties jusqu'au 2 octobre.

Chaque position est raccordée à son score/rang Oracle et au régime archivé
**de sa date de décision**, puis à ses vrais fills simulés. Les legs partiels
sont regroupés par identité et date d'entrée. PnL des positions moins intérêts
de marge = résultat net du compte, avec tolérance de 0,000001 USD.

Les excursions sont mesurées sur les **vingt séances depuis l'entrée J+1**,
par rapport à l'open réellement exécuté. MFE = hausse maximale HIGH ; MAE =
baisse maximale LOW. L'open d'expiration après vingt séances est analysé
séparément et son HIGH/LOW ne gonfle pas le MFE/MAE.

Ces trajectoires sont rétrospectives : **pas une simulation de vente au maximum**.
Un HIGH du jour d'un stop peut être postérieur à la sortie. Pour l'opportunité
avant sortie, seules les séances strictement antérieures et les fills constatés
sont utilisés : une borne basse, pas un maximum intraday exact.
Un double contact TP/SL intrabar est marqué ambigu ; un contact à l'open prime.
Chemins incomplets/identités changées/CA non rebasées resteraient inconnus,
sans être déclarés gagnants ou perdants. Aucun cas observé ne nécessite ici
une opération sur titres effectivement subie par le portefeuille.

## 1. Direction et capture : TOP10

| Année | Positions perdantes | Baisse dominante, jamais +20 % | Hausse dominante, jamais +20 % | +20 % atteint, mais après SL |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 92 | 70 (76,1 %) | 20 | 2 |
| 2025 | 81 | 62 (76,5 %) | 13 | 6 |
| 2026 | 93 | 64 (68,8 %) | 16 | 13 |

Dans cette table, les trois groupes couvrent les pertes observées. « Dominant »
signifie le plus grand mouvement absolu pendant le chemin ; ce n'est pas une
prévision ou une certitude qu'un SHORT aurait été profitable.

En 2025, les premiers contacts observables sont **35 TP d'abord, 72 SL d'abord,
24 sans contact**. Le maximum absolu est haussier sur 66 positions et baissier
sur 65. Une trajectoire globalement haussière n'est donc pas nécessairement
compatible avec un LONG qui survit au SL10 : **9 chemins à dominance haussière
ont néanmoins touché le SL en premier**.

Les occasions de gain plus modeste existent : sur les 81 pertes de 2025,
**40** présentent une hausse pré-sortie confirmée d'au moins 5 %, **14** d'au
moins 10 %, **6** d'au moins 15 %. Les mêmes comptes TOP10 sont 47/19/7 en
2024 et 41/24/6 en 2026. Il s'agit de constats descriptifs, **pas du choix d'un
nouveau TP ou d'une preuve qu'on pouvait anticiper le retournement**.

La sortie quotidienne pourrait être étudiée plus tard pour ces gains partiels,
mais elle ne résout pas à elle seule les nombreuses baisses dominantes. Cet
audit ne justifie pas de conserver une position après le stop dur.

## 2. Pourquoi 2025 perd et 2026 gagne avec un taux de réussite similaire

| TOP10 | 2024 | 2025 | 2026 partiel |
| --- | ---: | ---: | ---: |
| PnL brut USD | +37,21 | −174,99 | +429,20 |
| Coûts USD | 80,00 | 46,74 | 59,81 |
| PnL net USD | −42,79 | −221,73 | +369,39 |
| Positions gagnantes | 40,26 % | 38,17 % | 38,00 % |
| Gain moyen d'une position gagnante USD | 44,82 | 34,32 | 46,83 |
| Perte moyenne d'une position perdante USD | 30,67 | 23,92 | 24,73 |
| Fréquence d'équilibre rétrospective | 40,63 % | 41,07 % | 34,56 % |

2024 est légèrement positif avant coûts, négatif après. **2025 est déjà
négatif avant coûts** : les supprimer ne résoudrait pas le problème.
2026 gagne grâce à des gains moyens plus élevés relativement aux pertes,
pas grâce à un meilleur taux de trades gagnants.

La fréquence d'équilibre est `perte_moyenne / (gain_moyen + perte_moyenne)`
avec les montants réellement observés en dollars. Ce n'est pas un seuil
prédictif de score, et son application future suppose à tort des payoffs constants.
Sizing ATR, expirations, gaps et variation du capital modifient ces montants.

### Gaps

En 2025 TOP10, **11 sorties sur gap sous le SL**. La différence entre leur
prix exécuté et le prix théorique du SL représente **159,72 USD**. Elle est
incluse dans le PnL, pas ajoutée comme coût une seconde fois.

Exemple important : **SRPT**, entrée 2025-11-03, sortie 2025-11-04,
perte nette **136,90 USD** pour un notional initial de **366,67 USD**.
La part de perte située sous le prix du SL représente **99,76 USD**.
Un SL10 ne garantit pas une perte maximale de 10 % sur un gap.
Les contrôles sont cohérents avec l'archive, pas une nouvelle validation
indépendante de cet événement par un fournisseur externe.

Ces écarts ne constituent pas un backtest où l'on pourrait supprimer les gaps :
changer les fills changerait aussi le capital, les décisions et les trades suivants.

## 3. Périodes et secteurs : diagnostic, pas veto appris après les pertes

2025 TOP10, cohortes **par mois d'entrée**, tous leurs résultats ultérieurs inclus :

- février : **−437,67 USD**, 24 positions, 12,5 % gagnantes ;
- mars : **−126,20 USD**, 13 positions, 15,4 % gagnantes ;
- avril : **−59,26 USD**, trois positions, aucune gagnante.

Le PnL mensuel marqué du compte est distinct : février **−422,14 USD**
(−10,09 %), mars **−147,08 USD** (−3,91 %), avril **−105,73 USD** (−2,93 %).
Mai/juin sont sans position/exposition dans ce replay ; la remontée annuelle
provient ensuite notamment d'août et octobre. Les tables conservent aussi les
cohortes de janvier suivant résultant des dernières décisions de décembre.

Les catégories actuelles les plus perdantes changent :
biotechnologies en 2024 (−385,08 USD) et 2026 (−105,33 USD), mais en 2025
la catégorie Biotechnology est **positive, +28,35 USD**. Les exclusions
sectorielles automatiques ne sont donc pas établies par cet audit. Les
catégories du référentiel sont parfois des industries, pas les onze grands
secteurs GICS homogènes ; elles ne sont pas historiques PIT.

### Régimes de marché

Toutes les entrées TOP10 des trois années ont lieu en mode applicatif
`normal`. Les périodes `capital_preservation` existent mais ne produisent
pas ces entrées : le mécanisme de restriction a bien été conservé. Cela
ne prouve ni que `normal` garantit une hausse ni que le régime est idéal.

Le contexte SPY fondé sur ses SMA50/SMA200 à J donne :

| Contexte à la décision, TOP10 | 2024 PnL USD | 2025 PnL USD | 2026 PnL USD |
| --- | ---: | ---: | ---: |
| BULL | −264,20 | −186,04 | +168,82 |
| CORRECTION | +221,42 | +100,65 | −14,92 |
| SLIDE | aucune entrée | −136,35 | +215,50 |

**Un veto LONG sur `SLIDE` aurait retiré des pertes en 2025 mais également
des gains en 2026.** Soustraire ces PnL après coup n'est pas le résultat d'un
portefeuille rejoué, car les allocations suivantes changeraient. Aucun veto
de régime ni aucun seuil macro n'a été choisi ou testé ici.

## 4. Réentrées : particularité intéressante mais non stable

« Première entrée » = première sur un symbole **dans cette cohorte annuelle**,
pas première de son histoire ; les cohortes repartent en cash.

| TOP10 | Première entrée USD | Réentrées USD | Réentrée ≤5 jours calendaires après une perte USD |
| --- | ---: | ---: | ---: |
| 2024 | +300,26 | −343,05 | +70,01 |
| 2025 | +142,48 | −364,21 | −243,38 |
| 2026 | −96,44 | +465,83 | +143,04 |

En 2025, 26 réentrées rapides après perte expliquent une contribution négative
importante. Mais cette famille est positive en 2024 et 2026 : **pas de preuve
pour interdire toutes les réentrées**, ni pour régler un délai sur ces pertes.
Les protections de concentration/blacklist existantes restent inchangées.

## 5. Pourquoi TOP20 = TOP50 en 2024

Comparaison exacte : **trades identiques, décisions approuvées identiques,
courbes quotidiennes identiques**. Dans TOP50, le rang Oracle maximal d'une
position exécutée est **12** : aucun des rangs 21–50 n'a effectivement ouvert
une position. Ce n'est pas simplement un arrondi identique du rendement.

Le portefeuille reste limité à huit positions ; 138 séances ont huit positions
en fin de journée dans les deux cas. Les logs comptent 2 800 événements de
capacité LONG pour TOP20 et 9 480 pour TOP50, ainsi que des limites par
catégorie et des filtres de concentration. Ces événements ne constituent pas
un décompte exhaustif de refus uniques, donc tous les non-trades ne peuvent
pas être attribués à la seule capacité. **Élargir le pool ne signifie pas
acheter davantage**, et n'a ici changé aucune exécution.

## Suite recommandée, pas lancée

Priorité : une qualification d'un **filtre d'entrée conditionnel aux candidats
Oracle parcours**, pour distinguer les chemins compatibles avec un LONG
TP20 avant SL10, plutôt qu'un assouplissement du stop. Il faut d'abord vérifier
si les données disponibles à J séparent réellement les futurs perdants/gagnants.
Ce n'est pas une promesse de signal ou une justification de refaire à l'identique
les expériences directionnelles déjà négatives.

Les trajectoires futures de cet audit ne doivent jamais devenir des features
d'entrée. Une éventuelle hypothèse doit être figée avant son évaluation, avec
purge des labels, baseline identique et replay complet capital/coûts/risque.
2024–2026 ont déjà été explorés : aucune revendication de holdout vierge.
Un filtre global sur un mois, un secteur, `SLIDE` ou les réentrées n'est pas
promu à partir de ces chiffres. **Un nouveau GO est nécessaire pour la suite.**

## Fichiers et reproductibilité

- `report.md` / `report.json` : neuf cas, compteurs, groupes et comparaisons ;
- `positions-diagnostic.parquet` : chemin complet, MFE/MAE, premier contact,
  rang, régime J, coûts, réentrées et PnL par position ;
- `closed-legs-costs.parquet` : coût et excès de gap par leg ;
- `monthly-mtm.csv`, `entry-months.csv`, `sectors.csv`, `regimes.csv`, `symbols.csv` ;
- `protocol.json` : sources/empreintes figées avant calcul ;
- `progress.json` : **COMPLETED, 9/9**.

Code : `scripts/research/us_oracle_path_loss_audit.py`.
Tests : `tests/test_us_oracle_path_loss_audit.py`.

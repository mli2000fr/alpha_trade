# Oracle : décomposition nuit / séance, TOP10 et TOP20 %

## Conclusion du 20 octobre 2026

**Test terminé et audité : aucun avantage directionnel stable à promouvoir.**
Le suivi du mouvement réalisé en séance donne un résultat intéressant dans le
TOP10 en2026, mais perd en2024 et2025. L’élargissement au TOP20% ne résout pas
cette instabilité. Ni le signal de nuit ni l’accord nuit/séance ne passent les
critères figés. Les horizons5 et10 n’apportent pas de confirmation transversale.

Les chiffres suivants sont des **moyennes nettes par occasion indépendante de
vingt séances**, pas des rendements annuels du capital, ni une simulation du
portefeuille live. Entrée à l’ouverture suivante, sortie à la clôture de la
vingtième séance, **sans TP, SL ou trailing**. Coûts hypothétiques inclus.

| Périmètre | Direction choisie | 2024 | 2025 | 2026 partiel |
|---|---|---:|---:|---:|
| TOP10 | Tendance en séance | **−3,274%** | **−2,577%** | **+4,571%** |
| TOP10 | Tendance de nuit | −2,497% | +0,383% | −2,006% |
| TOP10 | Accord nuit/séance, abstention sinon | −5,225% | −2,083% | +2,709% |
| TOP10 | Référence toujours LONG, sans filtre | +1,009% | +4,905% | +3,784% |
| TOP20% | Tendance en séance | **−0,483%** | **+0,462%** | **+0,953%** |
| TOP20% | Tendance de nuit | −0,517% | −0,605% | −0,964% |
| TOP20% | Accord nuit/séance, abstention sinon | −0,830% | +0,131% | +0,231% |
| TOP20% | Référence toujours LONG, sans filtre | +0,795% | +1,675% | +1,841% |

Le tableau donne la référence LONG sur toutes les occasions admissibles. Pour
le bras accord, dont la couverture est plus faible, **le verdict statistique
utilise bien une référence LONG sur exactement ses propres occasions**, pas
une comparaison naïve avec la dernière ligne de son périmètre.

Toutes les six comparaisons primaires échouent au protocole ; pas de nouvelle
fenêtre, inversion de signal ou régime choisi après lecture des pertes.

## Hypothèse, source chinoise et différence avec les anciens essais

La [thèse Tsinghua2025 sur les rendements de nuit et de séance](https://newetds.lib.tsinghua.edu.cn/qh/paper/summary?dbCode=ETDQH&sysId=302463)
discute la décomposition des rendements et les différences Chine/États-Unis.
Son résumé ne conclut pas à un effet universel : plusieurs résultats sont
spécifiques aux facteurs et au marché. Nous empruntons une question de
recherche, **pas une performance ni une règle propriétaire prétendument
reproduite**.

Un titre peut présenter une tendance positive globale tout en étant vendu
pendant la séance et acheté entre clôture et ouverture. Nous cherchons si ces
deux composantes, suivies sur vingt séances passées, aident à choisir le sens
des mouvements futurs après l’Oracle.

Ce n’est pas le précédent test des cinq minutes de la séance J, ni la première
cassure intraday après J. Aucun historique intraday n’est nécessaire ici :
les ouvertures et clôtures daily suffisent sous une base d’ajustement cohérente.

## Protocole figé avant lecture des résultats

L’utilisateur a autorisé le TOP20% en complément avant le calcul des résultats.
Le TOP10 reste le périmètre principal ; le TOP20% est une comparaison distincte,
pas un remplacement opportuniste parce qu’un résultat serait meilleur.

### Entrées et sélection

- Univers courant de1790titres, fichier
  `config/univers_batch/univers_filtred_tradable.txt`, figé par empreinte.
- Scores **Oracle amplitude parcours H20 CatBoost de recherche**, annuels2024,
  2025 et2026 :
  `artifacts/research/us_h10_h20_frozen_comparison/20261019-v1/`.
- Ce sont les références annuelles déjà auditées de cette recherche ; **pas un
  nouveau training, pas le modèle live courant, pas les rangs Oracle H10**.
  L’audit d’origine vérifie la maturité des labels avant les années de test.
- Seulement `date/symbol/rank/score` sont lus dans les scores ; aucune colonne
  de cible future/amplitude future ne choisit les membres.
- Classement `score DESC, symbole ASC` contrôlé. TOP10 strict et
  `ceil(20% × nombre scoré du jour)` ; aucun rang suivant ne remplace un titre
  dont les prix sont ensuite invalides.
- **1195076lignes de scores**,669séances, du2janvier2024 au1septembre2026.
  Sélections :6690couples TOP10 et239074couples TOP20%.
- Prix de2023 pour l’amorçage ; suivi disponible jusqu’au30septembre2026.
  Les signaux2026 s’arrêtent au1septembre pour la maturité H20.

### Trois règles directionnelles, deux références

Pour chaque clôture J, sur les20séances terminant à J :

```text
Intraday20  = somme log(clôture_t / ouverture_t)
Overnight20 = somme log(ouverture_t / clôture_(t−1))
Close20     = Intraday20 + Overnight20
```

Les deux premières composantes exigent21barres historiques pour couvrir la
clôture précédant le premier gap. L’identité multiplicative est contrôlée :
`exp(Close20) = clôture_J / clôture_(J−20)`.

| Règle | Décision à J après clôture |
|---|---|
| `INTRADAY20` | LONG si composante séance positive, SHORT si négative |
| `OVERNIGHT20` | LONG si composante nuit positive, SHORT si négative |
| `AGREEMENT20` | Même sens si les deux sont de même signe ; sinon abstention |
| `CLOSE20`, référence | Signe de la performance quotidienne composée globale |
| `ALWAYS_LONG`, référence | Toujours LONG sur les mêmes occasions admissibles |

La tolérance1e−12 sert uniquement aux zéros numériques, pas à filtrer un
mouvement jugé trop faible après observation des résultats. Une issue future
plate reste un résultat net après frais mais sort du dénominateur de précision
directionnelle ; elle n’est pas artificiellement appelée baissière.

### Exécution diagnostique et coûts

- Information arrêtée à la clôture J ; entrée à **J+1open**, jamais à l’open J.
- Horizon principal20séances ; sensibilités5 et10. La séance d’entrée compte
  comme première séance ; sortie à la clôture de J+H.
- Pas de TP/SL/trailing, couverture marché, optimisation ou réentraînement.
  Le test mesure une direction, pas le gain d’une nouvelle gestion de risque.
- Unité de notionnel initial indépendante par occasion. Commission/spread/
  slippage regroupés dans une hypothèse de **10bps par jambe**, dont sortie
  facturée sur son notionnel réel ; stress25bps par jambe.
- Pour SHORT : emprunt hypothétique0,3% annuel du notionnel initial, ACT/365.
  Aucune disponibilité historique du prêt, marge, fills, capital partagé,
  réinvestissement ou coût de financement broker n’est certifié.

Un rendement moyen positif d’occasions n’est donc pas un rendement annuel
mobilisable, ni une autorisation de short réel ou de levier.

## Prix, ajustements et cas inconnus

Source : copie normalisée et déjà auditée de recherche
`artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet`.

L’ouverture, le haut, le bas et la clôture sont tous multipliés par le facteur
**du même jour** `adj_close / close`. Ne pas comparer une ouverture brute avec
une clôture ajustée : cela créerait de faux gaps sur splits/distributions.
Ce proxy ajusté fournisseur ne certifie pas les flux de dividendes du courtier
ni tous les événements économiques des actions.

Les fenêtres doivent avoir OHLC/volume valides, aucune barre artificielle,
identité/fournisseur/base connus et stables. Aucun forward-fill. Réserves DD
à partir du3novembre2025 et TOELY à partir du13juillet2026 conservées.
Les anciennes réserves de features ne sont pas réutilisées comme features :
les trois mesures de prix sont recalculées depuis la copie normalisée.
Les exclusions appliquées dans les scores Oracle source restent héritées.

### Contrôle sans chevauchement, principal

Pour chaque symbole et périmètre, prendre la première appartenance disponible,
**avant** d’examiner l’historique, le sens ou les prix futurs, puis bloquer
jusqu’à la clôture vingt séances plus tard. Une nouvelle décision à cette
clôture peut entrer le lendemain. Un cas inconnu bloque aussi l’intervalle ;
aucun remplacement par un signal ultérieur mieux documenté ou gagnant.
La procédure ne repart pas à zéro au changement d’année.

| Périmètre | Année | Occasions initiales sans chevauchement | Prix/historique qualifiés H20 |
|---|---:|---:|---:|
| TOP10 | 2024 | 255 | 255 |
| TOP10 | 2025 | 248 | 248 |
| TOP10 | 2026partiel | 170 | 170 |
| TOP20% | 2024 | 5734 | 5734 |
| TOP20% | 2025 | 5479 | 5477 |
| TOP20% | 2026partiel | 3509 | 3451 |

Les rares signes zéro entraînent ensuite une abstention selon la règle. Les
statistiques avec toutes les appartenances quotidiennes, fortement
chevauchantes, sont conservées comme secondaires dans les artefacts.

## Précision directionnelle et D1/D10

Pour le signal séance, hors chevauchement, sur le signe du résultat à H20 :

| Périmètre | 2024 | 2025 | 2026partiel |
|---|---:|---:|---:|
| TOP10 | 43,92% | 44,35% | **60,00%** |
| TOP20% | 49,76% | 52,10% | 52,07% |

Le60% de2026 n’est pas un signal validé en trois ans, et l’accuracy de50% n’est
pas nécessairement la référence correcte : la fréquence de hausse varie. La
référence LONG TOP10 est elle-même correcte50,98%/60,89%/48,24% sur ces années.

Les queues D1/D10 secondaires sont reconstruites sur **tout l’univers scoré
et qualifié en prix à la date/horizon**, jamais sur les dix titres seuls :
10% les plus faibles et10% les plus forts des rendements entrée-open→sortie-close.
Elles ne sont admises que si≥95% de l’univers scoré a un parcours qualifié.
Elles sont donc **conditionnelles à cette couverture**, et différentes des
labels D1/D10 SQL historiques ou du signe du maximum absolu du parcours.

Disponibilité des queues :664/669dates à H5,659/669 à H10,649/669 à H20.
À H20, signal séance TOP10 : précision dans ces seules queues
41,98%/42,64%/70,11%, sur131/129/87observations. Même bascule2026, aucune
stabilité démontrée. Aucun label SQL n’a été réécrit.

## Résultats agrégés et incertitude

Les six tests primaires sont trois règles × deux périmètres, H20 hors
chevauchement. Intervalles par bootstrap de blocs de20séances de calendrier,
1999tirages, graine20261020, moyenne pondérée par nombre d’occasions. Les
intervalles principaux sont corrigés pour ces six tests, pas pour toute notre
histoire de recherche.

| Périmètre/règle | Moyenne nette par occasion, trois années | Écart à LONG mêmes occasions |
|---|---:|---:|
| TOP10 séance | −1,036% | −4,181points |
| TOP10 nuit | −1,312% | −4,457points |
| TOP10 accord | −2,113% | −5,887points |
| TOP20% séance | +0,208% | −1,160point |
| TOP20% nuit | −0,655% | −2,025points |
| TOP20% accord | −0,223% | −1,450point |

TOP20% séance : IC95 net **[−0,438%; +0,991%]** ; écart à LONG mêmes occasions
**[−2,980; +0,610]points**. Son petit gain absolu ne démontre ni gain significatif
ni supplément sur la référence. Les critères annuels et les intervalles
corrigés ne passent pour aucune des six règles.

### Décomposition LONG/SHORT demandée au protocole

Le bras SHORT du signal séance dans le TOP20% reste négatif sur les trois
années : **−1,336%/−1,334%/−1,106%** nets moyens. Son bras LONG est positif :
**+0,641%/+2,561%/+2,986%**,2470/2523/1737occasions.

Ce dernier point reste **descriptif**, pas un nouveau filtre promu : face au
LONG non filtré du TOP20%, il est inférieur en2024 et supérieur en2025/2026.
Les ensembles et expositions sont différents. Cela ne prouve pas un gain
économique causal d’un filtre LONG seul, ni une combinaison validée avec le
consensus ou les news. Pas de nouvelle recherche de seuil lancée ici.

## Livrables et vérifications

Racine : `artifacts/research/us_overnight_intraday/20261020-v1/`.

- `protocol.json` : règles, sources et empreintes avant calcul.
- `candidates.parquet` :239074couples sélectionnés, features, résultats connus
  ou manquants, adhésions sans chevauchement fixées avant qualité future.
- `tail-coverage.parquet` : dénominateurs du plein univers scoré.
- `outcomes.parquet` : **3484710lignes de calcul**, couvrant règles, périmètres,
  horizons et admissions ; **pas3484710trades indépendants**.
- `annual-summary.csv`, `coverage.csv`, `report.json`, `audit.json`.
- `readout-v1/side-summary.csv` :324décompositions LONG/SHORT ;
  `long-only-descriptive.csv` conserve les comparaisons à effectifs différents.
- Scripts sous `scripts/research/us_overnight_intraday_*` et tests associés.

**21tests ciblés passent**, dont causalité par préfixe, ajustements de split,
barres manquantes, fournisseur IEX rejeté, identité, entréeJ+1, horizon et coûts.
Un audit scalaire distinct contrôle245764admissions,250historiques et750issues
sur les prix originaux ; erreur maximale8,33e−16. Arithmétique des coûts et
références recalculée sur toutes les3484710lignes : écart maximal0.
Statut **PASS_OFFLINE_EXPLORATORY_ONLY** ; même assistant, pas une seconde revue
humaine indépendante ni une certification de toute l’application.

**Aucun modèle réentraîné ou promu, appel fournisseur/LLM, SQL écrit, ordre,
batch/configuration de production modifié ou calcul de portefeuille.** Les
années sont déjà explorées, l’univers courant est survivant, les ajustements
sont des versions fournisseur actuelles. Pas de calcul de recherche encore actif.

## Décision

Ne pas intégrer ces trois règles de sens à ML Predict, au risque ou au live.
Conserver le constat2026 et le diagnostic LONG comme pistes non confirmées,
sans les présenter comme une solution D1/D10. Ni l’élargissement du périmètre
ni le raccourcissement H5/H10 ne valident cette hypothèse figée.

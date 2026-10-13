# Comparaison des trois modèles Oracle — TOP50, 2024–2026

## Demande et périmètre

Comparer les trois identifiants fournis par l'utilisateur, sans réentraînement,
sans écriture SQL, sans remplacement de modèle de production et sans ordre broker.
Les challengers d'entrée, de sortie quotidienne et de TP/SL personnalisés
précédemment préparés restent suspendus : cette demande autorise seulement la
comparaison des modèles existants.

| Nom précis | Identifiant | Cible d'entraînement | Score de sélection |
| --- | --- | --- | --- |
| Oracle parcours H20 | `model-factory-20261012201432-834576` | TOP20 % de l'amplitude maximale high/low sur J+1…J+20 depuis le close J | `proba_path_extreme` |
| Oracle TP20/SL7 | `model-factory-20261012201220-a769bb` | TP +20 % avant SL −7 %, sur vingt séances | `proba_long_tp_before_sl` |
| Oracle TP20/SL10 | `model-factory-20261012183840-6d6569` | TP +20 % avant SL −10 %, sur vingt séances | `proba_long_tp_before_sl` |

**Attention : `834576` n'est pas l'Oracle terminal H20 historique.** Son
répertoire `oracle_path` et son protocole `oracle_path_h20` désignent la cible
parcours ; le test n'inclut pas un quatrième modèle terminal non demandé.
Le score parcours ne prédit pas la direction LONG : LONG est ici une stratégie
fixe de replay, identique à celle des baselines précédentes.

Les trois contrats possèdent 1 790 titres, 173 features, les mêmes options de
génération et le dernier fold `2023-01-05`. Les poids et leurs empreintes sont
vérifiés. Les labels de training/validation de ce fold sont disponibles avant
2024 ; il ne s'agit pas d'un refit implicite de toute l'année 2023.

## Comparaison contrôlée

Les mentions SL7/SL10 décrivent **l'entraînement**, pas les sorties comparatives.
Pour isoler l'effet du classement, chaque portefeuille utilise :

- LONG uniquement ; les cinquante meilleurs scores à J, décroissants, égalités
  départagées par symbole. Aucun rendement futur ni qualité future ne filtre le TOP.
- Probabilités brutes conservées, mais même rang normalisé fourni au sizing :
  pas de comparaison directe de scores non calibrés entre cibles différentes.
- Entrée open J+1, **TP20/SL10 pour les trois modèles**, barrières ancrées au fill.
- Trailing OFF ; expiration à l'ouverture de la 21e séance détenue.
- 4 000 USD réinitialisés par cas ; mêmes coûts canoniques, intérêts, cash,
  sizing ATR natif, contraintes de portefeuille et régime de marché.
- Maximum structurel natif de huit positions et limites sectorielles :
  TOP50 est une liste de candidats, pas cinquante achats simultanés.
- 2024/2025 : décisions sur chaque année, puis dénouements de la cohorte.
  2026 : décisions jusqu'au 3 septembre, sorties suivantes jusqu'au 5 octobre.

Ce protocole ne choisit pas a posteriori un stop propre au modèle qui gagne.
Comparer ensuite les protections d'origine serait une expérience distincte.

## Données et contrôles

La matrice commune et les prix viennent de la baseline réparée
`artifacts/research/us_oracle_tp20_sl10_new/20261012-v6`. Corrections locales
AVB/BAND/GPRE/ATEX alignées avec les features, conversion TOELY → TELWY qualifiée,
sans effacer les versions anciennes ni modifier les tables.
L'appartenance et l'ordre des candidats sont identiques avant inférence.
Le contrat de features de chaque modèle est comparé exactement à la matrice.
Les prédictions du modèle TP20/SL10 doivent reproduire la référence ; ses trois
portefeuilles sont recalculés, puis comparés exactement sur trades et compteurs.

Tout cas bloqué par prix/volume détenu manquant, identité ambiguë ou créance non
valorisée reste FAILED, sans suppression rétrospective du titre. Les cas
terminés vérifient TP/SL, durée, portefeuille clos et cash réconcilié.
Les hashes des inputs, modèles et sources sont vérifiés avant/après calcul.
30 tests ciblés passent avant lancement.

Réserves : univers statique de survivants, secteurs actuels/non PIT déjà acceptés,
prix ajustés actuels fournisseur, disponibilité historique macro/selector non
certifiée, protections après corporate action migrées en simulation. Les ADR
OTC ne prouvent pas une exécutabilité historique chez Alpaca. Les années ont
déjà été explorées ; aucun résultat n'est un holdout neuf ou une certification LIVE.

## Résultats et suivi

Statut final : **neuf cas terminés exploratoires, zéro échec, contrôle final validé**.
Racine : `artifacts/research/us_three_oracle_comparison/20261012-top50-v1`.

| Année | Modèle entraîné | Capital final $ | Gains $ | Pertes $ | Gagnants % | Perdants % | Rendement % | DD max % |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | Parcours H20 | 4240,16 | 3218,24 | −2978,08 | 42,86 | 57,14 | +6,00 | −12,63 |
| 2024 | TP20/SL7 | 4081,00 | 2290,80 | −2209,79 | 42,96 | 57,04 | +2,03 | −15,44 |
| 2024 | TP20/SL10 | 4657,43 | 2888,44 | −2231,01 | 44,08 | 55,92 | +16,44 | −8,46 |
| 2025 | Parcours H20 | 3686,50 | 1663,23 | −1976,73 | 34,25 | 65,75 | −7,84 | −20,15 |
| 2025 | TP20/SL7 | 3440,64 | 1248,35 | −1807,71 | 34,07 | 65,93 | −13,98 | −21,56 |
| 2025 | TP20/SL10 | 3757,96 | 1368,78 | −1610,82 | 37,50 | 62,50 | −6,05 | −16,26 |
| 2026 | Parcours H20 | 4345,77 | 3050,32 | −2704,55 | 38,15 | 61,85 | +8,64 | −12,51 |
| 2026 | TP20/SL7 | 4694,56 | 2537,88 | −1843,32 | 46,88 | 53,12 | +17,36 | −5,79 |
| 2026 | TP20/SL10 | 4857,15 | 2820,63 | −1963,48 | 48,25 | 51,75 | +21,43 | −9,10 |

Lecture bornée : TP20/SL10 présente le meilleur rendement dans chacune des
trois cohortes, et le meilleur taux gagnant, mais les trois modèles perdent en
2025. Il ne domine pas tous les risques : en 2026, TP20/SL7 a un DD plus faible
(5,79 % contre 9,10 %). La comparaison ne démontre ni rentabilité annuelle
stable ni supériorité de protections TP20/SL10 sur TP20/SL7 : les sorties sont
identiques ici, seuls les poids/classements des modèles changent.

Les trois références TP20/SL10 reproduisent exactement les tapes et compteurs
de la baseline précédente. `completion-audit.json` qualifie les neuf cas,
les mêmes clés de candidats, les prix/macro/lifecycle identiques, les modèles
attribués correctement, le LONG/TOP50, les TP/SL, échéances, portefeuilles clos
et cash réconcilié. Inputs, poids et code inchangés ; aucun entraînement,
SQL, ordre broker ou challenger précédemment suspendu lancé. Aucun modèle promu.

`manifest.json` conserve les contrats et empreintes. `progress.json` indique le
modèle, l'année et le nombre de cas ; `results-2024.json`, `results-2025.json`,
`results-2026.json`, puis `report.md/json` conservent les résultats détaillés.
Chaque modèle possède ses tapes dans `<modèle>/BASELINE/<année>-TOP50`.
Compteurs : capital initial/final, gains/pertes après coûts, net, positions
gagnantes/perdantes, pourcentages, profit factor, DD et réconciliation cash.

```powershell
Get-Content F:\projets\artifacts\research\us_three_oracle_comparison\20261012-top50-v1\progress.json
```

Un seul writer par racine. Ne pas modifier les inputs, sources ou configuration
pendant le calcul. La commande comparative ne lance ni `--phase experiments`
ni entraînement, et ne touche à aucun batch.

## Diagnostic rétrospectif des pertes 2025 — 13 octobre 2026

Lecture des tapes terminées, sans nouveau replay, entraînement, changement de
protections, écriture SQL ou ordre broker. Les noms TP20/SL7 et TP20/SL10
désignent les labels d'entraînement : les trois portefeuilles comparés utilisent
les mêmes sorties TP20/SL10, sans trailing, avec échéance après vingt séances.

Les pertes sont concentrées dans les signaux de février–mars, et non réparties
uniformément sur l'année. Attribution par **mois du signal** (PnL net des
positions une fois sorties, éventuellement le mois suivant) :

| Modèle | Signaux février | Signaux mars | Total cohorte 2025 |
| --- | ---: | ---: | ---: |
| Parcours H20 | −476,66 $ | −223,94 $ | −313,50 $ |
| TP20/SL7 | −330,24 $ | −232,47 $ | −559,36 $ |
| TP20/SL10 | −424,27 $ | aucune nouvelle entrée | −242,04 $ |

Pour TP20/SL10, seuls 4 des 26 trades issus de signaux de février sont gagnants.
Sur la cohorte complète : 48 gagnants / 80 perdants, soit 37,50 % gagnants,
contre 44,08 % en 2024 et 48,25 % sur la période partielle 2026.
Les gains nets cumulés sont 1 368,78 $, les pertes −1 610,82 $.

Les sorties TP20/SL10 en 2025 sont : 62 stops à −10 % (−1 291,25 $ net),
10 stops sur gap d'ouverture (−286,58 $, rendement prix moyen −13,42 %),
30 TP à +20 % (+1 146,36 $ net), et 26 échéances (+189,42 $ net).
Un stop n'est donc pas une garantie de perte maximale de 10 % lors d'un gap.
Les gains à échéance sont souvent inférieurs à +20 %, et les tailles de
position ne sont pas égales. Avec les gains/pertes moyens **en dollars**
observés (28,52 $ / 20,14 $), le taux gagnant d'équilibre descriptif est
41,39 %, supérieur aux 37,50 % obtenus. Ce seuil n'est pas une prévision
ni une nouvelle règle d'entrée.

Le régime était déjà pris en compte. Le contrôleur B4 réduit l'allocation
TP20/SL10 à 10 % dès le 3 mars ; pour les deux autres bras, dès le 3 avril.
La couche macro bascule en `capital_preservation` le 3 avril (14 séances sur
2025). Tous les bras sont sans positions en mai–juin ; les nouvelles entrées
reprennent en juillet. Les multiplicateurs restent réduits longtemps après
les premières pertes. Cela décrit une protection réactive et une reprise
limitée, pas une anticipation des pertes de février. Les tapes ne conservent
pas tous les rejets : la responsabilité respective du sizing minimum,
contrôleur, contraintes et éligibilité dans chaque journée sans entrée n'est
pas intégralement attribuée ici. Le code applique notamment le sizing ATR
au multiplicateur réduit et un minimum notionnel de 155 $.

Le SPY archivé progresse de **16,35 %** entre les dernières clôtures 2024 et
2025 (prix ajustés des splits, **hors dividendes**), avec −1,27 % en février,
−5,86 % en mars, puis +6,28 % en mai et +4,83 % en juin. « Toute la Bourse
baisse en 2025 » serait donc une mauvaise explication : la sélection LONG
souffre au début, puis reste en cash pendant une partie du rebond.
Ne pas en déduire le rendement qu'aurait obtenu une reprise forcée.

La perte n'est pas attribuable à un unique titre : dans TP20/SL10, les
contributions annuelles les plus négatives incluent LMND (−125,57 $), ONT
(−74,39 $), KURA (−74,11 $), MXL (−64,80 $) et XIFR (−57,14 $).
Ces sommes sont des contributions nettes avec des gagnants ailleurs ; elles
ne représentent pas des fractions exclusives de la perte finale.
Les secteurs utilisés restent des métadonnées actuelles non PIT.

Conclusion bornée : moins de trades gagnants et de TP, davantage de stops,
concentration temporelle des pertes et reprise défensive insuffisante pour
les compenser. Le régime explique une partie de la dynamique du portefeuille,
mais cette attribution ne démontre aucun filtre capable d'éviter les pertes
à l'avance. Ne pas supprimer février, ces titres ou ajuster les seuils sur
ces pertes puis présenter cela comme une validation hors échantillon.

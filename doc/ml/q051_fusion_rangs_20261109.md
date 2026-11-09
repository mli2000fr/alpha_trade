# TOP5 — fusion des classements per-symbol et per-sector, 50/50

GO utilisateur du 9 novembre 2026 après proposition de fusion relative plutôt
que croisement de deux listes TOP5. Les quatre replays sont terminés et importés
dans l’historique IHM. La fusion 50/50 n’est pas retenue.

## Règle figée avant le replay

Même univers 1 790 et mêmes Oracles annuels que Q051. Dans chaque séance :

1. Fixer les **179 candidats TOP10 % Oracle**, avant la disponibilité des
   scores directionnels ou l’examen des rendements futurs.
2. Garder les candidats ayant **les deux probabilités LONG disponibles**,
   finies dans [0,1], avec le bon poids du modèle et sa disponibilité strictement
   antérieure au signal. Aucun remplacement hors du TOP179.
3. Sur cette même population commune, convertir chaque probabilité en rang
   relatif : `(rang croissant moyen − 0,5) / nombre de candidats communs`.
   Une probabilité plus élevée donne un rang relatif plus élevé.
4. **Score fusion = 0,5 × rang relatif per-symbol + 0,5 × rang relatif
   per-sector**. Poids constants, ni recherche de pondérations ni ajustement
   suivant les résultats.
5. Retenir les cinq scores fusion les plus élevés. Égalité : priorité au
   rang d’amplitude Oracle, puis au symbole alphabétique. Aucun remplacement
   après veto du risque ou présence en portefeuille.

Cette variante **n’applique pas les seuils absolus de probabilité >0,50 ou
d’AUC ≥0,50**. Un score de rang n’est pas une probabilité de bénéfice ; les
cinq meilleurs candidats peuvent avoir des probabilités absolues inférieures
à 0,50. Cela ne constitue pas une double confirmation LONG absolue.

Les empreintes et dates des poids per-symbol et sectoriels ayant produit
chaque probabilité sont vérifiées. Le per-sector est celui de la reprise v4,
avec alignement SPY corrigé, sans réutilisation des prédictions v3 invalidées.
Pas de nouvel entraînement, nouvelle inférence de modèle ou appel fournisseur.

## Deux profils et deux témoins appariés

| Nouveau replay | Sélection | Protection |
|---|---|---|
| Q051_FUSION50 | TOP5 des rangs combinés 50/50 | Q051 |
| VOL20_FUSION50 | Même TOP5 fusion | Q051 + volatilité 20 % + régime |
| Q051_RELATIVE_SYMBOL | TOP5 per-symbol **sur la même population commune**, sans seuils | Q051 |
| VOL20_RELATIVE_SYMBOL | Même témoin relatif | Q051 + volatilité 20 % + régime |

Ces deux témoins supplémentaires distinguent l’effet de fusion de celui du
retrait des seuils. Les anciennes références avec seuils, sans filtre et
per-sector seul restent dans les tableaux comparatifs mais ne constituent
pas à elles seules une ablation isolée de la pondération 50/50.

## Données et couverture

Période continue **01/01/2021–31/12/2025**, capital initial **4 000 USD**.
Pas de reset annuel, mêmes Oracles annuels :

| Année d’entrée testée | Batch Oracle |
|---|---|
| 2021 | model-factory-20261107222539-837309 |
| 2022 | model-factory-20261107222557-280d86 |
| 2023 | model-factory-20261107222607-f44095 |
| 2024 | model-factory-20261107222618-89a4d2 |
| 2025 | model-factory-20261106203103-91b063 |

Comme les témoins, la sélection du dernier jour de l’année précédente peut
servir à l’entrée de la première séance. La disponibilité de chaque modèle
directionnel est vérifiée selon l’année de son signal, pas à partir d’un
modèle futur de l’année d’entrée.

| Année | Séances | Minimum de candidats avec les deux scores | Moyenne |
|---|---:|---:|---:|
| 2021 | 252 | 88 | 106,60 |
| 2022 | 251 | 83 | 95,51 |
| 2023 | 250 | 92 | 115,84 |
| 2024 | 252 | 117 | 133,72 |
| 2025 | 250 | 138 | 155,22 |

La sélection est réellement de cinq candidats sur chacune des **1 255
séances**, soit **6 275 signaux par variante relative**, sans fabriquer de
score manquant. Le nombre d’achats pourra être inférieur selon le capital,
les limites de risque et les positions déjà détenues.

## Risque identique aux comparaisons précédentes

Position complète, entrée à l’ouverture J+1 sans confirmation 5m, SL5 %,
sans TP/trailing/renforcement, sortie open11. Risque par entrée 1,25 %, poids
maximal 20 %, maximum 20 positions, minimum 50 USD, plafond achats **1×**, compte
margin de capacité 2×. B4/DD15, facteurs, corrélation et limites sectorielles
désactivés. Frais/slippage 8 pb par opération, financement annuel 6,5 %.

Le profil protégé ajoute seulement le budget de volatilité annualisée du
portefeuille **20 %**, covariance sur **60 séances antérieures**, et le régime
des nouvelles entrées **SPY J >98 % de SMA200**. Le budget réduit éventuellement
la quantité native et ne liquide pas les positions détenues.

Les prix quotidiens et 5m déjà figés dans les témoins sont réutilisés, ainsi
que le risque natif et Winner. Aucun changement du moteur ou de production.
Tous les rapports demeurent exploratoires : couverture 5m partielle avec
secours OHLC daily, univers et secteurs actuels, archives révisables et
plusieurs expériences déjà examinées sur ces mêmes années. Il ne s’agit
pas d’une nouvelle confirmation prospective indépendante.

## Vérifications et suivi

Cinq tests passent : invariance du rang à une transformation monotone de
probabilité, départage déterministe, population commune sans imputation,
absence de seuil absolu caché, indépendance entre dates et rejet d’un modèle
futur ou d’une probabilité invalide. Les décisions sont figées et scellées
avant le replay, sans consulter les labels économiques.

Racine active : `artifacts/research/us_q051_rank_fusion/20261109-v1/`.

- `request.json` : protocole et empreintes des sources.
- `inputs/ranking.parquet` : deux probabilités, percentiles et fusion.
- `inputs/coverage-daily.csv` : effectifs observables et sélections par date.
- `inputs/signals-FUSION50.parquet` / `signals-RELATIVE_SYMBOL.parquet` : listes figées.
- `progress.json` et `cases/<profil>/progress.json` : suivi des quatre replays.
- Après réussite : `comparison.csv`, `annual-comparison.csv`, `report.json`,
  graphique capital PNG/SVG, imports dans l’historique IHM.

Script : `scripts/research/us_q051_rank_fusion_20261109.py`. Deux replays
simultanés, les deux fusions d’abord puis les témoins appariés. Aucun SQL,
appel LLM/fournisseur ou ordre broker. Aucune modification de la liste de
profils du produit n’est effectuée par cette expérience.

## Résultats terminaux et conclusion

Période identique **2021–2025**, départ **4 000 USD**, frais et financement
inclus. Le DD est mesuré sur les valorisations intraday du replay.

| Profil / sélection | Capital final USD | Rendement | DD max | Trades clôturés | Gagnants | Capital brut moyen USD |
|---|---:|---:|---:|---:|---:|---:|
| Q051 per-symbol avec seuils, référence | 8 788,86 | +119,72 % | −36,89 % | 1 046 | 34,51 % | 4 800,14 |
| Q051 per-symbol relatif, sans seuils, population commune | 8 865,81 | +121,65 % | −32,74 % | 1 203 | 36,66 % | 5 510,38 |
| Q051 fusion 50/50, même population commune | 4 115,07 | +2,88 % | −53,38 % | 1 191 | 33,59 % | 2 789,78 |
| Vol20/régime per-symbol avec seuils, référence | 6 401,27 | +60,03 % | −24,29 % | 784 | 35,59 % | 2 189,74 |
| Vol20/régime per-symbol relatif, sans seuils, population commune | 6 036,57 | +50,91 % | −22,00 % | 880 | 36,36 % | 2 294,71 |
| Vol20/régime fusion 50/50, même population commune | 3 579,85 | −10,50 % | −41,69 % | 825 | 34,42 % | 1 558,61 |

La comparaison appariée isole l’effet du score sectoriel : pour Q051,
la fusion perd **118,77 points** de rendement et aggrave le DD de **20,65
points** face au per-symbol relatif. Avec protection vol/régime, elle perd
**61,42 points** et aggrave le DD de **19,69 points**. Le taux gagnant baisse
respectivement de 3,07 et 1,94 points. Ajouter ce classement sectoriel à poids
50/50 ne fournit donc aucun avantage dans ce protocole. Cela ne prouve pas
que toute utilisation future d’informations sectorielles soit inutile.

Le témoin per-symbol relatif présente un compromis intéressant sans protection,
mais il modifie aussi la population et les seuils par rapport à la référence
historique. Ce résultat exploratoire ne justifie pas de modifier la production.
Avec vol/régime, il échange une partie du rendement contre un DD moins profond.

| Année | Q051 relatif | Q051 fusion | Vol20/régime relatif | Vol20/régime fusion |
|---|---:|---:|---:|---:|
| 2021 | +19,97 % | −19,58 % | +6,16 % | −7,29 % |
| 2022 | −11,96 % | −23,11 % | −9,08 % | −19,69 % |
| 2023 | +61,06 % | +7,92 % | +23,40 % | +13,90 % |
| 2024 | +8,67 % | +17,86 % | +19,55 % | +12,61 % |
| 2025 | +19,91 % | +30,79 % | +5,99 % | −6,30 % |

Validation terminale `validation.json` : PASS, empreintes des entrées figées,
compteurs gagnants/perdants recomptés depuis les trades, vingt bilans annuels,
capital final rapproché des courbes, configurations de portefeuille identiques
et 6 275 signaux par sélection. Quatre imports IHM réussis :

- `20261109_q051_fusion50_fusion_v1`
- `20261109_vol20_fusion50_fusion_v1`
- `20261109_q051_relative_symbol_fusion_v1`
- `20261109_vol20_relative_symbol_fusion_v1`

Le statut de campagne est `COMPLETED_EXPLORATORY`, sans échec de calcul ;
les quatre rapports natifs conservent **INCOMPLETE_COVERAGE** (secours OHLC
journalier lorsque les 5m sont incomplets ou incompatibles). Les limites
historiques décrites plus haut restent applicables. Ne pas comparer ces
rendements 2021–2025 au +206,51 % qui incluait une partie de 2026.

Courbes : `artifacts/research/us_q051_rank_fusion/20261109-v1/charts/capital-comparison.png`.

## Extension demandée jusqu’au 1er octobre 2026

GO utilisateur après remise des résultats 2021–2025 : prolonger les quatre
variantes jusqu’au **01/10/2026**, date du témoin Q051 vol20/régime à +125,98 %,
pour une comparaison de durée identique. Nouvelle campagne indépendante des
archives v1, mêmes règles, mêmes Oracles annuels, aucun reset du capital ni
des positions en 2026. Les quatre replays continus repartent de 2021.

Le parent Oracle 2026 est `model-factory-20261107222627-db80b0` (entraînement
2019–2025). Ses scores Oracle/per-symbol déjà archivés sont conservés. Les
modèles sectoriels manquants sont préparés uniquement à partir des chunks
d’entraînement figés de ce parent, labels purgés avant la disponibilité des
millésimes 2025/2026. La carte sectorielle précédente est conservée. Aucun
réentraînement des années 2021–2025 ni de l’Oracle/per-symbol 2026.

Les entrées d’inférence 2026 sont figées en SQL lecture seule, sans appel
fournisseur. Avant sélection, les probabilités per-symbol produites sur ces
entrées doivent reproduire les probabilités archivées à 1e-8 près ; sinon
arrêt et diagnostic, pas de substitution silencieuse. La couverture et les
limites de données historiques sont conservées.

Suivi des prérequis : `artifacts/research/us_q051_per_sector/20261109-v5-2026/`.
Suivi des quatre replays : `artifacts/research/us_q051_rank_fusion/20261109-v2-2026/`.
Scripts : `scripts/research/us_q051_sector_2026_extension_20261109.py` et
`scripts/research/us_q051_rank_fusion_2026_20261109.py`. Deux workers, cinq
tests de classement/causalité passent. Les anciens résultats sont préservés.
Les comparaisons terminales incluront les deux témoins per-symbol historiques
sur **2021–01/10/2026**, sans mélanger leurs résultats avec ceux arrêtés en 2025.

Préparation terminée : **22 modèles sectoriels**, **31 209 probabilités
per-symbol reproduites à l’identique (écart maximal 0)**. Les sélections
2021–2025 sont strictement identiques aux fichiers v1. En 2026, 158 candidats
au minimum disposent des deux scores dans le TOP179 (moyenne 166,01), donc
cinq candidats effectivement sélectionnés à chacune des 188 nouvelles séances.
Total continu : **1 443 séances et 7 215 signaux par variante**.

Statut terminal : **QUATRE REPLAYS TERMINÉS ET IMPORTÉS**, aucun échec de calcul.
Validation PASS : les courbes 2021–2025 sont reproduites exactement (écart
maximal 0 pour les quatre variantes), les compteurs annuels et globaux sont
rapprochés des trades, et le capital final est rapproché de chaque courbe.

### Comparaison continue 01/01/2021–01/10/2026

| Sélection | Capital final USD | Rendement | DD max intraday | Gagnants | Trades clôturés | Capital brut moyen USD |
|---|---:|---:|---:|---:|---:|---:|
| Q051 per-symbol avec seuils, témoin | 12 260,32 | +206,51 % | −36,89 % | 35,01 % | 1 234 | 5 461,32 |
| Q051 per-symbol relatif, sans seuils | 12 106,72 | +202,67 % | −32,74 % | 36,71 % | 1 400 | 6 116,63 |
| Q051 fusion 50/50 | 4 210,50 | +5,26 % | −53,38 % | 33,02 % | 1 375 | 2 923,94 |
| Vol20/régime per-symbol avec seuils, témoin | 9 039,00 | +125,98 % | −24,29 % | 36,17 % | 940 | 2 396,13 |
| Vol20/régime per-symbol relatif, sans seuils | 8 159,86 | +104,00 % | −22,00 % | 36,49 % | 1 036 | 2 463,46 |
| Vol20/régime fusion 50/50 | 3 528,64 | −11,78 % | −41,69 % | 33,44 % | 969 | 1 560,85 |

La comparaison appariée sur la population commune reste défavorable à la fusion :
Q051 perd 197,41 points de rendement, DD aggravé de 20,65 points et taux gagnant
inférieur de 3,70 points ; avec vol/régime, perte de 115,78 points de rendement,
DD aggravé de 19,69 points et taux gagnant inférieur de 3,05 points. **Fusion
50/50 non retenue**, pas de modification de production ni de recherche de poids.

Le per-symbol relatif sans seuils présente un autre compromis : face au témoin
Q051, rendement inférieur de 3,84 points, DD moins profond de 4,16 points,
taux gagnant supérieur de 1,71 point. Avec vol/régime, il cède 21,98 points de
rendement pour 2,30 points de DD en moins. Cette comparaison change à la fois
la population et les seuils ; elle ne prouve pas que retirer les seuils seuls
soit la cause du changement. Les mêmes années ont déjà été explorées plusieurs
fois ; aucune confirmation prospective indépendante.

Les quatre rapports natifs conservent **INCOMPLETE_COVERAGE** (recours OHLC
journalier lorsque les 5m sont incomplets/incompatibles). La réussite du calcul
ne signifie donc pas couverture intraday complète. Frais et financement inclus,
aucun SQL en écriture ni ordre. Imports IHM :

- `20261109_q051_fusion50_fusion_2026_v2`
- `20261109_vol20_fusion50_fusion_2026_v2`
- `20261109_q051_relative_symbol_fusion_2026_v2`
- `20261109_vol20_relative_symbol_fusion_2026_v2`

Résultats : `artifacts/research/us_q051_rank_fusion/20261109-v2-2026/comparison.csv`,
`annual-comparison.csv`, `validation.json`, `report.json` et
`charts/capital-comparison.png` (également SVG/CSV).

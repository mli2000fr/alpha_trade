# Complémentarité des anciens signaux sur le TOP10 Oracle parcours

## Demande et protocole figé le 18 octobre 2026

Réévaluer les faibles avantages anciens dans les dix candidats de l'Oracle
parcours H20 actuel, puis examiner s'ils corrigent mutuellement leurs erreurs.
Un résultat négatif sur un univers plus large ne prouve pas un résultat négatif
dans ces dix ; inversement un sous-ensemble plus extrême n'est pas nécessairement
plus facile à orienter.

Audit local, sans entraînement, fournisseur/LLM, SQL, ordre, PnL ni changement
de modèle/batch servi. Configuration :
`config/research/us_top10_legacy_complementarity_20261018.json` ; lecteur :
`scripts/research/us_top10_legacy_complementarity.py`.

Statut : calcul terminé, bilan ci-dessous.
Dossier de référence :
`artifacts/research/us_top10_legacy_complementarity/20261018-v2`.
Le premier dossier v1 est conservé : les sélections sont identiques ; v2
corrige le décompte Holm pour conserver les douze comparaisons déclarées,
même lorsque quatre sont non testables (p imputée à 1 uniquement pour la
correction, résultat de ces tests laissé inconnu). Aucun poids/seuil ajusté.

## Population et cible

Les dix scores Oracle originaux, sans reclassement par résultat futur.
Évaluation 2022–2026 sur le même panel causal archivé que les diagnostics TOP10
précédents ; 2023 partiel, fin des décisions le 2 septembre 2026. D1/D10 sont
les **déciles globaux du rendement terminal H20**, pas la direction de l'excursion
maximale, ni des trades gagnants/perdants TP/SL.

Les sélections sont figées à J : trois parmi dix. La comparaison principale
des résultats ne conserve ensuite que les dates où les dix labels sont connus ;
aucun inconnu n'est remplacé par un perdant ni par le candidat suivant.
Toute recette exige les dix scores disponibles, sans score neutre inventé.

## Inventaire et périmètres séparés

- Scores récents TOP10 : ancienne logistique D10 J/parcours, CatBoost trois
  classes et logistique trois classes, anti-D1 CatBoost. Même famille prix :
  leur nombre ne signifie pas autant d'informations indépendantes.
- Momentum 120, volatilité 60/ATR20 et moyenne momentum/amplitude : mêmes
  formules anciennes, mais rangs calculés dans les dix actuels. Ce n'est pas
  le rejeu exact de l'ancien croisement Oracle terminal × ATR TOP20 %.
- Deux facteurs prix E17 archivés : momentum résiduel et retournement cinq
  séances. Cibles initiales H60/H120, nouvelle lecture H20, prix ajustés et
  métadonnées historiques réservés ; pas d'archive 2026.
- Douze prévisions E23 J/prix/sentiment/mixte × trois algorithmes : **descriptif
  uniquement**. Le producteur a filtré la population sur les labels futurs
  avant sauvegarde ; sa présence/absence ne peut devenir une règle d'entrée.
  Pas de combinaison décisionnelle utilisant ces scores.
- Ancien catalogue de consensus de modèles : chemins vérifiés individuellement,
  sans recréer les modèles ou scores supprimés.
- Options prospectives : archive à partir du 13 septembre 2026, après ce panel.
  Barres options historiques : février–mars 2024 seulement et qualification
  indicative/PIT distincte. Couverture mesurée, pas de résultat global inventé.
- News/GPT rétrospectifs, surprise EPS non PIT, informations d'ouverture J+1,
  autres producteurs insuffisamment tracés : exclus des recettes principales.
  Sources bloquées par droits/prudence non restaurées et non réutilisées.

Les empreintes de toutes les entrées utilisées sont figées avant calcul puis
revérifiées. Le code actuel d'un producteur ancien ne certifie pas à lui seul
la version qui avait produit son archive.

## Six recettes, pas de recherche de poids

Moyennes équipondérées des rangs : ancien D10 parcours + anti-D1 CatBoost
(recette principale), + momentum120, + momentum/volatilité, + retournement5,
+ momentum résiduel120. Sixième recette : accord des cinq premiers de D10
et anti-D1, au maximum trois, départage par D10. Aucun retournement de signe
après résultat. Références Oracle et D10 choisissent **le même nombre par date**
que la recette, y compris zéro ; moins d'entrées ne signifie pas automatiquement
meilleure sélection.

Mesures : proportion D10 et D1, AUC D10/reste quotidienne, couverture annuelle,
recouvrement des sélections, corrélations des rangs, D1 retirés/D10 perdus et
D10 ajoutés/D1 introduits. L'IC du résidu est descriptif, pas une probabilité
ni un modèle appris ; projection entre scores de J seulement.

Gates de recherche : couverture annuelle ≥90 %, ≥30 dates évaluables,
gain D10 ≥3 points et baisse D1 ≥1 point contre l'ancien filtre D10 ; validation
2022 puis au moins trois des quatre périodes suivantes. Tests appariés en blocs
de 63 séances (≥20 dates/bloc, ≥8 blocs), 999 permutations, correction Holm sur
les douze tests des six recettes × deux critères. Ce gate ne qualifie ni le
PIT strict, ni une rentabilité, ni une promotion en production. Une couverture
incomplète signifie **inconclusif sur toute la période**, pas inefficacité prouvée.

Les années ont déjà servi à de nombreuses expériences : même un résultat
positif ne serait pas un nouveau holdout indépendant.

## Bilan calculé

**Terminé / `NO_STABLE_TOP10_COMPLEMENTARITY`, aucune promotion.**
10 490 couples, 1 049 dates ; les comparaisons principales retiennent les
1 027 dates aux dix labels connus, soit 3 081 sélections pour une shortlist
constante de trois. Deux dates incomplètes en 2022 et vingt en 2026 restent
archivées mais hors de cette comparaison. Dix scores/règles examinés,
plus douze anciens scores E23 descriptifs seulement ; six recettes figées.

### Un petit gain moyen, pas une confirmation stable

Proportions parmi les **trois retenus sur les dix**, moyenne des dates complètes
pondérée par leur nombre (pas moyenne donnant le même poids à chaque année) :

| Sélection | D10 | D1 |
|---|---:|---:|
| Trois premiers Oracle, ordre initial | 29,11 % | 25,61 % |
| Filtre logistique D10 parcours seul, référence de recherche | 30,57 % | 23,79 % |
| Moyenne D10 parcours + anti-D1 CatBoost, recette principale | **31,61 %** | **22,07 %** |
| Moyenne D10 + momentum120 | 29,96 % | 24,54 % |
| Moyenne D10 + momentum/volatilité/ATR | 30,93 % | 24,25 % |

La recette principale ajoute **1,04 point de D10** et retire **1,72 point de D1**
contre le filtre D10 seul. Contre l'ordre Oracle brut : +2,50 et −3,54 points.
Ces proportions ne sont **ni un taux de trades gagnants ni un rendement**.
Le filtre D10 de référence était déjà exploratoire/non promu : le dépasser
légèrement n'est pas une autorisation d'utilisation.

| Période | D10 référence → combinaison | D1 référence → combinaison |
|---|---:|---:|
| 2022 | 24,36 → 27,04 % | 35,61 → 33,73 % |
| 2023 partiel | 42,71 → 43,49 % | 20,05 → 17,71 % |
| 2024 | **24,21 → 23,54 %** | **19,18 → 20,77 %** |
| 2025 | 37,87 → 38,53 % | 14,93 → 12,93 % |
| 2026 partiel | 29,05 → 31,08 % | 29,95 → 23,87 % |

2026 s'améliore surtout par la baisse de D1 ; **2024 se dégrade sur les deux
critères**. Le gain D10 reste inférieur aux trois points exigés dans chaque
période. Aucune recette ne passe la validation et la confirmation fixées.

Sur les seules confirmations 2023–2026 : gain D10 de la recette principale
**+0,51 point**, baisse D1 **1,67 point** ; treize blocs exploitables.
Tests deux côtés, Holm sur toute la famille déclarée : p=**1,000** et **0,936**.
Pas d'avantage statistiquement démontré. Quatre recettes ont une couverture
complète mais aucun gain stable ; deux avec E17 sont **inconclusives sur toute
la période**, avec seulement 85 dates complètes et aucune en 2023/2026.

L'accord top5/top5 retient 2 802 titres, environ 2,73 par date, au lieu de 3 081 :
D10 quotidien moyen **31,84 %** contre **30,30 %** pour D10 seul à effectif
identique ; D1 **22,14 %** contre **23,84 %**. Aucun test corrigé significatif.
Il ne faut pas comparer naïvement ces résultats à une référence choisissant
toujours trois titres ; les moyennes sont par date, pas par article/trade.

### Pourquoi les faibles avantages ne s'additionnent pas simplement

- Ancien D10 parcours et logistique trois classes : corrélation des rangs
  **0,831**, environ **79,5 %** de recouvrement des trois choisis. Grande
  partie de l'information répétée.
- D10 et anti-D1 CatBoost : corrélation **0,315**, recouvrement **46,5 %**.
  Le remplacement complet retire **397 D1** mais en introduit **400** ;
  il ajoute **474 D10** mais en perd **469**. Être différent ne suffit pas
  à corriger les erreurs de l'autre. Leur moyenne est un peu meilleure,
  sans la stabilité annuelle nécessaire.
- Momentum120 et D10 sont peu corrélés (**−0,106**), mais le remplacement
  retire 526 D1 et en introduit 615 : désaccord ne signifie pas avantage.
  Momentum/ATR vise notamment l'amplitude, pas nécessairement son sens.

Ce sont des décomptes de sélections date/titre, avec répétitions et horizons
chevauchants, pas autant de trades indépendants. L'IC résiduel des scores
reste faible ; aucune régression sur les rendements n'est devenue une recette.

### Ce que l'on ne peut pas conclure

Les douze archives E23 couvrent chacune **5 258 / 10 490 lignes** (50,12 %),
mais seulement **42 / 1 049 dates** avec les dix scores (4,00 %). Elles sont
filtrées à l'origine sur les labels futurs et leur disponibilité PIT/lineage
n'est pas suffisamment prouvée. Leurs corrélations parfois meilleures sur ce
petit échantillon sont **rétrospectives et non actionnables**. Pas de recette
E23, pas d'abstention déduite de leur absence, pas de neutralisation des trous.

Les **18 chemins OOF** de l'ancien catalogue ne sont plus présents : il
serait faux de dire que tous ces anciens modèles ont été retestés sur TOP10.
Leur absence ne prouve pas leur inefficacité. E17 manque de couverture ;
options prospectives ne recouvrent aucune date, barres options historiques
seulement une courte période. Les familles exclues et motifs précis sont dans
`inventory.json`. Le contexte macro commun à une date nécessiterait un test
temporel distinct ; cet audit de classement ne mesure pas un veto global.

**Conclusion pratique :** oui, il était pertinent de reprendre les anciens
avantages sur les dix actuels ; non, les archives admissibles ne démontrent
pas ici une combinaison directionnelle suffisamment stable. Pas de modèle
supplémentaire, de poids appris ni de backtest économique lancé après ce
résultat. Les vraies informations nouvelles prospectives restent une piste
distincte, pas une performance supposée.

## Vérifications réalisées

87 tests ciblés passent (nouveau lecteur, anciens lecteurs TOP10/CatBoost et
diagnostic hiérarchique). Contrôles réels supplémentaires : empreintes entrées
et sorties, identité/rangs 1–10 de chaque date, pas de doublon date/titre,
scores complets dix ou absents dix après qualification, maximum trois retenus,
absence de faux zéro sur sélection vide ; sources intactes en fin de calcul.
Tous les panels/statistiques numériques v1/v2 sont identiques ; seule la
correction de multiplicité est renforcée dans le rapport v2.

## Reproduction

```powershell
python -u -m scripts.research.us_top10_legacy_complementarity --output artifacts/research/us_top10_legacy_complementarity/20261018-v2
```

Les dossiers terminés sont immuables. Rapports : `inventory.json`,
`yearly-statistics.csv`, `pair-summary.csv`, panel et statistiques quotidiennes
en Parquet, protocole et `report.json`.

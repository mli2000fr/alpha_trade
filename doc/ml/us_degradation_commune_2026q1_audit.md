# US — Audit de la dégradation du bundle ancien, janvier–mars 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Statut au 5 octobre 2026

Le diagnostic directionnel et la comparaison de six contextes figés sont calculés.
L'attribution des pertes du portefeuille reste non terminée : journaux absents.
Aucun entraînement, écriture SQL ou changement de production n'a été effectué.

Batch examiné : `model-factory-20260903174624-014164`, entraînement terminé
au 30 juin 2024. Les anciens dossiers des backtests
`20260904_161042_e4696eb8` et `20260904_191330_695b4e33` n'ont pas été retrouvés.
Un nouvel entraînement sur un nouvel univers ne reproduirait pas cette expérience.

## Données récupérées et méthode

Les groupes de prédictions comprennent un groupe `oracle_synth` et 55 groupes
`directional_bundle`. Le premier ne constitue pas une preuve directionnelle : il
ne faut pas attribuer ses probabilités synthétiques aux modèles LONG/SHORT.
L'audit conserve uniquement les véritables lignes directionnelles pour ce filtre.

Les labels réalisés ont été reconstruits par le calcul natif
`modelFactory.oracle.build_labels.build_labels(dry_run=True)`, uniquement en
fichiers locaux, du 1er juillet 2024 au 30 juin 2026, sur les 400 symboles du
registre ancien. Sur 200 341 labels, 200 337 sont disponibles ; quatre sont
invalides pour absence de barre de sortie. Aucun de ces quatre n'appartient aux
candidats évalués du tableau ci-dessous.

Le TOP20 est calculé chaque jour sur les scores Oracle de cet ancien batch,
avant la jointure des modèles directionnels. Pas de substitution par le batch
Oracle actuel, pas de filtre ATR ajouté. Trois populations sont distinguées :
TOP20 complet, TOP20 disposant d'une prédiction directionnelle, puis filtre LONG.

Filtre diagnostic figé issu du code actuel : P(LONG) > 0,55,
P(LONG) > P(SHORT), P(LONG) > P(FLAT), P(LONG)−P(SHORT) ≥ 0,02.
L'absence des anciennes configurations empêche de certifier que cette règle
reproduit bit pour bit la politique réellement exécutée en septembre.

## Résultats H20 avant portefeuille

| Mois du signal | Oracle : rendement moyen | LONG filtrés | D1 des LONG | D10 des LONG | Rendement moyen LONG | Rendement médian LONG |
|---|---:|---:|---:|---:|---:|---:|
| Janvier 2026 | −5,87 % | 80 | 27,50 % | 6,25 % | −7,56 % | −8,04 % |
| Février 2026 | −1,65 % | 75 | 5,33 % | 32,00 % | +4,52 % | +0,38 % |
| Mars 2026 | +3,59 % | 142 | 16,90 % | 16,90 % | +3,56 % | +2,97 % |

Les rendements sont clôture ajustée J → J+20 séances. Ce ne sont ni des
rendements nets de coûts, ni une simulation des entrées à l'ouverture suivante,
des stops, du TP et des contraintes de capital. Une ligne est un événement
symbole/date : les observations successives se chevauchent et ne sont pas
des trades indépendants.

Janvier est nettement mauvais et le filtre LONG aggrave la moyenne du pool.
Février ne confirme pas une dégradation uniforme du filtre : sa moyenne est
positive mais sa médiane est faible. Mars est positif sur cette mesure.
Mai est également défavorable au filtre (−4,10 %, D1 37,29 %, D10 7,63 %).
Des épisodes défavorables existaient déjà en février, mars et octobre 2025.
Il serait donc incorrect de chercher seulement une anomalie des trois premiers
mois 2026 ou un effet spécifique au mois de février.

## Limites et prochaine étape

1. Comparer les contextes disponibles avant décision sur ces populations
   précisément identifiées ; garder les règles figées et compter les bonnes
   périodes qui auraient été écartées.
2. Ne pas confondre régime du pool actuel Oracle × ATR et ancien bundle :
   leurs univers, modèles et sélections diffèrent.
3. Conserver les réserves de disponibilité/vintage macro et sentiment de
   l'[audit PIT](us_d10_d1_ratio_audit_pit_lineage.md).
4. Pour attribuer le résultat net aux trades, récupérer les rapports et
   journaux des deux backtests anciens. À défaut, seul un rejeu séparé,
   explicitement non identique, serait possible.

Pas de veto macro validé, pas de bénéfice économique démontré et pas de GO
production résultant de ce diagnostic.

## Suite terminée : contexte préalable et concentration

### Protocole figé

Les données de contexte d'une séance sont appliquées uniquement à la séance SPY
suivante. Aucune propagation n'est faite lorsqu'une observation est absente.
Les contrôles vérifient que la date observée est antérieure à la date du signal.
Ce décalage ne certifie toutefois pas la publication PIT des macros reconstruites.

Six partitions descriptives sont examinées, sans recherche du meilleur seuil :

- régime `normal` et nouvelles entrées autorisées ;
- VIX/VIX3M ≤ 1 ;
- rendement SPY 20 séances ≥ 0 ;
- rendement du titre supérieur à celui des pairs sectoriels sur 20 séances ;
- plus de 50 % des pairs au-dessus de leur SMA20 ;
- conjonction des deux critères sectoriels précédents.

Le contexte sectoriel réutilise le panel de recherche précédent, avec au moins
20 autres titres et retrait du titre étudié du calcul des pairs. Les catégories
sectorielles sont les métadonnées actuelles, non qualifiées PIT. Le panel de pairs
est l'univers de l'expérience précédente, pas uniquement les 400 titres du bundle.
Une absence de contexte reste `unknown`, séparée des candidats écartés.
Les rendements relatifs et la breadth ne sont pas des scores de sentiment.

Le bêta est cette fois estimé explicitement : covariance des rendements journaliers
titre/SPY sur 252 séances, divisée par la variance SPY, puis décalée d'une séance.
Ce n'est pas le bêta parfois constant des anciens exports de features.

### Janvier ne correspond pas à un régime global défavorable identifié

Les 20 séances avec candidats LONG sont en régime précédent `normal`.
VIX précédent moyen : 15,92 ; VIX/VIX3M moyen : 0,842 ; rendement SPY précédent
sur 20 séances moyen : +0,90 %. Régime et courbe VIX n'écartent aucune des
80 observations de janvier. Exiger SPY20 ≥ 0 en garde 76, encore à −7,50 %
de rendement H20 moyen contre −7,56 % avant ce critère.

La faiblesse relative sectorielle est plus visible, mais ne constitue pas une
validation : parmi 73 observations ayant ce contexte, seules neuf ont une force
relative positive, avec une moyenne H20 de +4,36 %. Les 64 autres sont à −9,75 %.
Sept observations restent inconnues. Cette restriction enlève aussi 68,18 % des
observations positives de la population connue. Ne pas appeler ces neuf lignes
neuf trades indépendants, ni promouvoir ce résultat isolé comme règle robuste.

### Comparaison historique : aucune protection stable démontrée

Le tableau utilise la moyenne des rendements moyens de chaque journée de signal,
pas la moyenne de toutes les lignes. Pour le critère sectoriel, la référence
est limitée aux lignes où le contexte est connu ; les valeurs ne sont donc pas
directement comparables à la référence macro complète.

| Période | LONG, contexte sectoriel connu | Après force relative positive | Après force relative ET breadth >50 % |
|---|---:|---:|---:|
| 2024H2 | −3,44 % | −8,73 % | −11,03 % |
| 2025H1 | +2,51 % | +2,03 % | +1,48 % |
| 2025H2 | +0,74 % | +0,58 % | +2,22 % |
| 2026Q1 | −1,65 % | +0,005 % | −3,36 % |

En 2026Q1, la conjonction ne garde que huit lignes sur 265 connues et écarte
96,75 % des observations positives. Le critère relatif seul en enlève 69,11 %.
Ces résultats ne montrent pas une règle durable pour éviter les pertes.

Sur la population macro complète de 2026Q1, la moyenne quotidienne de référence
est −0,44 %. Elle devient −0,57 % avec régime normal/entrées autorisées,
−1,25 % avec courbe VIX non inversée, et −5,10 % avec SPY20 ≥ 0. Le dernier
critère écarte 74,32 % des observations positives. Il coupe notamment des
opportunités de rebond : un marché auparavant faible ne rend pas tous les LONG
futurs perdants. Aucune causalité ni significativité statistique n'est revendiquée.

### Concentration : facteur explicatif particulièrement important

En janvier, neuf titres produisent les 80 observations et les cinq plus présents
en représentent 82,50 %. TTD apparaît 20 fois avec −27,27 % de rendement H20 moyen.
Sa contribution à la moyenne de toutes les lignes est −6,82 points sur −7,56 %.
ARLO contribue à −1,51 point. Ces contributions sont additives sur la moyenne
des événements, pas des pertes comptables ou une exposition réelle du portefeuille.

Cette concentration explique davantage janvier que le seul régime global.
Elle ne justifie pas une blacklist TTD déterminée après observation. Il faudrait
un audit de concentration du portefeuille exécuté et des règles de risque figées
avant d'affirmer que limiter la répétition des titres aurait amélioré le résultat.

En février, VIX moyen 19,11 et 19 séances normales ; en mars, VIX moyen 25,35,
21 séances normales et une en préservation. Les moyennes H20 LONG restent
positives en février et mars : l'histoire « macro adverse = trois mois perdants »
n'est pas confirmée sur ces candidats. La moyenne bêta passe de 1,22 en janvier
à 1,38 puis 1,49 ; ce descriptif ne suffit pas à établir un veto.

### Conclusion et limites restantes

Audit de contexte **terminé en descriptif, aucune règle validée à promouvoir**.
Ne pas ajuster maintenant les seuils sur janvier. Les anciennes prédictions
directionnelles ne commencent qu'en juillet 2024 : impossible de présenter
une confirmation 2020–2025 de cette même politique avec ces seules données.
Les analyses 2020–2025 du pool Oracle × ATR actuel sont des populations distinctes.

L'explication du résultat net exige toujours les anciens journaux de portefeuille.
Sans eux, un éventuel rejeu avec le moteur actuel serait une expérience séparée,
et non une reproduction certifiée de l'ancien backtest.

## Reproductibilité

Script : `scripts/research/us_original_directional_monthly_audit.py`.
Résultats : `artifacts/research/us_common_degradation/original-monthly-20261005-v1/`.
`protocol.json` décrit les règles ; `labels_quality.json` conserve la couverture ;
`joined_diagnostic.parquet` conserve toutes les jointures ; `monthly.csv` et
`report.json` donnent les chiffres mensuels juillet 2024–juin 2026.

Suite contexte : `scripts/research/us_original_context_audit.py` et
`artifacts/research/us_common_degradation/original-context-20261005-v1/`.
Le rapport contient trois populations distinctes (Oracle, modèles disponibles,
LONG filtrés), les six partitions par mois/semestre, la concentration par titre,
les effectifs connus/inconnus et la part des observations positives écartées.
Le fichier `context_candidates.parquet` conserve les dates sources et jointures.

Suite terminée : [répétition des signaux et fiabilité opérationnelle LONG](us_bundle_repetition_fiabilite_long_audit.md).
Retirer les répétitions ne résout pas janvier ; le classement par forte probabilité
n'est pas stable. Certains scores presque constants motivent une vérification
distincte de serving, sans conclure encore à un bug.

# Sprint 13-B5 — Matérialité des censures et droits économiques vérifiés

## Décision et périmètre

B5 ne cherche ni un meilleur seuil ni un nouveau modèle. La campagne
B2 de [480 cellules](../../artifacts/cn/economic/sprint13b/sprint13b-273492bdfbcf1230/report.json)
comptait **398 résultats valides et 82 censurés**. Chaque cellule est
un semestre × une politique × une seed × un scénario de fill × un profil
de coûts. Une comparaison appariée exige que l'Oracle et les deux veto
soient valides dans le même quadruplet : **130/160** l'étaient au départ.

Les preuves B3 et B4 ont réconcilié quatre opérations supplémentaires,
sans supprimer les autres événements de la base. B5 traite trois
ruptures de facteur encore détenues par certains portefeuilles. Les
replays ciblés établissent leur validité technique ; l'[audit de
matérialité](../../modelFactory/cn_economic_materiality_13b5.py)
projette les cellules récupérées **sans agréger leurs PnL**. Une
projection à partir de preuves B2/B3/B4/B5 différentes n'est pas un
replay homogène des 480 cellules.

## Trois événements traités, jamais une règle générique

| Action | Fait économique vérifié | Conflit fournisseur conservé | Traitement B5 |
| --- | --- | --- | --- |
| `16255`, `sz.002443`, 30/05/2022 | 0,40 CNY/action avant impôt, aucune action nouvelle. Le [rapport annuel rédigé par l'émetteur](https://stockn.xueqiu.com/SZ002443/20230421366633.pdf) confirme les droits, et BaoStock donne le registre au 27/05 et le paiement au 30/05. | Facteur relatif 3,851 contre 1,047 théorique ; close brut 8,94 → open 8,55, pas une division du titre par 3,85. | Appliquer seulement le cash confirmé aux positions détenues, conserver l'erreur du facteur dans l'artefact. |
| `23221`, `sz.300862`, 12/12/2025 | L'[avis officiel de distribution](https://disc.static.szse.cn/disc/disk03/finalpage/2025-12-04/94c9f73c-4b86-4d29-9244-cfe07216b821.PDF) confirme 0,005 CNY/action, sans actions nouvelles ; registre le 11/12. | Facteur relatif 0,702 contre environ 1,0002 ; close brut 24,56 → open 23,52. | Appliquer seulement le cash confirmé ; ne pas interpréter la remise à 1 du facteur comme un reverse split. |
| `316`, `sz.302132`, 18/02/2025 | L'[avis officiel](https://static.cninfo.com.cn/finalpage/2025-02-15/1222544408.PDF) fixe au 17/02 le changement `300114 → 302132` et précise que les titres détenus gardent le même nombre et la même catégorie. Aucune distribution BaoStock à la date du 18/02. | Facteur 1 → 5,975678 le 18/02, alors que close brut 68,01 → open 68,00. | Reconnaître **uniquement** cet ID comme non-distribution : aucun cash/action fictif, aucune censure de la barre brute. |

Le [constructeur de preuve B5](../../modelFactory/cn_economic_remediation_13b5.py)
vérifie pour chaque ID l'instrument, le symbole, la date, les termes de
source, son hash, les valeurs de facteur gelées et la continuité
observable des cours bruts. L'adaptateur de replay ne reconnaît
`EVIDENCED_NON_DISTRIBUTION` que pour l'ID 316, l'ancien et le nouveau
code et la date officielle. Toutes les autres ruptures inconnues
restent bloquantes. La preuve est ex-post pour le PnL ; une publication
postérieure au signal ne devient jamais une feature PIT.

L'artefact est [evidence B5](../../artifacts/cn/corporate_actions/sprint13b5/evidence-d8a633c6830b0ded/evidence.json),
hash `d8a633c6830b0dedcbcd486bf39b556d781a8db08cb95a16a828149f059ed285`.
La base `alpha_trade_cn`, les signaux, les coûts et les règles de
fill n'ont pas été modifiés.

### Replays ciblés terminés

Les trois sous-ensembles ont chacun 12/12 cellules
`RESEARCH_MARK_VALID` : trois politiques × deux scénarios de fill ×
deux profils de coûts. Voici uniquement le scénario `base` au coût
`cn_a_research` ; il ne faut pas extrapoler ces trois seeds au reste
de l'univers.

| Sous-ensemble | Oracle seul | Veto retournement | Veto LightGBM | Rapport |
| --- | ---: | ---: | ---: | --- |
| 2022H1, seed 3 | −25,61 % | −21,79 % | −20,41 % | [12 cellules](../../artifacts/cn/economic/sprint13b/sprint13b-83c95f4711ab3a5d/report.json) |
| 2025H1, seed 3 | +0,92 % | −3,52 % | +1,05 % | [12 cellules](../../artifacts/cn/economic/sprint13b/sprint13b-e5275d7696af705b/report.json) |
| 2025H2, seed 4 | +2,03 % | +6,44 % | −0,85 % | [12 cellules](../../artifacts/cn/economic/sprint13b/sprint13b-2bd16d5d1f1914a5/report.json) |

L'ordre des politiques change d'un semestre à l'autre. La validité
technique de 36 cellules ne valide donc pas le veto directionnel.

### Matérialité des blocages

Le [rapport de projection](../../artifacts/cn/economic/sprint13b5/materiality-72ac89dba00b3b73/report.json)
vérifie les hashes de preuve et les hashes des prédictions de chaque
cellule ciblée. Il retrouve **8 cellules récupérées par B3, 24 par B4
et 32 par B5**, soit 64. Le nombre projeté de cellules valides passe
de **398 à 462 sur 480** ; les triplets Oracle + deux veto valides et
appariés passent de **130 à 154 sur 160**. Les 18 autres cellules
sont exactement les 12 de la position radiée de 2023H2/seed 2 et les
6 de la fraction d'action de 2024H1/seed 0 sous coût stress.

Ce calcul n'agrège **aucun rendement** entre versions de preuve. La
campagne homogène B5 s'est terminée le 27/09/2026 à 09:39 Europe/Paris,
avec la même grille de 480 cellules et sans réoptimisation. Le
[rapport final](../../artifacts/cn/economic/sprint13b5/full/sprint13b-fcc5a4b464c50832/report.json)
confirme **462 cellules valides et 18 censurées**. Son statut est
`COMPLETE_RESEARCH_BLOCKED_OR_PARTIAL` : `economic_go_allowed=false`,
`serving_enabled=false` et `live_enabled=false`. Les journaux sont dans
`log/batch/cn-sprint13b5-full-20260927-012419/`.

### Lecture économique du replay homogène

En scénario de fill `base` et au profil de coûts `cn_a_research`, les
trois politiques sont simultanément valides dans 39 des 40 combinaisons
semestre × seed. Le rendement semestriel marqué moyen de ces mêmes cas
est de −3,06 % pour Oracle seul, −1,41 % pour le veto retournement et
−1,77 % pour le veto LightGBM. En comparaison appariée avec Oracle,
le veto retournement améliore en moyenne de +1,65 point (21 cas améliorés,
18 dégradés) et le veto LightGBM de +1,30 point (23 améliorés,
16 dégradés). Ce sont des statistiques descriptives sur les cas valides,
non un rendement composé ni un GO économique.

| Semestre | Oracle seul | Veto retournement | Veto LightGBM | Seeds valides |
| --- | ---: | ---: | ---: | ---: |
| 2022H1 | −16,67 % | −15,41 % | −18,35 % | 5 |
| 2022H2 | −10,94 % | −9,01 % | −13,43 % | 5 |
| 2023H1 | −2,17 % | +2,23 % | +2,14 % | 5 |
| 2023H2 | −16,03 % | −17,97 % | −12,55 % | 4 |
| 2024H1 | −22,44 % | −22,29 % | −15,46 % | 5 |
| 2024H2 | +22,71 % | +33,98 % | +25,73 % | 5 |
| 2025H1 | +11,49 % | +9,53 % | +9,59 % | 5 |
| 2025H2 | +6,93 % | +4,32 % | +6,02 % | 5 |

Le classement change selon le semestre : les veto ne dominent pas
Oracle de manière stable. Le CSI 300 du rapport est seulement un contexte
indiciel brut, sans les mêmes coûts ou règles de fill. Ces périodes OOS
ont déjà été inspectées ; elles ne forment pas un holdout indépendant.

## Cas qui restent censurés

| Cas | Pourquoi ne pas inventer un résultat |
| --- | --- |
| `sz.000046`, 2023H2/seed 2 | Les trois politiques possèdent les mêmes 9 600 actions à la fin du semestre. Le dernier mark local est 0,38 CNY, soit 3 648 CNY, mais la sortie H20 reste en attente, puis le titre est radié. Le montant marqué n'est **pas** un produit de vente prouvé. Le recouvrement et la date réelle sont inconnus. |
| `sh.688175`, 2024H1/seed 0, coûts stress | 414 actions × 0,4 donnent 165,6 actions nouvelles théoriques. La règle agrégée de l'émetteur ne permet pas de savoir quelle allocation entière/cash-in-lieu aurait été reçue par ce compte hypothétique. La fraction est économiquement petite, mais le replay exact reste censuré. Une action valait au plus 17,04 CNY entre l'ex-date et la fin du semestre, soit 0,017 % du capital initial de 100 000 CNY ; c'est une **borne de sensibilité**, pas un fill ni un PnL valide. |

Le suivi de la radiation ne permet pas de valoriser les actions à zéro
par convention. Même si les trois politiques ont ici la même quantité
de `sz.000046`, seules leurs différences de cash final peuvent être
comparées conditionnellement à un recouvrement commun ; leurs
rendements semestriels absolus restent invalides.

## Anomalie de référentiel distincte

Le référentiel local `instrument_provider_symbols` indique actuellement
`sz.302132` depuis le 27/08/2010, alors que l'émetteur documente le
passage de `sz.300114` à `sz.302132` au 17/02/2025. B5 ne modifie
pas l'identité économique de l'instrument ni les barres, mais ce
`valid_from` est historiquement faux. Il exige un audit séparé des
jointures symbole/PIT avant tout usage CN en production.

## Gate

- replays B5 ciblés : validité technique et absence de nouveau blocage ;
- audit de matérialité : compte des récupérations, des résiduels et des
  comparaisons appariées, **sans rendement mélangé** ;
- campagne homogène complète : terminée, 462/480 valides et 18 censurées,
  avec un statut explicite pour les deux cas encore non évaluables ;
- aucun GO économique, aucune activation serving/live sur ce travail
  rétrospectif déjà inspecté.

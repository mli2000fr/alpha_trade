# Sprint 15-D3 — Robustesse historique Dragon/Tiger 2018–2025

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Audit achevé le 30 septembre 2026. **Verdict : réconciliation des identités confirmée sur l'échantillon historique, intégrité structurelle des sièges plausible ; pas de certification PIT, pas de GO ML.** Aucun modèle, batch quotidien, table, backtest ou serving n'a été modifié.

## Périmètre pré-enregistré

Le [pilote 15-D2](./sprint_15d2_audit_dragon_tiger_pit.md) avait rapproché quatre séances 2024–2025. Pour sortir de ce petit échantillon, 15-D3 choisit **deux séances par année de 2018 à 2025**, sans regarder les événements ou rendements : positions `n//3` et `2n//3` dans le calendrier `market_sessions` CN_A ouvert, ordonné par date. Les **16 dates ont été écrites dans `preregistered_dates.json` avant les requêtes fournisseurs** : 2018-05-08, 2018-08-30, 2019-05-08, 2019-08-30, 2020-05-08, 2020-09-02, 2021-05-10, 2021-09-01, 2022-05-10, 2022-09-01, 2023-05-08, 2023-08-31, 2024-05-08, 2024-08-30, 2025-05-09 et 2025-09-02.

Sources lues en lecture seule : [SSE marché principal](https://www.sse.com.cn/disclosure/diclosure/public/dailydata/), [SSE STAR](https://www.sse.com.cn/disclosure/diclosure/public/dailydatatib/), [SZSE](https://www.szse.cn/disclosure/deal/public/index.html), puis archive Eastmoney comme comparateur. Pagination SZSE et Eastmoney vérifiée contre leurs compteurs. Même périmètre **actions A seulement** que 15-D2 ; ni B shares, ni obligations, ni REITs, ni Beijing. Les filtres de préfixe restent un outil d'audit, **pas** un substitut au security master PIT.

## Résultat d'identité

| Année | Séances | Couples marché–titre officiels | Concordances Eastmoney | Écarts après qualification |
| --- | ---: | ---: | ---: | ---: |
| 2018 | 2 | 91 | 91 | 0 |
| 2019 | 2 | 138 | 138 | 0 |
| 2020 | 2 | 109 | 109 | 0 |
| 2021 | 2 | 156 | 156 | 0 |
| 2022 | 2 | 120 | 120 | 0 |
| 2023 | 2 | 122 | 122 | 0 |
| 2024 | 2 | 123 | 123 | 0 |
| 2025 | 2 | 126 | 126 | 0 |
| **Total** | **16** | **985** | **985** | **0** |

Ces 985 sont des couples **séance–marché–titre** additionnés, pas 985 entreprises distinctes. Les bourses fournissent 1 120 lignes de motifs : un titre peut être publié plusieurs fois le même jour pour des critères différents.

Deux différences apparentes du premier passage 2018 (`600094` le 08/05 et `601198` le 30/08) étaient des notices « **achats sur marge du jour > 50 % du volume** » incluses par l'agrégateur dans la même famille de rapport. Elles relèvent d'une autre rubrique officielle que la liste d'activité anormale auditée ici. Elles ont été exclues **par motif explicite** et les mêmes 16 dates ont été recalculées ; elles ne sont pas des lacunes du SSE. Le catalogue SZSE retourne en outre `1842_xxpl` sur les dates anciennes et `1842_xxpl_after` ensuite : le pilote accepte ces deux identifiants et refuse les autres familles.

La concordance parfaite d'identité sur 16 dates **ne prouve pas** l'exhaustivité quotidienne sur huit ans, ni l'absence de corrections, ni la conformité des montants.

## Motifs et montants des sièges : ce qui est vérifié

- **SSE** : sur 396 lignes de motifs, **395 possèdent les deux listes de sièges** et une (`605255`, 02/09/2025, motif `Z5`) n'en fournit aucune dans la réponse. Là où les listes existent, le nombre de noms correspond au nombre de montants, tous les montants présents sont numériques et non négatifs : **zéro anomalie de format détectée**, mais une liste absente à qualifier. Les tableaux principal et STAR n'utilisent pas nécessairement la même unité affichée : aucune agrégation de montants entre boards n'a été faite.
- **SZSE** : un détail officiel `1842_detal` par séance a été sélectionné mécaniquement par code/motif, soit **16 détails**. Les 16 renvoient dix lignes de sièges, le même motif que la liste et aucun montant d'achat/vente illisible dans les champs contrôlés. Ce n'est qu'un échantillon de détails, pas le contrôle de toutes les lignes.
- **Entre fournisseurs** : les motifs textuels/référentiels et les montants par siège **n'ont pas été rapprochés ligne à ligne à Eastmoney**. Son endpoint de détail candidat n'a pas fourni une réponse exploitable dans le smoke. Le résultat 985/985 porte seulement sur **date + marché + code**.

Un siège « institutionnel » ou « Stock Connect » n'identifie pas le propriétaire économique final ; il ne faut pas convertir un montant publié en « achat institutionnel net » sans définition et réconciliation supplémentaires.

## PIT et fuite de label

Le jour de transaction, le début d'une fenêtre d'anomalie sur plusieurs jours et la date de publication ne sont **pas interchangeables**. Ni les réponses officielles consultées ni Eastmoney n'ont établi ici l'heure **historique** à laquelle chaque ligne est devenue publique. Une utilisation au début de la séance J serait une fuite. Toute étude exploratoire devrait décaler l'événement J à **J+1** et refaire une sensibilité **J+2**, sans appeler cela PIT certifié.

Eastmoney retourne des rendements futurs `D1/D2/D5/D10/D20/D30_CLOSE_ADJCHRATE` ainsi qu'un champ `EXPLAIN` contenant parfois un taux de réussite a posteriori. Le pilote détecte ces colonnes mais n'enregistre **aucune valeur** dans l'échantillon assaini. Il n'y a pas de backtest, d'ablation ni de score D1/D10 en 15-D3. Le biais de sélection est majeur : figurer sur la liste signifie que la séance J a déjà été atypique.

## Décision et prochain gate

**15-D3 = `GO_SOURCE_IDENTITY_BREADTH_SAMPLE`, `SEAT_STRUCTURE_PARTIAL`, `NO_GO_HISTORICAL_PIT_ML`.** La piste reste intéressante comme événement rare de confirmation, pas comme signal quotidien universel.

Étape suivante possible : **15-D4, audit de contrat temporel et de couverture Oracle**. Il devra obtenir/éprouver les heures de diffusion ou, à défaut, isoler clairement un proxy J+1/J+2 ; faire le mapping `instrument_id` PIT ; vérifier les montants et motifs par siège sur davantage de cas et les corrections ; estimer la part de paires Oracle réellement couvertes. Une ablation directionnelle ne sera ouverte qu'après un protocole pré-enregistré, apparié sur les mêmes titres/dates et mouvement de J, avec abstention et résultats LONG/SHORT séparés. Il faut confirmer les droits et limites des interfaces avant un backfill quotidien complet.

Reproduction : `service/market/cn_dragon_tiger_robustness_15d3.py` s'appuie sur `service/market/cn_dragon_tiger_pilot_15d2.py`. Le rapport final est `artifacts/research/cn_dragon_tiger_15d3/pilot-20260929-final/report.json`, avec dates fixées et échantillons officiels/assainis dans le sous-dossier `reconciliation`. Le premier essai et le recalcul intermédiaire restent séparés pour la traçabilité ; **`pilot-20260929-final` fait foi**. Tests ciblés : `tests/test_cn_dragon_tiger_pilot_15d2.py` et `tests/test_cn_dragon_tiger_robustness_15d3.py`.

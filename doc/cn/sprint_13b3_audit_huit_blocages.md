# Sprint 13-B3 — Audit des blocages révélés par cinq seeds

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Périmètre et résultat initial

Le [replay de robustesse](../../artifacts/cn/economic/sprint13b/sprint13b-273492bdfbcf1230/report.json)
a exécuté 480/480 cellules : huit semestres, trois politiques (Oracle et
les deux veto), cinq seeds, deux scénarios de fill et deux coûts. Il compte
398 replays valides et 82 bloqués. Ce sont **huit titres** à examiner,
mais neuf causes événementielles : `sz.003010` a deux distributions
distinctes non résolues.

Chaque veto ne peut être comparé à Oracle que sur 130/160 cellules
appariées. La moyenne exploratoire est proche de +2 points semestriels
pour les deux veto, mais les cellules sont corrélées, les seeds divergent
et les périodes ont déjà été inspectées. Le plan B3 ne supprime aucun
symbole ex-post et n'autorise aucun GO économique.

## Vérification événement par événement

| Titre / action | Constat dans la source locale et le replay | Décision |
| --- | --- | --- |
| `sz.002112`, action `14811`, 23/09/2022 | Cache BaoStock : `10转3`, 0,3 action/action, cash absent et aucun cash décrit ; ratio facteur 1,300539 contre 1,300000 théorique (écart 0,0415 %). La règle de classification share-only déjà corrigée en A2 prouve désormais l'événement. | **Promouvoir uniquement cet ID**, dans une preuve B3 versionnée ; base canonique et preuve B2 inchangées. |
| `sz.002443`, action `16255`, 30/05/2022 | Source : 0,4 CNY/action, sans nouvelles actions ; facteur observé 3,851061 contre 1,046838 théorique. | Rester censuré : contradiction majeure, une preuve indépendante des termes et de la chaîne de facteurs est nécessaire. |
| `sz.003010`, actions `19014` et `19015` | Source : 0,3 CNY +0,4 action/action en 2024, puis 0,5 CNY +0,4 en 2025. Écarts de facteur 1,96 % et 0,95 %. | Censuré en B3 ; la [preuve B4](./sprint_13b4_dilution_actions_rachetees.md) examine ensuite les actions rachetées non éligibles publiées par l'émetteur, sans traiter l'écart comme un simple arrondi. |
| `sz.302132`, action `316`, 18/02/2025 | Aucune distribution à cette ex-date dans la réponse BaoStock 2025 ; les deux distributions présentes concernent juin. | Rester censuré ; rechercher une autre opération ou une correction du fournisseur. |
| `sz.300862`, action `23221`, 12/12/2025 | Source : 0,005 CNY/action ; facteur observé 0,701741 contre 1,000204 théorique. | Rester censuré : contradiction majeure. |
| `sz.301042`, action `24005`, 27/05/2024 | Source : 1,2 CNY/action ; facteur observé 1,033888 contre 1,035098 théorique (écart 0,117 %). | Censuré en B3 ; la [preuve B4](./sprint_13b4_dilution_actions_rachetees.md) vérifie ensuite la dilution par actions rachetées à tolérance inchangée. |
| `sh.688175`, action `10490`, 06/06/2024 | Distribution validée : +0,4 action/action. Avec 414 actions détenues dans le scénario stress, le droit calculé donne 579,6 actions ; le replay ne connaît pas la règle de fractions/cash-in-lieu réellement appliquée. | Rester censuré pour cette cellule ; obtenir les règles ou le règlement de cette opération avant d'ajouter une compensation. |
| `sz.000046`, sortie H20 signalée le 26/12/2023 | Après le 27/12, les barres ont un dernier cours répété à 0,38 CNY mais aucun volume ; le titre est radié le 07/02/2024. La vente reste en attente à la clôture de 2023H2. | Rester censuré ; ni vente au dernier cours, ni valeur zéro arbitraire. Il faut une preuve de liquidation/recouvrement et un suivi hors semestre. |

Les constats de source sont issus des réponses BaoStock archivées sous
`artifacts/cn/corporate_actions/sprint13a2/queries/`, de la preuve A2/B2,
des barres brutes CN et des journaux du replay. Ils reconstruisent le
PnL ex-post ; aucune information découverte après la date de signal ne
devient une feature PIT.

## Suite contrôlée

Le [constructeur B3](../../modelFactory/cn_economic_remediation_13b3.py)
vérifie l'ID, le symbole, l'ex-date, les termes, la date de droit, le hash
de la source et la cohérence du facteur, puis émet une nouvelle preuve
hashée. Un replay ciblé de 2022H2/seed 4 doit confirmer que les cellules
touchées deviennent valides sans changement de signaux, coûts ou fill.
Les autres blocages restent visibles ; une campagne complète B3 ne
deviendrait pertinente qu'après preuve indépendante des termes/règlements.

### Replay ciblé exécuté

Le [rapport B3 2022H2/seed 4](../../artifacts/cn/economic/sprint13b/sprint13b-a2c0b052ac0fdc6b/report.json)
confirme **12/12 cellules valides** (trois politiques × deux scénarios ×
deux coûts), contre **8 bloquées et 4 valides** avec la preuve B2 : les
deux veto détenaient le titre, Oracle n'était pas bloqué dans ce
sous-ensemble. À fill `base` et coût `cn_a_research`, les rendements
proxy sont Oracle −8,005 %, veto retournement −11,105 % et veto
LightGBM −19,108 %. Réhabiliter un calcul **n'améliore pas** la stratégie
sur cette cellule ; les trois résultats restent de recherche, sur OOS
déjà inspecté. Le rapport de sous-ensemble conserve le statut global
`COMPLETE_RESEARCH_BLOCKED_OR_PARTIAL` par construction : il ne vaut
pas validation de la grille complète B3.

Dans les 480 replays, `base` et `conservative` ont produit des rendements,
fills et statuts identiques cellule par cellule. Le scénario de stress
de participation à 1 % ne s'est pas activé dans cette campagne : il
**ne constitue pas une preuve de robustesse d'exécution**.

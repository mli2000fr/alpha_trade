# Sprint 13-B4 — Dividendes et transferts avec actions rachetées

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Pourquoi le facteur paraissait contradictoire

La preuve A2 compare par défaut le ratio du facteur de prix avec les
droits économiques **par action éligible détenue**. Quand l'émetteur a
des actions en autocontrôle, celles-ci ne reçoivent ni cash ni actions
nouvelles, mais le facteur de référence est calculé sur le nombre total
d'actions. Les deux ratios ne sont alors pas égaux. Élargir la tolérance
générale serait incorrect ; il faut la table de capitalisation publiée
par l'émetteur pour cette opération précise.

Pour chaque action promue, la preuve B4 conserve les droits réels par
action détenue et vérifie séparément :

```text
cash dilué = cash par action éligible × actions éligibles / actions totales
transfert dilué = actions effectivement émises / actions totales
facteur théorique = cours brut précédent × (1 + transfert dilué)
                   / (cours brut précédent − cash dilué)
```

| Action / titre | Droit pour le portefeuille | Actions totales / éligibles / émises | Écart du facteur brut → après dilution |
| --- | --- | --- | --- |
| `19014` / `sz.003010`, 13/06/2024 | 0,30 CNY + 0,4 action | 122 329 340 / 114 591 433 / 45 836 573 | 1,96 % → 0,033 % |
| `19015` / `sz.003010`, 09/06/2025 | 0,50 CNY + 0,4 action | 164 030 506 / 158 643 606 / 63 457 442 | 0,95 % → 0,0068 % |
| `24005` / `sz.301042`, 27/05/2024 | 1,20 CNY, pas d'action nouvelle | 69 738 577 / 67 648 943 / 0 | 0,117 % → 0,0118 % |

Les preuves primaires sont [l'avis d'exécution 2024 de 若羽臣](https://static.cninfo.com.cn/finalpage/2024-06-05/1220256283.PDF),
son [rapport semestriel 2025](https://disc.static.szse.cn/download/disc/disk03/finalpage/2025-08-20/11eb9df5-71c7-4f9a-8f17-23e4bcb263e8.PDF),
et le [rapport annuel 2024 d'安联锐视](https://static.cninfo.com.cn/finalpage/2025-04-25/1223276657.PDF).
Les rapports publiés après la date de signal ne servent qu'à la
réconciliation rétrospective du PnL, jamais à l'entraînement PIT.

Le [constructeur B4](../../modelFactory/cn_economic_remediation_13b4.py)
part de la preuve B3 hashée, vérifie l'ID, le titre, la date, les droits
BaoStock, la date de registre, les nombres d'actions publiés et le
facteur dilué à la tolérance A2 **inchangée**. La preuve B4 est additive :
aucune mise à jour de `cn_corporate_actions`, aucun changement de règle
générale, aucun nouveau signal et aucune exclusion rétroactive.

## Limites

Le facteur d'origine reste consigné comme contradictoire sans dilution.
Les cash dividends restent avant impôt. Les transferts qui produisent
une fraction d'action dans un compte donné restent censurés tant que
leur allocation effective n'est pas connue ; B4 ne résout donc pas le
cas `sh.688175` de 2024H1. Les titres `sz.002443`, `sz.302132` et
`sz.300862`, ainsi que la sortie du titre radié `sz.000046`, ne sont
pas modifiés par cette preuve.

## Replays ciblés terminés le 27/09/2026

Les deux replays portent chacun sur trois politiques, deux scénarios
de fill et deux profils de coûts, soit 12 cellules par semestre. Les
24 cellules sont `RESEARCH_MARK_VALID` ; aucune position non résolue
n'est utilisée pour les marques de ces sous-ensembles. Les rapports
reproductibles sont [2024H1/seed 4](../../artifacts/cn/economic/sprint13b/sprint13b-921389b90216f681/report.json)
et [2025H1/seed 2](../../artifacts/cn/economic/sprint13b/sprint13b-456bd82b16a044f1/report.json).

| Sous-ensemble, scénario `base`, coûts `cn_a_research` | Oracle seul | Veto reversal | Veto LightGBM |
| --- | ---: | ---: | ---: |
| 2024H1, seed 4 | −32,77 % | −29,41 % | −33,70 % |
| 2025H1, seed 2 | +21,73 % | +15,81 % | +15,67 % |

La remédiation lève des blocages **de qualité des données**, pas
l'incertitude économique. En 2024H1, les trois politiques perdent ; en
2025H1, Oracle seul dépasse les deux veto. Ces dates et seeds avaient
déjà été inspectés : ce ne sont pas des holdouts indépendants. Les 24
cellules ciblées ne remplacent ni les 480 cellules de la campagne B3,
ni les événements encore censurés. Verdict : **aucun GO économique,
aucune activation serving/live**.

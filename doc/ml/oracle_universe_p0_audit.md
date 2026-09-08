# P0 — Audit de l’univers Oracle de 400 symboles

## Objet

Cet audit vérifie si les labels D1/D10 et `oracle_extreme10` du batch
`model-factory-20260907170018-0e94ac` reposent sur un univers historiquement
représentatif. Il ne réentraîne aucun modèle et ne modifie aucune table.

Le batch couvre 2016-01-01 → 2025-12-31, à l’horizon H20. Sa source persistée
est `universe-file:ticket_recherche.txt`. La liste persistée dans
`model_training_batch.symbols` contient 400 symboles uniques et correspond
exactement au fichier actuel. `ticket_recherche.txt` et
`ticket_mid_cap_400.txt` ont le même SHA-256 :
`513f5f50eaf10ac961b859f8bee7712a5182c34528ba2d5a741d1a3e9d01c9e8`.

## Verdict

Le biais est confirmé, mais doit être nommé précisément :

> Les données d’un titre ne sont pas injectées avant sa première barre. En
> revanche, la liste des sociétés est une sélection statique récente rejouée
> dans le passé. Il s’agit d’un biais de sélection/survivorship de l’univers,
> pas d’une fuite directe dans les features ou les rendements futurs.

Le code charge un `universe-file:*` comme une liste fixe. Seule la source
`tradable-universe` utilise le résolveur de snapshots PIT. Lors de la création
des labels, les rangs sont néanmoins recalculés intra-date sur les seuls
rendements valides du jour. Une société introduite en 2024 n’est donc pas
présente dans les rangs 2016 ; le biais vient de la sélection préalable des
survivants et non de fausses barres historiques.

## Couverture historique

| Mesure | Résultat |
|---|---:|
| Symboles demandés / avec barres | 400 / 400 |
| Présents dès le début selon la première barre disponible | 288 |
| Première barre après le début de l’entraînement | 112 |
| Première barre en 2020 ou après | 60 |
| Première barre en 2022 ou après | 14 |
| Couverture ≥ 95 % des 2 514 séances SPY | 291 |

La première barre est un proxy de présence dans `stock_bars_daily`, pas une
date officielle d’IPO. Les cas les plus récents incluent notamment AMTM, WAY,
RBRK, CTRI, SOLV, BTSG, KVYO, SN, KGS, ATMU, ATAT, MBLY, CRBG et TPG.

## Composition courante

Les 400 lignes sont actuellement `active`, `tradable=1`, `bars_available=1` et
`asset_class=us_equity`. Cela démontre précisément le filtre sur l’état courant,
mais pas leur admissibilité historique.

| Capitalisation courante | Symboles |
|---|---:|
| Mini cap < 500 M$ | 0 |
| Small cap 500 M$–2 Md$ | 31 |
| Mid cap 2–10 Md$ | 252 |
| Large cap ≥ 10 Md$ | 117 |

Les principaux secteurs courants sont Technology 40, Real Estate 35, Retail
28, Energy 25, Hotels/Restaurants/Leisure 23, Financial Services 23 et Media
21. `stock_metadata` ne contient ni pays ni type d’instrument détaillé. Les ADR,
REIT, BDC, MLP et titres ordinaires étrangers ne peuvent donc pas être classés
de façon certaine uniquement avec le schéma actuel. Ces informations courantes
ne doivent pas être utilisées comme si elles étaient PIT.

## Concentration D1/D10

Sur 890 928 labels, le correctif de qualité conserve 890 789 lignes et isole
103 `missing_exit_bar` et 36 `known_security_discontinuity`.

| Population la plus contributrice | Extrêmes | D1 | D10 |
|---|---:|---:|---:|
| Top 10 % des symboles | 23,7 % | 24,0 % | 24,0 % |
| Top 20 % des symboles | 41,0 % | 41,3 % | 42,0 % |
| Top 30 % des symboles | 55,3 % | 55,8 % | 56,1 % |

Une répartition uniforme donnerait respectivement 10 %, 20 % et 30 %. Les
tails sont donc fortement concentrés sur les mêmes titres.

La fréquence `oracle_extreme10` est très liée aux propriétés structurelles :

| Relation | Spearman |
|---|---:|
| Fréquence extrême / volatilité réalisée | 0,895 |
| Fréquence extrême / range intraday médian | 0,918 |
| Fréquence extrême / bêta SPY | 0,417 |
| Fréquence extrême / dollar-volume médian | −0,014 |

Par quintile de volatilité, la fréquence extrême moyenne passe de 7,8 % dans
le quintile le plus calme à 40,8 % dans le quintile le plus volatil. L’Oracle
est donc entraîné sur une cible qui encode fortement la propension structurelle
d’un symbole à produire les extrêmes cross-sectionnels. Cette propriété peut
être utile pour prédire l’amplitude, mais elle complique l’interprétation de
l’Oracle comme détecteur d’un événement exceptionnel nouveau.

## Comparaison aux snapshots PIT existants

Les tables PIT couvrent 2 500 dates comparables sur la période et contiennent
765 symboles distincts, dont 368 absents de la liste statique. Cependant :

- taille médiane du panel statique avec label : 358 ;
- taille médiane du snapshot PIT tradable : 37 ;
- Jaccard médian : 10,0 % ;
- 97,6 % des dates sont marquées `degraded` ;
- le nombre moyen de titres PIT tombe à 8 en 2022 et 6 en 2023.

Ces snapshots prouvent qu’une composition historique différente existe, mais
ils ne peuvent pas encore servir de gold standard. Leur couverture doit être
réparée ou une référence bar-only doit être reconstruite avant de recalculer
des D1/D10 PIT.

## Conséquence scientifique

Le batch reste valable pour la question conditionnelle : « parmi ces 400
sociétés sélectionnées récemment, quels jours historiques ont produit les plus
grands mouvements ? ». Il ne mesure pas sans correction la performance qu’un
opérateur aurait obtenue avec l’univers connaissable à chaque date.

La prochaine étape autorisée est P0b : construire une population historique
éligible avec historique minimal, prix et liquidité trailing strictement PIT,
puis qualifier les sources historiques de capitalisation, pays, type et statut
de cotation. Ensuite seulement, comparer les labels actuels aux D1/D10
recalculés sur cette référence. Aucun nouvel entraînement directionnel n’est
justifié avant cette comparaison.

La procédure réutilisable de renouvellement est définie dans le
[guide de sélection des univers ML et Oracle](oracle_universe_selection_playbook.md).
La première reconstruction quotidienne bar-only et la comparaison des labels
sont consignées dans [P0b — univers dynamique](oracle_universe_p0b_dynamic.md).

## Artefacts et reproduction

- Rapport généré :
  `artifacts/research/oracle_universe_audit/audit-20260908163854-0e94ac/report.md`
- Détail des 400 symboles : `symbol_audit.csv`
- Recouvrement quotidien : `pit_overlap_daily.csv`
- Agrégats sectoriels : `sector_summary.csv`
- Synthèse machine-readable : `summary.json`

Commande :

```powershell
python -m modelFactory.oracle_universe_audit --batch-id model-factory-20260907170018-0e94ac
```

# E17-C — Robustesse historique verrouillée du momentum résiduel H120

## 1. Verdict

E17-C conclut **`NOT_ROBUST`** selon les gates pré-enregistrés.

Le signal conserve une valeur de classement cross-sectionnel réelle contre
l’univers équipondéré, mais il n’est ni stable dans tous les blocs temporels ni
statistiquement supérieur à SPY. Ce résultat ne remet pas E17 en `GO` et ne
permet aucune promotion.

## 2. Portée scientifique

E17-C est un audit **post-découverte**. Le momentum résiduel H120 a été choisi
après l’analyse E17 sur 2018–2025. Les mêmes années peuvent tester la fragilité
du résultat sous différents découpages, mais elles ne redeviennent pas OOS.

Le protocole machine porte donc explicitement :

```text
validation_class = post_discovery_historical_robustness_not_oos
oos_claim_authorized = false
promotion_authorized = false
oracle_used = false
```

## 3. Contrat verrouillé avant calcul

| Élément | Contrat |
|---|---|
| Source | panel E17 figé |
| Période | 2018-07-01 au 2025-12-31 |
| Signal | momentum résiduel 120–10 |
| Horizon | H120 |
| Portefeuille | long-only TOP20, équipondéré |
| Entrée/sortie | open J+1 / open J+121 |
| Rebalance | 20 séances |
| Coût primaire | 6 bps aller-retour |
| Comparateurs | univers éligible équipondéré et SPY |

Le fichier
`config/research/e17c_residual_momentum_h120_robustness.json` est protégé par
l’empreinte canonique :

```text
a3d9469922bd45bd64f586b22de69fb60ead04532d69418cb0d3800489660869
```

Les contrôles figés sont : trois blocs temporels, cinq sous-univers par hash,
quatre origines de calendrier, trois niveaux de coûts, stabilité sectorielle et
concentration des contributions.

## 4. Résultat principal

Les rendements ci-dessous sont les rendements moyens d’une cohorte H120. Les 95
cohortes se chevauchent en raison de la rebalance toutes les 20 séances ; il ne
faut pas les lire comme des rendements annuels indépendants.

| Mesure | Résultat |
|---|---:|
| Cohortes | 95 |
| Titres sélectionnés en moyenne | 250,8 |
| Rendement LONG net | +7,696 % |
| Excès contre univers équipondéré | +2,294 % |
| IC95 contre univers | **[+0,959 % ; +3,463 %]** |
| Excès contre SPY | +1,194 % |
| IC95 contre SPY | **[−1,279 % ; +4,093 %]** |
| Semestres avec excès positif vs univers | 86,67 % |
| Part des 20 symboles les plus contributeurs | 13,36 % |

Le signal classe donc correctement les actions les unes par rapport aux autres.
En revanche, la preuve qu’il crée plus de valeur qu’une exposition simple à SPY
n’est pas établie.

## 5. Stabilité temporelle

| Bloc | Cohortes | LONG net | Excès vs univers | Excès vs SPY |
|---|---:|---:|---:|---:|
| 2018H2–2020 | 32 | +11,921 % | +3,179 % | +4,194 % |
| 2021–2022 | 25 | **−0,843 %** | **−0,770 %** | **−1,568 %** |
| 2023–2025 | 38 | +9,755 % | +3,564 % | +0,484 % |

Le bloc central échoue clairement. L’excès contre l’univers est négatif et son
IC95 `[-2,252 % ; +1,001 %]` recouvre zéro. Deux semestres sont particulièrement
défavorables : 2021H2 (`−3,066 %` vs univers) et 2022H2 (`−2,153 %`).

Cette rupture suffit à rejeter l’hypothèse d’un alpha universel stable. Elle est
compatible avec un signal dépendant du régime, mais E17-C ne teste ni ne choisit
un filtre de régime.

## 6. Sous-univers déterministes

Les symboles sont répartis dans cinq groupes par SHA-256 avec un sel figé. Dans
chaque groupe, le TOP20 est recalculé indépendamment.

| Fold | Excès vs univers | Excès vs SPY |
|---|---:|---:|
| 0 | +1,325 % | +0,342 % |
| 1 | +3,068 % | +2,072 % |
| 2 | +2,745 % | +1,950 % |
| 3 | +2,052 % | +0,321 % |
| 4 | +2,293 % | +1,228 % |

Les cinq groupes sont positifs contre leur univers. Le résultat ne dépend donc
pas d’un petit sous-ensemble arbitraire de symboles.

## 7. Sensibilité au calendrier

| Décalage de la première rebalance | Cohortes | Excès vs univers |
|---|---:|---:|
| 0 séance | 95 | +2,294 % |
| 5 séances | 94 | +2,526 % |
| 10 séances | 94 | +2,439 % |
| 15 séances | 94 | +2,430 % |

Les quatre calendriers restent positifs. Le résultat n’est pas produit par un
jour de rebalance particulièrement favorable.

## 8. Coûts et concentration

Le rendement LONG moyen reste positif à 6, 12 et 25 bps : respectivement
`+7,696 %`, `+7,636 %` et `+7,506 %` par cohorte.

L’excès contre l’univers est identique dans ce stress parce que le même coût
aller-retour est appliqué au portefeuille sélectionné et au comparateur
équipondéré ; il s’annule algébriquement dans la différence. Ce gate confirme
la positivité absolue à coûts renforcés, mais n’apporte pas une preuve
supplémentaire sur l’excès relatif. Le protocole étant verrouillé, cette règle
n’a pas été remplacée après observation.

Les 20 plus grands contributeurs ne portent que 13,36 % de la somme des
contributions positives, sous le plafond de 35 %. Le signal n’est pas expliqué
par quelques gagnants isolés.

## 9. Stabilité sectorielle

Après application stricte d’au moins 25 titres disponibles par cohorte et 12
cohortes par secteur, 21 secteurs sont exploitables. Quatorze sont positifs
contre leur univers sectoriel, soit 66,67 %, au-dessus du gate de 60 %.

Ce résultat est favorable, mais ne compense pas l’échec temporel et l’absence de
preuve contre SPY.

## 10. Gates

| Gate pré-enregistré | Résultat |
|---|---|
| Au moins 80 cohortes | PASS |
| LONG net positif | PASS |
| IC95 excès vs univers > 0 | PASS |
| IC95 excès vs SPY > 0 | **FAIL** |
| Au moins 70 % des semestres positifs | PASS |
| Tous les blocs temporels positifs | **FAIL** |
| Au moins 80 % des hash folds positifs | PASS, 100 % |
| Tous les calendriers positifs | PASS |
| Positif sous 25 bps | PASS |
| Au moins 60 % des secteurs positifs | PASS, 66,67 % |
| Concentration top 20 ≤ 35 % | PASS, 13,36 % |

Deux échecs sur onze imposent `NOT_ROBUST`.

## 11. Interprétation et action autorisée

E17-C consolide une conclusion plus précise que « le signal ne fonctionne
pas » :

> Le momentum résiduel H120 est un alpha de sélection relative diversifié, mais
> dépendant du temps et insuffisamment distinct d’une exposition à SPY.

Il ne doit pas être intégré au live ni utilisé comme solution directionnelle
D1/D10. Une nouvelle expérience pourrait pré-enregistrer une hypothèse de
régime expliquant 2021–2022, mais elle devrait utiliser des règles économiques
définies avant résultats et ne pourrait pas recycler ce rapport comme
confirmation indépendante.

## 12. Reproductibilité

```powershell
.\.venv\Scripts\python.exe -u -m modelFactory.directional_alpha_book_robustness --log-level INFO
```

Artefact canonique :

```text
artifacts/research/directional_alpha_book_robustness/e17c-robustness-20260911201018/
├── report.json
├── primary_cohorts.csv
├── primary_constituents.csv
└── sector_summary.csv
```

Implémentation : `modelFactory/directional_alpha_book_robustness.py`.

Tests : `tests/test_directional_alpha_book_robustness.py`.


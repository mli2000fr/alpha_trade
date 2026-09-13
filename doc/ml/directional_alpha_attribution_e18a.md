# E18-A — Attribution bêta, secteurs et régimes du momentum résiduel H120

## 1. Verdict

E18-A conclut **`MARKET_OR_SECTOR_EXPOSURE`**. L’analyse détaillée précise que
l’exposition dominante est le **marché**, et non un simple pari sectoriel.

Le signal conserve une capacité de classement relative après neutralisation
sectorielle. En revanche, la performance absolue du portefeuille TOP20 est
principalement expliquée par son exposition à SPY. Après couverture bêta et
neutralisation sectorielle simultanées, aucun alpha statistiquement démontré ne
reste.

## 2. Question d’attribution

E17-C montrait un paradoxe :

- excès significatif contre l’univers équipondéré ;
- absence de supériorité statistique contre SPY ;
- échec temporel en 2021–2022.

E18-A décompose donc le rendement sans changer le signal :

```text
TOP20 momentum résiduel H120
        │
        ├── rendement brut
        ├── rendement couvert du bêta SPY
        ├── sélection neutralisée par secteur
        └── sélection sector-neutral + couverture bêta
```

L’expérience est post-découverte, indépendante de l’Oracle et ne revendique pas
un nouvel OOS.

## 3. Contrat pré-enregistré

| Élément | Valeur |
|---|---|
| Signal | `residual_momentum_120_10` |
| Horizon | H120 |
| Population | panel E17, 1 798 symboles |
| Période | 2018-07-01 au 2025-12-31 |
| Portefeuille | long-only TOP20, équipondéré |
| Cohortes | rebalance toutes les 20 séances |
| Coût LONG | 6 bps aller-retour |
| Coût couverture SPY | 6 bps × valeur absolue du bêta |
| Bêta | covariance/variance glissante 126 séances, bornée `[-5,+5]` |
| Secteurs | poids du secteur identique à l’univers éligible à J |

Le protocole est verrouillé dans
`config/research/e18a_residual_momentum_attribution.json` avec l’empreinte :

```text
36d2d2c7e3d07ed8885c9622c7415d2a4abd81de5ad07cff317f5bfa76651b1a
```

## 4. Causalité PIT

Le bêta de chaque titre est estimé au close J avec les 126 rendements connus à
J. Les états SPY utilisent également uniquement les données disponibles à J :

- tendance : close ajusté SPY comparé à SMA200 ;
- volatilité : volatilité réalisée 20 jours comparée à celle sur 252 jours.

Changer les cours postérieurs à J ne modifie pas le bêta calculé à J. Les
rendements futurs H120 n’interviennent que dans l’évaluation.

## 5. Résultat global

| Décomposition | Moyenne par cohorte H120 | IC95 |
|---|---:|---:|
| LONG brut net | +7,696 % | — |
| Excès brut vs univers | +2,294 % | **[+0,884 % ; +3,406 %]** |
| Excès brut vs SPY | +1,194 % | [−1,198 % ; +3,903 %] |
| LONG couvert du bêta | +0,645 % | [−1,955 % ; +3,263 %] |
| LONG sector-neutral | +6,805 % | — |
| Excès sector-neutral vs univers | +1,402 % | **[+0,429 % ; +2,239 %]** |
| Sector-neutral + beta-hedged | **−0,238 %** | [−2,360 % ; +2,168 %] |

Le classement relatif reste positif après contrôle des secteurs. Il ne s’agit
donc pas seulement d’une surpondération des secteurs gagnants. Mais la
neutralisation du marché élimine l’essentiel du rendement économique.

## 6. Décomposition du marché

| Mesure | Résultat |
|---|---:|
| Bêta moyen TOP20 | 1,0210 |
| Bêta moyen sector-neutral | 1,0197 |
| Contribution moyenne estimée du marché | +6,990 % |
| Composante spécifique brute | +0,766 % |

Sur environ `+7,70 %` bruts par cohorte H120, près de `+6,99 points` sont
attribués à `bêta × rendement SPY`. Après coûts de la position et de la
couverture, le résidu moyen n’est plus que `+0,645 %`, avec un intervalle très
large autour de zéro.

Le terme « momentum résiduel » décrit la construction du signal. Il ne garantit
pas que le portefeuille finalement sélectionné soit lui-même beta-neutral.

## 7. Stabilité temporelle après attribution

| Bloc | Excès brut vs univers | Beta-hedged | Sector-neutral vs univers | Combiné |
|---|---:|---:|---:|---:|
| 2018H2–2020 | +3,179 % | +3,728 % | +1,917 % | +2,264 % |
| 2021–2022 | **−0,770 %** | **−2,308 %** | **−0,887 %** | **−2,180 %** |
| 2023–2025 | +3,564 % | −0,010 % | +2,474 % | **−1,068 %** |

Le bloc 2021–2022 reste négatif sous toutes les décompositions. Plus important,
la période récente conserve un bon classement relatif mais ne conserve plus de
rendement après couverture du marché. La reprise brute de 2023–2025 vient donc
en grande partie de l’exposition au marché.

## 8. Audit des quatre régimes figés

| Régime | Cohortes | Excès brut vs univers | Combiné | IC95 combiné |
|---|---:|---:|---:|---:|
| Bull / calme | 57 | +2,904 % | −0,070 % | [−2,673 % ; +3,184 %] |
| Bull / stressé | 14 | +1,424 % | **−2,045 %** | **[−2,439 % ; −0,870 %]** |
| Bear / calme | 6 | +0,121 % | −1,895 % | preuve insuffisante |
| Bear / stressé | 18 | +1,763 % | +1,187 % | [−1,736 % ; +4,821 %] |

Deux observations sont intéressantes mais non actionnables :

- bull/stressé est clairement défavorable après neutralisation ;
- bear/stressé est positif en moyenne, mais son IC95 recouvre zéro.

Aucun régime ne remplit simultanément le minimum de cohortes, un IC95 positif
et une réplication dans deux blocs temporels. Il n’existe donc pas de base pour
activer un filtre de régime.

## 9. Règles de classification

Le protocole prévoyait :

- `STRUCTURAL_SELECTION_CANDIDATE` si l’excès sector-neutral et le rendement
  combiné ont un IC95 positif dans tous les blocs ;
- `REGIME_DEPENDENT_CANDIDATE` si un état fixé possède un IC95 positif et se
  répète dans au moins deux blocs ;
- `MARKET_OR_SECTOR_EXPOSURE` si l’excès brut est significatif mais disparaît
  après les neutralisations ;
- `NO_STABLE_ALPHA` sinon.

E18-A appartient à la troisième catégorie.

## 10. Conclusion fonctionnelle

E18-A permet de fermer trois interprétations trop optimistes :

1. le rendement de `+7,696 %` n’est pas un alpha spécifique de même taille ;
2. neutraliser uniquement les secteurs ne suffit pas ;
3. les quatre régimes price-only simples ne fournissent pas une règle de
   déploiement reproductible.

Le momentum résiduel H120 peut rester un score auxiliaire de classement relatif,
mais il ne doit pas devenir une stratégie autonome ni être présenté comme une
solution directionnelle D1/D10.

## 11. Action suivante autorisée

Il ne faut pas optimiser de nouveaux seuils SMA ou volatilité sur ce rapport.
La prochaine recherche doit changer de source d’information économique :

- alpha fondamental/qualité/valorisation PIT indépendant ; ou
- signal spécifiquement conçu pour la baisse et les contraintes short ; ou
- combinaison multi-alpha pré-enregistrée où le momentum résiduel n’est qu’une
  composante de classement.

## 12. Reproductibilité

```powershell
.\.venv\Scripts\python.exe -u -m modelFactory.directional_alpha_attribution --log-level INFO
```

Artefact canonique :

```text
artifacts/research/directional_alpha_attribution/e18a-attribution-20260911201902/
├── report.json
└── attribution_cohorts.csv
```

Implémentation : `modelFactory/directional_alpha_attribution.py`.

Tests : `tests/test_directional_alpha_attribution.py`.


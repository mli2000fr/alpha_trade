# E19-A — Audit de disponibilité PIT des fondamentaux

## 1. Verdict

E19-A conclut **`PARTIAL_CONTRACT_BLOCKED`**.

La couverture SEC EDGAR est suffisamment riche pour poursuivre la piste sur le
plan des données. En revanche, le loader ML actuel ne fournit pas encore les
garanties nécessaires pour entraîner une bibliothèque d’alphas fondamentaux
PIT sans ambiguïté.

```text
données comptables disponibles          → OUI
couverture quotidienne suffisante       → OUI
contrat de disponibilité conservateur   → NON
identité/version de chaque dépôt         → NON
sélection fournisseur déterministe      → NON
valeurs manquantes préservées            → NON
entraînement E19-B autorisé              → NON
```

E19-A n’a modifié ni la table, ni le loader, ni le training.

## 2. Population auditée

| Élément | Valeur |
|---|---:|
| Univers | `univers_filtred_equities.txt` |
| Symboles demandés | 1 798 |
| Période | 2018-01-01 au 2025-12-31 |
| Symboles tradables présents dans le panel | 1 710 |
| Lignes quotidiennes tradables | 2 369 379 |
| Lignes SEC dans la période | 45 132 |
| Symboles avec SEC dans la période | 1 621 |
| Couverture symboles SEC | 90,16 % |

Le panel quotidien commence effectivement en juillet 2018 parce qu’E19-A
réutilise les dates et l’éligibilité de l’artefact E17. L’intitulé 2018 couvre
donc seulement le second semestre pour les statistiques quotidiennes.

## 3. Sources réellement présentes

La table complète contient 203 642 lignes et 5 942 symboles :

| Source | Lignes | Symboles | Période |
|---|---:|---:|---|
| SEC_EDGAR | 196 406 | 5 717 | 2009-04-15 → 2026-09-08 |
| Finnhub | 3 649 | 1 858 | 2026-09-09 → 2026-09-11 |
| Yahoo Finance | 3 581 | 1 827 | 2026-09-09 → 2026-09-11 |
| FMP | 6 | 6 | 2026-09-09 |

Sur l’univers E19 et jusqu’au 31 décembre 2025, toutes les lignes historiques
chargées sont `SEC_EDGAR`. Yahoo, Finnhub et FMP sont uniquement des snapshots
récents ; ils ne peuvent pas reconstruire 2018–2025.

La migration 0073 protège correctement l’identité physique
`(symbol, trade_date, source)` : aucun doublon au sein d’une source n’existe.
La table complète contient toutefois 3 577 couples symbole/date avec plusieurs
fournisseurs. Le loader doit donc fixer une priorité explicite avant tout usage
prospectif.

## 4. Règle PIT reconstruite par l’audit

Pour E19-A, une ligne SEC déposée à la date civile F devient disponible à la
première séance observée strictement postérieure :

```text
SEC filed_date = vendredi 5 janvier
        ↓
available_date = lundi 8 janvier
```

Cette règle J+1 est volontairement conservatrice. `companyfacts` fournit la
date du dépôt mais le pipeline ne conserve pas l’heure d’acceptation ; utiliser
la donnée au close du même jour pourrait donc lire un dépôt publié après la
clôture.

La reconstruction utilise exclusivement `SEC_EDGAR`, sélectionne le dernier
dépôt disponible à J et conserve les valeurs manquantes. Une information est
considérée fraîche pendant 180 jours pour le gate principal.

## 5. Couverture quotidienne PIT

Après application de J+1 et d’une fraîcheur maximale de 180 jours :

- 89,57 % des lignes tradables possèdent au moins une donnée comptable fraîche ;
- l’âge médian est 50 jours ;
- le P90 est proche de 104 jours sur l’ensemble de la période ;
- 94,55 % des lignes ayant déjà une comptabilité ont un âge ≤ 180 jours ;
- 99,09 % ont un âge ≤ 365 jours.

### 5.1 Par année

| Année | Lignes tradables | Symboles | Comptabilité fraîche | Âge médian | P90 |
|---|---:|---:|---:|---:|---:|
| 2018H2 | 136 585 | 1 232 | 89,90 % | 51 j | 92 j |
| 2019 | 274 833 | 1 303 | 89,99 % | 49 j | 99 j |
| 2020 | 282 440 | 1 385 | 89,57 % | 50 j | 102 j |
| 2021 | 314 397 | 1 489 | 89,24 % | 50 j | 103 j |
| 2022 | 326 053 | 1 512 | 88,67 % | 50 j | 105 j |
| 2023 | 325 289 | 1 521 | 89,70 % | 50 j | 106 j |
| 2024 | 350 282 | 1 589 | 89,77 % | 50 j | 105 j |
| 2025 | 359 500 | 1 630 | 89,89 % | 50 j | 104 j |

La stabilité annuelle est bonne. Le problème principal n’est pas une disparition
de la couverture sur une période particulière.

## 6. Couverture des features

La couverture quotidienne ci-dessous exige simultanément une ligne SEC
disponible en J+1, un âge ≤ 180 jours et une valeur non nulle.

### 6.1 Comptabilité exploitable

| Feature | Lignes de dépôt non nulles | Symboles | Couverture quotidienne fraîche |
|---|---:|---:|---:|
| ROA | 95,94 % | 1 492 | 85,60 % |
| ROE | 90,81 % | 1 460 | 81,40 % |
| EPS | 86,77 % | 1 408 | 77,51 % |
| Book value/share | 86,55 % | 1 361 | 77,44 % |
| Net margin | 83,36 % | 1 384 | 77,41 % |
| Revenue | 83,29 % | 1 384 | 76,81 % |
| Revenue growth YoY | 80,07 % | 1 360 | 74,73 % |
| EPS growth YoY | 82,49 % | 1 397 | 74,53 % |
| Current ratio | 73,62 % | 1 133 | 67,76 % |
| EBITDA | 72,50 % | 1 172 | 66,14 % |
| Debt/equity déclaré | 72,42 % | 1 190 | 63,31 % |
| Operating margin | 67,52 % | 1 160 | 62,56 % |
| Gross margin | 39,05 % | 716 | 35,89 % |

Le noyau ROA/ROE/marges/croissance/revenue est suffisamment couvert. La marge
brute ne doit pas devenir une feature obligatoire sur tout l’univers.

### 6.2 Ratios dérivés du marché

| Feature | Couverture quotidienne fraîche |
|---|---:|
| Beta | 88,88 % |
| Market cap | 83,44 % |
| PB | 76,53 % |
| PS | 73,85 % |
| PE | 67,85 % |
| EV/EBITDA | 53,66 % |
| Dividend yield | 36,89 % |

Les ratios de marché doivent être recalculés avec le prix PIT à J lorsque cela
est possible. Ils ne doivent pas être confondus avec les valeurs comptables du
dépôt.

### 6.3 Features indisponibles

Les quatre champs suivants ont zéro observation SEC sur 2018–2025 :

- `forward_pe` ;
- `peg_ratio` ;
- `eps_estimate_current` ;
- `eps_estimate_next`.

Ils doivent être exclus d’E19-B. Leur remplacement actuel par `-1` ou `0` ne
crée aucune information économique et peut seulement apprendre le fournisseur
ou l’absence de donnée.

## 7. Défauts du contrat applicatif actuel

### 7.1 Disponibilité le jour du dépôt

`trade_date` contient la date SEC `filed`. Le loader forward-fill à partir de
cette même date. Sans heure d’acceptation, cette convention n’est pas assez
conservatrice pour une décision au close J. E19-A utilise J+1 ; le loader de
production ne le fait pas.

### 7.2 Identité fiscale et versions absentes

La table ne conserve pas :

- `fiscal_period_end` ;
- le formulaire `10-Q`, `10-K` ou amendement ;
- `accession_number`.

Tous les historiques ont été téléchargés en 2026. Sans ces champs, il est
impossible de prouver quelle version d’une valeur appartenait à quel dépôt,
d’auditer une restatement ou de rejouer proprement un amendement.

### 7.3 Fournisseur non sélectionné

`load_fundamentals_from_db()` ne sélectionne ni `source` ni `fetched_at`, malgré
sa documentation. À partir de 2026, plusieurs lignes peuvent exister pour le
même symbole et la même date. Le `pivot_table(..., aggfunc="last")` ne définit
aucune priorité fournisseur stable.

### 7.4 Prédécesseur antérieur au début non chargé

Le loader requête `trade_date >= start_date`. Il ne récupère pas la dernière
publication connue avant le début demandé. Une période d’entraînement commence
donc avec des valeurs manquantes artificielles jusqu’au dépôt suivant.

Ce défaut ne crée pas de fuite future, mais dégrade et rend instable la
couverture au bord gauche.

### 7.5 Valeurs manquantes transformées en constantes

Les fondamentaux absents sont remplacés par des valeurs dites neutres : PE à
`-1`, ROE à `0`, current ratio à `1`, bêta à `1`, etc. Cela empêche de distinguer
une vraie valeur économique de l’absence de donnée.

E19-B doit conserver NaN et ajouter, si nécessaire, des indicateurs explicites
de disponibilité.

## 8. Risques sémantiques détectés dans le code

| Nom exposé | Calcul réel | Risque |
|---|---|---|
| `debt_to_equity` | total liabilities / equity | ce n’est pas la dette financière/equity |
| `ebitda` | `OperatingIncomeLoss` prioritaire avant `EBITDA` | operating income peut être étiqueté EBITDA |
| `dividend_yield` | dividend/share stocké avant enrichissement prix | unité potentiellement ambiguë si enrichissement absent |
| `fund_estimate_revision` | estimate_next / estimate_current − 1 | comparaison de niveaux, pas révision temporelle |

Ces features ne doivent pas être utilisées sous leur nom actuel sans correction
ou renommage explicite.

## 9. Gates

| Gate | Résultat |
|---|---|
| Couverture symboles ≥ 80 % | PASS, 90,16 % |
| Comptabilité fraîche quotidienne ≥ 70 % | PASS, 89,57 % |
| Noyau de features ≥ 50 % | PASS |
| Identité fiscale/version complète | **FAIL** |
| Disponibilité conservatrice J+1 dans le loader | **FAIL** |
| Priorité fournisseur déterministe | **FAIL** |
| Valeurs manquantes préservées | **FAIL** |
| Publication antérieure au début chargée | **FAIL** |
| Aucun doublon dans une même source | PASS |

Les données passent les gates de couverture, mais cinq gates contractuels
échouent. Le verdict est donc `PARTIAL_CONTRACT_BLOCKED` et
`training_authorized=false`.

## 10. Corrections requises avant E19-B

Ordre recommandé :

1. ajouter l’identité du dépôt : période fiscale, formulaire, accession et date
   de disponibilité ;
2. conserver les amendements comme nouvelles versions au lieu de perdre leur
   chronologie ;
3. appliquer une disponibilité conservatrice à la séance suivante ;
4. rendre la sélection fournisseur explicite — SEC pour l’historique comptable,
   snapshots Yahoo/Finnhub seulement à partir de leur collecte ;
5. charger le dernier dépôt antérieur au début de la fenêtre ;
6. préserver NaN et produire des masques de disponibilité ;
7. corriger ou renommer dette/equity, EBITDA, dividend yield et estimate
   revision ;
8. exclure les quatre features forward totalement absentes.

Après ces corrections, il faudra rejouer E19-A. E19-B ne sera autorisée que si
le rapport devient `DATA_READY`.

## 11. Reproductibilité

```powershell
.\.venv\Scripts\python.exe -u -m modelFactory.fundamental_pit_availability_audit --log-level INFO
```

Artefact canonique :

```text
artifacts/research/fundamental_pit_availability/e19a-fundamental-pit-audit-20260911203804/
├── report.json
├── feature_coverage.csv
├── yearly_coverage.csv
└── daily_availability.parquet
```

Implémentation : `modelFactory/fundamental_pit_availability_audit.py`.

Tests : `tests/test_fundamental_pit_availability_audit.py`.

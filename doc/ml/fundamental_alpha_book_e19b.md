# E19-B — Bibliothèque d’alphas fondamentaux PIT

## 1. Pré-enregistrement

Ce protocole est figé avant le premier calcul de performance E19-B. Toute
variante ultérieure devra recevoir un identifiant distinct et ne remplacera pas
ce résultat.

## 2. Hypothèse

Des caractéristiques comptables connues au plus tard à la date de décision
contiennent une information directionnelle lente, distincte du prix : les
entreprises de meilleure qualité, moins chères, en croissance, moins endettées
et dont les fondamentaux s’améliorent doivent surperformer les entreprises
opposées après neutralisation des expositions secteur et taille.

L’expérience ne cherche pas à expliquer ou réparer l’Oracle. Elle teste une
bibliothèque indépendante, susceptible de devenir ensuite une confirmation ou
une source d’alpha autonome seulement si elle passe les gates OOS.

## 3. Population et contrat PIT

- univers : `config/univers/univers_filtred_equities.txt` ;
- période : 2018-07-01 au 2025-12-31 ;
- source historique autorisée : `SEC_EDGAR` ;
- disponibilité : séance strictement postérieure au dépôt SEC ;
- fraîcheur maximale d’une observation comptable : 180 jours civils ;
- observation antérieure au début de fenêtre conservée comme prédécesseur ;
- entrée : open ajusté J+1 ;
- sorties de mesure : open ajusté J+21, J+61 et J+121 ;
- H60 primaire, H120 confirmation, H20 diagnostic ;
- univers de marché : actions éligibles, historique ≥252 séances, prix ≥10 USD,
  volume moyen 20 jours ≥50 000 et ADV20 ≥10 MUSD ;
- aucune donnée forward analyst (`forward_pe`, `peg_ratio`, estimations EPS),
  car leur couverture SEC est nulle ;
- aucune imputation sémantique : une composante absente ne participe pas au
  score ; un nombre minimum de composantes observées est exigé.

L’univers et les secteurs reposent encore sur des snapshots actuels : le biais
de survivance résiduel est déclaré et interdit toute promotion directe.

## 4. Familles pré-enregistrées

Les signes économiques sont fixés avant évaluation :

| Famille | Composantes | Signe favorable |
|---|---|---|
| qualité | ROA, ROE, marges nette/opérationnelle/brute, current ratio | élevé |
| valeur | PE, PB, PS, EV/EBITDA | faible ; ratios non positifs exclus |
| croissance | croissance YoY EPS et chiffre d’affaires | élevée |
| levier | dette financière/equity | faible ; valeurs négatives exclues |
| amélioration | variations depuis le dépôt précédent de ROA, ROE, marges et croissances | hausse |

Chaque composante est winsorisée transversalement aux percentiles 1/99, puis
convertie en rang. Les composites de famille sont équipondérés. Le composite
global est la moyenne équipondérée des familles disponibles, avec au moins
trois familles observées.

## 5. Neutralisations

Trois vues sont calculées sans changer les signes :

1. `raw` : rang transversal brut ;
2. `sector_neutral` : résidu après retrait des effets secteur ;
3. `sector_size_neutral` : résidu d’une régression quotidienne sur les
   indicatrices secteur et `log(market_cap)` PIT.

Les résidus sont centrés-réduits transversalement par date. Cette
transformation affine conserve leur orthogonalité à la taille et aux secteurs ;
un nouveau classement en rangs après régression la réintroduirait.

La vue principale et seule éligible aux gates est `sector_size_neutral`. Les
deux autres servent à attribuer un éventuel résultat au facteur fondamental ou
à une exposition secteur/taille.

## 6. Walk-Forward et portefeuilles

Les scores sont des formules fixes, sans apprentissage sur le futur. Pour rendre
la validation temporelle explicite, les observations sont néanmoins découpées
en fenêtres Walk-Forward : 504 séances initiales, tests de 252 séances, pas de
252 séances, maximum 8 folds. Seules les fenêtres de test composent le résultat
OOF.

Tous les 20 jours de bourse, chaque score forme :

- LONG : top 20 %, équipondéré ;
- SHORT : bottom 20 %, rendement inversé ;
- LONG/SHORT : 50 % LONG + 50 % SHORT, dollar-neutral ;
- minimum 10 titres par jambe ;
- coût aller-retour : 6 bps par jambe ; frais d’emprunt indisponibles et donc
  explicitement absents.

Les cibles principales sont les rendements absolus des jambes et le rendement
excédentaire à SPY pour l’IC transversal.

## 7. Métriques

Pour chaque famille, vue et horizon : IC de Spearman quotidien, intervalle de
confiance block-bootstrap 95 %, rendement net LONG, rendement net SHORT,
LONG/SHORT, intervalles 95 %, taux de folds et semestres positifs, stabilité
depuis 2023, taille des jambes et concentration temporelle.

## 8. Gates pré-enregistrés

Le composite global `sector_size_neutral` à H60 doit satisfaire :

- IC moyen > 0 et borne basse IC95 > 0 ;
- LONG/SHORT net > 0 et borne basse IC95 du rendement > 0 ;
- au moins 70 % des folds et 70 % des semestres positifs ;
- résultat moyen depuis 2023 positif ;
- au moins 50 cohortes ;
- confirmation H120 : IC > 0 et LONG/SHORT net > 0.

Verdicts de jambe séparés :

- `GO_LONG` seulement si LONG H60 net > 0, borne basse 95 % > 0 et au moins
  70 % des folds LONG positifs ;
- `GO_SHORT` selon les mêmes règles pour SHORT ;
- `GO_LONG_SHORT` selon les gates du composite ci-dessus.

Un signal ne passant que H20, une seule sous-période ou une vue non neutralisée
reste `NO_GO`. Aucun seuil ne sera ajusté sur les résultats de cette exécution.

## 9. Résultats du run canonique

Run : `fundamental-alpha-book-20260912112042`.

Population réellement évaluée : 1 798 actions, 3 333 794 observations
quotidiennes, 2 369 360 observations éligibles au marché, 2 122 341 avec un
fondamental frais et 2 259 763 observations dans cinq folds OOF. Les tests OOF
couvrent 1 260 séances et 63 cohortes de rebalancement. Les expositions
résiduelles du composite à la taille et aux secteurs sont inférieures à
`5e-15` : la neutralisation est effective numériquement.

### Composite pré-enregistré, secteur + taille neutralisés

| Horizon | IC moyen [borne 95 %] | LONG net [borne 95 %] | SHORT net | LONG/SHORT net [borne 95 %] |
|---|---:|---:|---:|---:|
| H20 | +0,40 % [+0,05 %] | +1,08 % [-0,16 %] | -1,14 % | -0,03 % [-0,18 %] |
| H60 | +0,46 % [+0,07 %] | +3,25 % [+0,22 %] | -3,32 % | -0,03 % [-0,36 %] |
| H120 | +1,44 % [+1,02 %] | +6,50 % [+0,01 %] | -6,18 % | +0,16 % [-0,26 %] |

Le verdict mécanique pré-enregistré est `GO_LONG`, `NO_GO_SHORT` et
`NO_GO_LONG_SHORT`. Le `GO_LONG` doit cependant être interprété avec prudence :
il porte sur le rendement absolu du panier dans un marché globalement haussier.
Le contrôle d’attribution post-hoc contre SPY donne à H60 `-0,09 %` d’excès
LONG par cohorte ; le composite ne démontre donc pas un alpha LONG autonome.
Son spread LONG/SHORT est nul et devient négatif depuis 2023 (`-0,28 %` à
H60). Le verdict scientifique retenu pour le composite est par conséquent
`NO_GO_COMPOSITE` et aucune promotion serving n’est autorisée.

### Attribution par famille

La valeur est la seule famille nettement prometteuse après neutralisation :

- H60 : IC `+4,47 %`, borne basse 95 % `+3,31 %`, LONG/SHORT net `+1,00 %`,
  borne basse `+0,06 %`, 80 % des folds et 80 % des semestres positifs ;
- H120 : IC `+6,58 %`, borne basse `+4,97 %`, LONG/SHORT net `+2,18 %`,
  borne basse `+0,33 %`, 100 % des folds et 70 % des semestres positifs ;
- depuis 2023 : LONG/SHORT `+0,11 %` à H60 et `+0,62 %` à H120 ;
- contrôle contre SPY : jambe LONG `+0,76 %` et jambe SHORT relative
  `+1,24 %` à H60 ; à H120, respectivement `+1,26 %` et `+3,10 %`.

La jambe SHORT absolue de la valeur reste perdante (`-2,11 %` à H60) : les
titres décotés faibles sous-performent le marché, mais ne baissent pas assez
pour constituer seuls une stratégie short. Qualité, croissance et faible
levier n’apportent pas de spread robuste dans cette formulation ; amélioration
est positive en IC mais trop faible économiquement. Leur moyenne équipondérée
dilue donc le facteur valeur.

La prochaine action autorisée est une E19-C pré-enregistrée de confirmation de
la famille valeur seule sur sous-périodes/univers verrouillés, avec comparaison
explicite à SPY et à l’univers. Il est interdit d’optimiser rétrospectivement
les quatre ratios, les poids ou les seuils sur ce run.

## 10. Sorties produites

- `report.json` : contrat, métriques, gates et verdicts ;
- `alpha_panel.parquet` : scores et cibles auditables ;
- `daily_ic.csv` ;
- `portfolio_cohorts.csv` ;
- `fold_metrics.csv`.

Artefact canonique :
`artifacts/research/fundamental_alpha_book/fundamental-alpha-book-20260912112042`.

L’expérience est `research_only`; elle ne modifie ni modèle, ni prédiction, ni
backtest, ni serving.

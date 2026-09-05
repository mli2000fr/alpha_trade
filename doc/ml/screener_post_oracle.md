# Filtre screener PIT après Oracle Extreme

## Statut

Cette fonctionnalité est un **harnais de recherche uniquement**. Elle ne modifie
ni la prédiction, ni la cascade, ni le backtest, ni le serving. Une relation
descriptive ou un résultat de développement ne constitue jamais une règle de
production.

Code source : `modelFactory/screener_post_oracle.py`.

Tests : `tests/test_screener_post_oracle.py`.

## Question étudiée

Oracle Extreme détecte une probabilité de mouvement important, sans en connaître
le sens. L’étude cherche si les informations historiques du screener, disponibles
à la date de décision, peuvent ensuite :

- enrichir les vrais événements haussiers pour une branche LONG ;
- enrichir les vrais événements baissiers pour une branche SHORT ;
- ou servir uniquement de filtre d’abstention.

Le flux expérimental est :

```text
univers historique
    -> prédictions Oracle strictement OOF
    -> TOP20 % quotidien selon le percentile Oracle
    -> dernier snapshot screener disponible en PIT
    -> règle LONG ou SHORT indépendante
    -> mesure du rendement futur H3, H10 ou H20
```

## Population Oracle

La source est obligatoirement le fichier `_oracle_oof_gate.parquet` du batch
Oracle. Le percentile quotidien `directional_oracle_extreme_pct` est recalculé
avec `pool_pct`; le score Oracle n’est jamais utilisé comme variable screener.

Pour le batch `model-factory-20260904192500-0802c8`, le cache réellement
disponible couvre le 5 juillet 2018 au 11 juillet 2025. Une date demandée en
dehors de cet intervalle ne crée pas artificiellement de prédiction.

## Jointure PIT du screener

La source est `stock_scores_history`, limitée au profil
`capital_2001_5000`. La table contient un historique du 4 janvier 2010 au
25 juin 2026, mais il ne s’agit pas d’un panel dense de tout l’univers : elle
contient environ 10 à 74 lignes par date selon les années.

Pour chaque événement `(date, symbol)` :

1. normaliser le symbole et la date ;
2. rechercher le dernier `snapshot_date <= date` ;
3. ne jamais autoriser un snapshot futur ;
4. calculer son âge calendaire ;
5. déclarer le snapshot frais lorsque son âge est compris entre 0 et 7 jours ;
6. conserver les données périmées pour l’audit, mais les exclure des règles.

Lorsque plusieurs exécutions existent le même jour, la dernière valeur selon
`created_at` est retenue. Aucune valeur absente n’est remplacée par zéro. Cette
distinction est essentielle car certaines constructions de features de
l’application utilisent `0.0` comme valeur technique par défaut.

La date du snapshot est compatible avec une décision prise après la clôture et
une entrée au prochain open. Le harnais ne doit pas être réutilisé pour une
décision intraday avant la disponibilité du snapshot.

## Deux familles de données

### Signaux prédictifs audités

L’allowlist inclut notamment les scores de tendance, VCP, RSI, force relative,
position 52 semaines, volatilité, ATR, score final, short score, sentiment et
composants entreprise/macro/quant lorsque les colonnes existent réellement.

Les colonnes suivantes sont volontairement exclues tant que leur provenance OOF
n’est pas démontrée :

- `final_score_walk_forward` ;
- poids Walk-Forward sentiment/macro/quant ;
- identifiants et sources de calibration.

### Signaux de tradabilité

Liquidité, capitalisation, spread, earnings blackout, anomalies et jours
manquants sont audités séparément. Ils ne sont pas présentés comme preuve de
direction.

## Cibles

Trois horizons sont pré-enregistrés : H3, H10 et H20. Les événements restent
symétriques pour rendre les comparaisons lisibles :

```text
TRUE_LONG  = rendement brut futur >= +3 %
TRUE_SHORT = rendement brut futur <= -3 %
NEUTRAL    = rendement compris entre -3 % et +3 %
```

Le rendement brut est la cible primaire. Les rendements excess-SPY et résiduels
secteur sont conservés pour diagnostic.

### Contrôle corporate actions

L’audit initial a détecté des rendements manifestement impossibles, notamment
`WFRD` au-delà de +200 000 % en vingt jours fin 2019 et `CHRD` à plusieurs
dizaines de milliers de pourcents. Ces observations proviennent de séries
ajustées incohérentes autour de corporate actions.

Le harnais conserve les lignes et ajoute `target_quality_valid`, mais neutralise
les cibles dont le rendement absolu dépasse 10, soit 1 000 %. Ce plafond très
permissif conserve les mouvements réels exceptionnels observés dans les données,
par exemple GME à environ +434 % sur H3 et SMMT à environ +589 % sur H20.

Le nombre de labels invalidés est publié pour chaque horizon.

## Audit descriptif

`feature_coverage.csv` distingue :

- la couverture absolue dans tout le TOP20 Oracle ;
- la couverture parmi les seuls snapshots frais ;
- le taux de zéro parmi les valeurs réellement observées ;
- le nombre de valeurs distinctes ;
- les quantiles p01 à p99.

`feature_coverage_by_semester.csv` expose la dérive de couverture.

`reliability_bins.csv` découpe chaque feature en quintiles sur chaque horizon et
publie, globalement puis par semestre :

- support, dates et symboles ;
- rendement brut futur moyen, pondéré également par date ;
- probabilité de TRUE_LONG ;
- probabilité de TRUE_SHORT.

Cette phase est descriptive : ses quintiles ne deviennent pas des règles.

## Découverte Walk-Forward

Les splits sont faits en dates uniques afin qu’une même journée ne traverse
jamais deux partitions. La fin du train et de la validation est purgée selon
l’horizon : 3, 10 ou 20 séances.

Pour chaque feature et chaque côté :

1. le train calcule les quantiles 20, 40, 60 et 80 % ;
2. le train compare les orientations `valeur <= seuil` et `valeur >= seuil` ;
3. la précision directionnelle doit rester non négative pour départager les
   règles, puis le rendement signé est maximisé ;
4. la validation accepte ou rejette le seuil figé ;
5. le test évalue une seule fois le seuil sans le modifier.

La baseline est appariée sur les mêmes dates et la même population observable.
L’espérance d’un tirage aléatoire de même taille est alors la moyenne du pool de
ces dates.

## Gates de développement

LONG et SHORT reçoivent des verdicts séparés. Pour une feature et un horizon,
avec neuf folds disponibles, au moins sept doivent satisfaire chacun des gates :

- validation positive simultanément en rendement et précision ;
- lift de rendement positif sur test ;
- lift de précision positif sur test.

Les moyennes des lifts doivent également être positives. La règle doit conserver
au moins 20 % des lignes où la feature est observable et au moins 2 % de tout le
pool Oracle. Ce deuxième seuil empêche de promouvoir une règle spectaculaire
fondée sur quelques événements seulement.

Un succès de développement ne serait encore que
`CANDIDATE_DEVELOPMENT`; il exigerait une confirmation temporelle intacte avant
toute proposition d’intégration.

## Artefacts

Chaque campagne crée un répertoire autonome contenant :

- `campaign.json` : contrat, population, qualité des cibles et verdict ;
- `analytic_dataset.parquet` : événements, snapshots bruts et outcomes ;
- `feature_coverage.csv` ;
- `feature_coverage_by_semester.csv` ;
- `reliability_bins.csv` ;
- `snapshot_presence_summary.csv` ;
- `walk_forward_folds.csv` : seuil et métriques de chaque fold ;
- `rule_summary.csv` : gates agrégés ;
- `oos_rule_decisions.parquet` : acceptations/rejets OOS ligne par ligne.

## Reproduction

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.screener_post_oracle --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --horizons 3,10,20 --pool-pct 0.20 --capital-preset-key capital_2001_5000 --max-snapshot-age-days 7 --quantile-bins 5 --min-feature-coverage 0.50 --min-rule-retention 0.20 --min-effective-retention 0.02 --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --target-up-threshold 0.03 --target-down-threshold -0.03 --max-abs-future-return 10.0 --artifacts-root artifacts/models/screener_post_oracle --log-level INFO
```

## Règle d’intégration

Aucun résultat de ce harnais n’est automatiquement consommé par l’application.
Une intégration future exigerait un GO explicite, un mode désactivé par défaut,
la persistance des valeurs et timestamps utilisés, des tests PIT, puis un
backtest OOS sans modification simultanée du lifecycle.

## Résultat de la campagne du 5 septembre 2026

Artefact canonique :
`artifacts/models/screener_post_oracle/screener-post-oracle-20260905122039-0802c8`.

### Contrôles techniques

- période OOF effective : 5 juillet 2018 au 11 juillet 2025 ;
- 127 256 événements Oracle TOP20, 1 764 dates et 268 symboles ;
- 28 features prédictives suffisamment renseignées parmi les snapshots frais ;
- 9 folds OOS pour chacun de H3, H10 et H20 ;
- 258 768 décisions OOS uniques, 57 colonnes booléennes de décision ;
- aucun doublon `(horizon, fold, date, symbol)` ;
- 6 labels H3, 21 labels H10 et 43 labels H20 invalidés pour rendement
  absolu supérieur à 1 000 % ;
- 15 tests ciblés réussis avec le ranker conditionnel inclus ;
- aucune écriture en base et aucune modification du serving.

### Limite structurelle de couverture

Un snapshot historique existe antérieurement pour 83,14 % des événements, mais
seulement 10,44 % disposent d’un snapshot âgé de sept jours ou moins. La
couverture varie très fortement : 17,79 % en 2021H1, 0,71 % en 2022H2,
15,60 % en 2024H1 et 12,98 % en 2025H1. Cette discontinuité interdit de traiter
les valeurs screener comme un panel quotidien homogène.

La simple présence d’un snapshot frais ne constitue pas un bon filtre :

| Horizon | Lift rendement LONG | Lift précision LONG | Lift rendement SHORT | Lift précision SHORT |
|---|---:|---:|---:|---:|
| H3 | -0,10 pt | -2,39 pts | +0,10 pt | -4,38 pts |
| H10 | -0,52 pt | -0,35 pt | +0,52 pt | -2,58 pts |
| H20 | -1,02 pt | -0,51 pt | +1,02 pt | -1,00 pt |

Le lift de rendement SHORT positif signifie seulement que les titres présents
montent moins que tout le pool. Leur rendement signé reste négatif et leur
précision des vraies baisses diminue : ce n’est pas un signal SHORT exploitable.

### Meilleurs signaux, mais gates non franchis

Les chiffres ci-dessous sont des moyennes OOS appariées et non des règles à
utiliser :

- H3 LONG, force relative : +0,31 point de rendement, +3,98 points de précision,
  mais seulement 6/9 folds positifs et 2/9 validations ; couverture effective
  1,74 % ;
- H3 LONG, proximité du plus haut 52 semaines : +0,28 point, +1,29 point de
  précision, 6/9 folds rendement et 7/9 précision, mais 2/9 validations ;
- H3 SHORT, score final faible : +0,49 point de rendement signé et +2,19 points
  de précision, mais seulement 4/9 validations et 6/9 folds de précision ;
- H10 LONG, force relative élevée : +0,70 point et +1,79 point de précision,
  mais 2/9 validations et couverture effective 1,74 % ;
- H10 LONG, proximité du plus haut : +0,36 point et +1,12 point, avec 7/9 folds
  rendement, mais 5/9 validations et 6/9 folds précision ;
- H20 LONG, `historical_range_score` : +0,49 point et +1,84 point, mais seulement
  3/9 validations ;
- H20 SHORT, ATR faible : +0,98 point et +5,38 points de précision en moyenne,
  mais seulement 4/9 folds positifs, 1/9 validation et 1,47 % de couverture
  effective.

Certaines relations descriptives sont intuitives : force relative élevée pour
LONG, score final/RSI faibles pour SHORT, ou ATR faible pour SHORT à H10/H20.
Elles changent toutefois de force selon les périodes. Aucun signal n’atteint les
sept folds requis simultanément sur validation, rendement et précision.

### Verdict

```text
GO_TRADABILITY = NON démontré
GO_LONG_RULE    = NON
GO_SHORT_RULE   = NON
VERDICT GLOBAL  = NO_GO_PREDICTIVE
```

Aucune combinaison à deux ou trois règles n’a été testée : le protocole
interdisait cette étape lorsqu’aucun signal univarié ne survivait. Tester des
combinaisons maintenant multiplierait les degrés de liberté et favoriserait le
surapprentissage. Aucune confirmation supplémentaire n’est nécessaire en
l’absence de candidat de développement.


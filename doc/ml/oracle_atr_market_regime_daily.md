# Étude quotidienne Oracle × ATR et régime de marché

## À quoi sert cette table ?

`alpha_trade.oracle_atr_market_regime_daily` rapproche les indicateurs macro du
jour et les résultats futurs de la sélection **Oracle TOP20 ∩ ATR TOP20**.
Elle permet d’étudier les jours/régimes où les candidats deviennent plus souvent
D1 ou D10. Ce n’est ni une table de signaux de production, ni un backtest de
portefeuille. Un pourcentage D10 élevé ne mesure pas un profit net.

L’écran **Régime Marché** propose le bloc « Alimenter l’étude Oracle × ATR et
régime de marché ». Le service de référence est
`service/market/oracle_atr_study.py`. Aucun entraînement ni téléchargement n’est
effectué. Seule la nouvelle table d’agrégats est écrite ; les modèles, barres,
macros, labels et prédictions existants ne sont pas modifiés.

## Utilisation dans l’IHM

1. Ouvrir **Régime Marché**, avec la base US `alpha_trade`.
2. Choisir les dates. Valeurs initiales : `2020-01-01` à `2026-09-30`.
3. Choisir un fichier d’univers dans `config/univers/`, comme dans Pipeline.
4. Choisir le batch Oracle. Seuls les batches ayant des scores persistés et un
   horizon identifiable dans leurs artefacts sont proposés ; le libellé affiche
   cet horizon. L’horizon est imposé par l’artefact, pas saisi arbitrairement.
5. Copier la commande affichée, ou cliquer **Alimenter l’étude Oracle × ATR**.
6. Examiner le nombre de séances complètes/incomplètes et le tableau de détail.

Le traitement se fait par tranches de **20 séances par défaut**, taille réglable
dans l’écran ou par `--date-batch-size`. Prix, scores et labels sont chargés pour
chaque tranche, puis celle-ci est enregistrée dans sa propre transaction. Une
progression indique la tranche en calcul puis sa confirmation de persistance.
Un échec ultérieur conserve les tranches précédentes ; seule la tranche non
validée doit être refaite.
Ne pas lancer plusieurs alimentations identiques en parallèle : cela n’apporte
aucun bénéfice. Par défaut, une relance saute les séances déjà `COMPLETE` pour la
même identité et version de calcul ; elle recalcule les séances absentes ou
`INCOMPLETE`. Ces dernières peuvent donc être réexaminées à chaque relance tant
que leurs données manquent. Le compteur des séances ignorées est affiché.

Après une correction des prix, macros, prédictions ou labels, cocher
**Recalculer aussi les séances déjà complètes**, ou ajouter `--no-resume` dans la
CLI. Sans cette option, une ligne complète est conservée même si sa source a
été corrigée depuis. La reprise n’est pas une détection automatique de changements
dans les sources. Aucun changement de schéma SQL n’est nécessaire.

Exemple de commande, à remplacer par un batch et un fichier réellement présents :

```powershell
python -u -m service.market.oracle_atr_study --batch-id <batch_oracle> --symbol-source universe-file:univers_filtred_tradable.txt --start-date 2020-01-01 --end-date 2026-09-30 --artifacts-dir artifacts/models
```

## Préconditions et données absentes

- Migration **0089** ou exécution du SQL de création
  `database/sql/ml/oracle_atr_market_regime_daily.sql`.
- Scores du batch dans `oracle_extreme_predictions`, sur la période souhaitée.
- Barres ajustées dans `stock_bars_daily`, avec au moins 21 barres valides avant
  les journées à évaluer. La lecture remonte 90 jours avant le début.
- Macros et `mode` dans `stock_macro_indicators_daily`.
- Labels réels dans `global_oracle_labels`, pour **le même batch et son horizon**.

Le service ne lance pas automatiquement une prédiction ni une reconstruction des
labels, car ces actions ont leur propre contrat d’univers et de qualité. Les
labels peuvent être préparés depuis Diagnostic ML ou le constructeur existant
`python -m modelFactory.oracle.build_labels --batch-id <batch> --horizon <H>
--start-date <début> --end-date <fin>`. Vérifier son univers de référence avant
de l’exécuter ; ne pas reconstruire les déciles seulement sur les candidats.

Les dates demandées ne créent pas les données sous-jacentes manquantes. Chaque
séance NYSE est conservée, même si ses scores/macros manquent. Les week-ends et
jours de fermeture n’ont pas de ligne. Un calendrier NYSE fiable est requis ;
le service refuse un calendrier de remplacement « lundi à vendredi ».

## Identité et absence de doublons

La clé primaire est :

```text
trade_date + universe_hash + oracle_batch_id + oracle_horizon
```

`universe_hash` est le SHA-256 de la liste normalisée, dédupliquée et triée des
symboles du fichier. `universe_source` conserve l’identifiant lisible du fichier.
Modifier ses symboles crée une nouvelle étude, sans écraser l’ancienne. Renommer
un fichier à contenu identique ne duplique pas l’étude ; la source lisible est
mise à jour. Un autre batch/horizon conserve des lignes distinctes.

L’upsert actualise toutes les mesures, y compris les `NULL` et le statut : des
résultats devenus invalides ne restent donc pas artificiellement renseignés.
`created_at` est la création initiale ; `updated_at` est la dernière mise à jour.

## Définition de la sélection et des pourcentages

Pour chaque J :

1. Restreindre les scores Oracle du batch aux symboles du fichier choisi.
2. Calculer les percentiles Oracle sur les scores finis disponibles ce jour.
3. Calculer ATR20/prix ajusté à J sur cette même population, avec le
   [module partagé backtest/live](oracle_atr_amplitude_gate.md).
4. Conserver les titres avec percentile Oracle ≥ 0,80 **et** percentile ATR ≥ 0,80.
5. Raccorder les labels réels qualifiés de ces titres.

Le classement ATR utilise les ATR valides ; les absents sont exclus. Les ex æquo
et seuils inclusifs peuvent donner une proportion différente de 20 % exactement.
Cette étude impose les deux TOP20 et n’utilise pas le booléen d’activation de
production : elle mesure toujours l’intersection demandée.

**La classe D1/D10 réelle n’est pas recalculée sur l’intersection**, ni sur le
fichier choisi. Elle provient de l’univers de référence des labels du batch.
D1 = décile inférieur des rendements futurs ; D10 = décile supérieur.
Comparer deux batches dont les univers de labels diffèrent demande de vérifier
ces univers. L’étude ne simule pas les filtres tradable PIT, Per-Symbol ou risque
du backtest ; elle n’est donc pas sa reproduction intégrale.

Un candidat est évalué si `target_quality_valid=1`, le rendement futur et le
décile sont renseignés, et `oracle_available_date` est connue et au plus égale
à la date actuelle d’évaluation (Europe/Paris).

```text
d1_pct  = 100 × d1_count  / evaluated_count
d10_pct = 100 × d10_count / evaluated_count
d10_d1_ratio = d10_pct / d1_pct = d10_count / d1_count
d1_d10_total_pct = d1_pct + d10_pct = 100 × (d1_count + d10_count) / evaluated_count
evaluation_coverage_pct = 100 × evaluated_count / intersection_count
```

Les pourcentages sont exprimés de 0 à 100, pas de 0 à 1. Zéro candidat évaluable
donne `NULL`, **pas 0 %**. Un résultat partiel peut être calculé sur les candidats
connus mais reste `INCOMPLETE`. Il faut lire sa couverture avant de l’interpréter.

Le ratio `d10_d1_ratio` n’est pas un pourcentage : D10=25 % et D1=20 %
donnent **1,25**. Supérieur à 1 : davantage de D10 que de D1 ; inférieur à 1 :
davantage de D1 ; égal à 1 : mêmes effectifs. Si D1 est nul ou aucun candidat
n’est évaluable, le ratio est `NULL` (pas infini). Si D10 est nul et D1 positif,
il vaut 0. Il conserve les réserves de couverture des pourcentages sources.

`d1_d10_total_pct` mesure la proportion totale de vrais extrêmes D1 ou D10
parmi les candidats évalués : 20 % + 25 % = **45 %**. Si aucun candidat n’est
évaluable, cette somme est `NULL` ; si des candidats sont évaluables mais aucun
n’est D1/D10, elle vaut 0 %. Elle mesure l’amplitude, pas la direction.
La migration **0091** ajoute et remplit cette colonne à partir des effectifs
existants, sans recalcul historique. Le SQL manuel associé est
`database/sql/ml/oracle_atr_market_regime_daily_total_migration.sql`.

La migration **0090** ajoute ce champ aux tables existantes et le remplit à
partir des compteurs déjà enregistrés : il n’est pas nécessaire de relancer
le calcul historique. Le tableau détaillé de l’IHM l’affiche pour les nouveaux
calculs. Le SQL manuel est `database/sql/ml/oracle_atr_market_regime_daily_ratio_migration.sql`.

## Colonnes

| Colonnes | Sens / source |
|---|---|
| `trade_date` | Séance étudiée J, pas la date d’import |
| `regime_mode` | `stock_macro_indicators_daily.mode`, copié sans recalcul |
| `vix`, `vix9d`, `ten_y`, `vxn`, `vix3m`, `move` | Valeurs macro existantes, mêmes unités que la table source |
| `yield_10y_5d_pct` | Nom exact de la variation 10 ans/5 jours dans la source ; pas `yeid_10y_5d_pct` |
| `sentiment_score` | Sentiment macro de la source, pas sentiment de chaque titre |
| `universe_count` | Nombre de symboles du fichier normalisé |
| `oracle_scored_count` | Nombre de symboles avec score Oracle fini à J |
| `oracle_top20_count` | Nombre dans le TOP20 Oracle avant intersection |
| `atr_valid_count`, `atr_missing_count` | Couverture ATR parmi les titres classés Oracle |
| `intersection_count` | Nombre de candidats Oracle ET ATR TOP20 |
| `evaluated_count`, `unknown_count` | Candidats avec labels disponibles/qualifiés ou inconnus |
| `d1_count`, `d10_count` | Effectifs réels parmi les candidats évalués |
| `d1_pct`, `d10_pct`, `evaluation_coverage_pct` | Pourcentages décrits ci-dessus |
| `d10_d1_ratio` | Ratio D10/D1 sans unité, `NULL` si division impossible |
| `d1_d10_total_pct` | Somme D1 + D10, de 0 à 100 ; `NULL` sans candidats évaluables |
| `status`, `quality_details` | Complétude et motifs explicites |
| `evaluated_as_of` | Date limite de disponibilité des labels utilisée pour le calcul |
| `calculation_version` | Version du contrat, actuellement `oracle_atr_v1` |

Les motifs sont `MISSING_REGIME`, `MISSING_MACRO`, `MISSING_ORACLE`,
`MISSING_ATR`, `EMPTY_INTERSECTION`, `INCOMPLETE_LABELS`. Une séance complète
signifie que ses candidats sélectionnés sont tous évaluables et que les macros
demandées sont présentes. Cela ne garantit pas la couverture de tous les titres
du fichier : comparer également `oracle_scored_count` à `universe_count`.

## Limites PIT et interprétation

Les scores viennent des lignes existantes du batch : l’étude ne prouve pas à
elle seule qu’ils sont hors échantillon. Vérifier le contrat et les dates
d’entraînement du batch avant toute conclusion. Les macros sont les valeurs
actuellement stockées, sans certification supplémentaire de leur vintage PIT.
L’univers fichier est statique et peut comporter un biais de survivance.

Les résultats D1/D10 à J utilisent volontairement des données futures : ce sont
des **réponses pour étude rétrospective**, jamais des features à injecter dans
une décision à J. À H20, les dernières semaines restent généralement incomplètes.
La fin demandée `2026-09-30` ne garantit pas que les prix H20 suivants existent.

Chercher un régime explicatif dans ce tableau ne valide pas un veto profitable.
Toute règle issue de l’étude doit être figée puis confirmée sur une période
indépendante, sans ajustement après observation des pertes.

## Vérification technique

`tests/test_oracle_atr_study.py` couvre le dénominateur connu, les labels futurs
ou invalides, les données absentes, les doublons, l’identité stable à répétition,
l’upsert limité à cette table, les transactions par tranche, la reprise après
échec, le recalcul forcé, la protection contre une base CN et la commande
IHM. Les tests complémentaires du filtre ATR vérifient calcul et causalité.

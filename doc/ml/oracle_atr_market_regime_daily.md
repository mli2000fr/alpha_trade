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
dans les sources. Cette option de recalcul ne change pas le schéma SQL ;
l’ajout des quatre listes décrit plus bas exige néanmoins la migration 0092.

Exemple de commande, à remplacer par un batch et un fichier réellement présents :

```powershell
python -u -m service.market.oracle_atr_study --batch-id <batch_oracle> --symbol-source universe-file:univers_filtred_tradable.txt --start-date 2020-01-01 --end-date 2026-09-30 --artifacts-dir artifacts/models
```

## Préconditions et données absentes

- Migrations **0089 à 0092**, ou exécution du SQL de création à jour
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
| `calculation_version` | Version du contrat, actuellement `oracle_atr_v2_movements` |

Les motifs sont `MISSING_REGIME`, `MISSING_MACRO`, `MISSING_ORACLE`,
`MISSING_ATR`, `EMPTY_INTERSECTION`, `INCOMPLETE_LABELS`. Une séance complète
signifie que ses candidats sélectionnés sont tous évaluables et que les macros
demandées sont présentes, et les quatre listes comparatives peuvent être constituées.
Cela ne garantit pas la couverture de tous les titres
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

## Quatre listes comparatives de mouvements réalisés — migration 0092

### Objectif et populations

Pour chaque séance, comparer les rendements réalisés de quatre sélections,
avec **N = `evaluated_count`**, c’est-à-dire le nombre de candidats évaluables
de l’intersection Oracle × ATR. Les quatre colonnes sont des tableaux JSON de
nombres, pas des probabilités ni des listes de symboles.

| Colonne JSON | Sélection des titres avant le tri final |
|---|---|
| `real_oracle_top_returns_pct` | TOP20 réel par valeur absolue du rendement futur ; conserver ses N premiers |
| `intersection_returns_pct` | Les N candidats évaluables de l’intersection Oracle TOP20 ∩ ATR TOP20 |
| `predicted_oracle_top_returns_pct` | Les N premiers titres par score `proba_extreme` décroissant |
| `atr_top_returns_pct` | Les N premiers titres par ATR20/prix décroissant |

Le périmètre de comparaison est celui du fichier choisi **restreint aux titres
ayant un score Oracle fini à J** (`oracle_scored_count`). Le classement ATR est
restreint davantage aux ATR positifs et finis de cette population. Ce contrat
évite de comparer le benchmark réel de tout le marché à un modèle ne couvrant
qu’une partie du fichier. Si cette couverture est faible, ces listes ne
représentent pas tout l’univers configuré : vérifier les compteurs.

Le TOP20 réel utilise ici le percentile de `abs(future_return)` ≥ 0,80 sur ce
périmètre de comparaison. Il **ne signifie pas D10 seulement** : une forte
baisse figure également parmi les plus fortes amplitudes. Les pourcentages
D1/D10 existants restent fondés sur les déciles originaux du batch, sans
reclassement. Ne pas confondre ces deux référentiels.

### Unités, horizon et ordre des valeurs

Les quatre listes reprennent `global_oracle_labels.future_return`, pour le batch,
la séance et l’horizon Oracle identifiés dans l’artefact. La convention du label
est le rendement de prix à H séances, pas le MFE/MAE intrapériode ni le résultat
d’une position avec TP/stop. Le service ne calcule pas une nouvelle cible et ne
soustrait pas commissions, spread, slippage ou taxes.

```text
valeur stockée = 100 × future_return
0,082 → 8,2 % ; −0,075 → −7,5 %
JSON : [8.2,-7.5,6.9]
```

Après la sélection propre à chaque colonne, les valeurs sont triées par
**amplitude absolue décroissante**, en conservant leur signe. Le tableau
Oracle prédit n’est donc pas présenté dans l’ordre des scores Oracle ; la
sélection l’est, puis le tri final sert à comparer les amplitudes réalisées.
Les égalités de score, d’ATR ou d’amplitude sont départagées par symbole en
ordre lexical pour obtenir un résultat déterministe.

Exemple : N=2 et les deux meilleurs scores Oracle désignent A et B. Leurs
rendements sont +3 % et −8 %. La troisième colonne contient `[-8,3]`, même
si C réalise +20 %. C ne remplace jamais A ou B après observation du futur.
Chaque liste renseignée a exactement N valeurs, même si le TOP20 d’origine
contient davantage de titres. Les seuils inclusifs et ex æquo peuvent faire
varier la taille des pools TOP20 ; si le pool réel ne permet pas N valeurs,
son tableau reste `NULL` plutôt que d’être complété hors de ce pool.

### Labels absents, invalides ou encore futurs

Un label évaluable exige qualité valide, rendement **fini**, décile valide et
date de disponibilité au plus égale à `evaluated_as_of`. Zéro résultat
évaluable donne quatre `NULL`, pas quatre tableaux vides ou remplis de zéros.

- Intersection : tableau des seuls candidats évaluables. Une intersection
  partielle reste marquée `INCOMPLETE_LABELS`, même si ce tableau est renseigné.
- Oracle prédit / ATR : sélectionner les N premiers **avant** de vérifier leurs
  labels. Si l’un manque, toute la liste concernée reste `NULL` : aucun remplacement
  par un titre moins bien classé. Motifs `INCOMPLETE_PREDICTED_TOP_RETURNS` et
  `INCOMPLETE_ATR_TOP_RETURNS`.
- TOP20 réel : tous les titres du périmètre Oracle scoré doivent avoir un label
  évaluable pour connaître honnêtement le classement réel. Sinon `NULL` avec
  `INCOMPLETE_REAL_TOP_RETURNS`. Classer uniquement les labels connus risquerait
  de déclarer « premiers réels » des titres qui ne le sont pas.

Ces motifs supplémentaires rendent la ligne `INCOMPLETE`, sans effacer les
mesures ou les autres listes effectivement calculables. Ils ne constituent
pas une erreur technique arrêtant les tranches suivantes.

La comparaison des dates de disponibilité conserve le type datetime pandas,
y compris lorsque tous les labels ont une date absente/invalide ou lorsque
la journée n’a aucun label. Ces cas donnent une ligne incomplète sans arrêter
le calcul. La date limite est inclusive sur toute la journée ; les dates
absentes et les journées ultérieures ne sont jamais évaluables.

### Installation et alimentation des lignes existantes

La création de table de référence contient les quatre colonnes. Pour une table
déjà existante, choisir **soit** Alembic 0092 **soit** le SQL manuel
[`oracle_atr_market_regime_daily_movements_migration.sql`](../../database/sql/ml/oracle_atr_market_regime_daily_movements_migration.sql).
Le SQL manuel s’exécute une seule fois ; la migration Alembic vérifie les
colonnes existantes et peut suivre une application manuelle sans les ajouter
en double. La migration refuse toute base autre que `alpha_trade` en mode
connecté. Elle n’alimente pas les listes avec des valeurs inventées.

Après modification du schéma, relancer **Alimenter l’étude Oracle × ATR** sur
la période, l’univers et le batch souhaités. Le changement de version de calcul
vers `oracle_atr_v2_movements` force automatiquement le recalcul des anciennes
lignes v1, même complètes, sans nécessité de cocher le recalcul forcé. Les clés
restent identiques : upsert, pas doublons. Les tranches déjà complètes en v2
sont ensuite ignorées lors des reprises ordinaires.

Le contrôle des quatre colonnes est effectué avant la lecture coûteuse des
prix. Aucun nouvel entraînement ou téléchargement n’est nécessaire si les
scores, prix et labels sont déjà présents. Le tableau de résultat dans l’IHM
présente aussi les nouvelles colonnes ; aucune nouvelle commande n’est requise.

**Réserve importante :** ces listes sont des résultats futurs, donc strictement
rétrospectifs. Elles ne doivent jamais servir de features connues à J pour un
modèle, une sélection live ou une décision de backtest.

Les tests couvrent également les quatre populations, les unités et signes,
le tri absolu, les ex æquo déterministes, les valeurs non finies, l’absence de
remplacement d’un résultat manquant, les indices de DataFrame répétés, le
changement de version, la persistance JSON et les gardes de migration US.

# Étude quotidienne Oracle × ATR et régime de marché

## Complément du 11 octobre 2026 — maximum absolu signé en pourcentage

Nouvelle colonne JSON **`predicted_oracle_score_order_max_returns_pct`** : pour
les mêmes N premiers scores Oracle, elle conserve **le plus fort mouvement
absolu du chemin J+1..J+H, hausse ou baisse, avec son signe**. Pas de retri par
résultat futur et aucun remplacement des titres manquants. Chaque valeur est
arrondie à l'entier (`ROUND_HALF_UP`), mais le choix du côté dominant compare
les pourcentages **précis avant arrondi**.

```text
up_pct   = 100 × (maximum des HIGH comparables / clôture J − 1)
down_pct = 100 × (minimum des LOW comparables / clôture J − 1)
valeur   = up_pct si abs(up_pct) >= abs(down_pct), sinon down_pct
```

Les LOW suivent exactement la même base d'ajustement que les HIGH ci-dessous.
Le jour J n'est pas dans la fenêtre future. En cas d'égalité exacte des
amplitudes non arrondies, le côté hausse est conservé, règle explicite et stable.
Ce n'est **ni le rendement terminal à J20, ni la seule hausse maximale, ni un
gain réellement encaissé**, ni une information disponible à J pour le live.

Exemple vérifié : **AMR, signal du 10 février 2020**, référence **5,67 $**.

| Mesure | Valeur précise | Liste entière |
| --- | ---: | ---: |
| Sommet HIGH du 20 février : 6,93 $ | +22,22 % | Prix maximal : 7 |
| Creux LOW du 9 mars : 3,935 $ | −30,60 % | Maximum absolu signé : **−31** |
| Clôture finale du 10 mars : 4,17 $ | −26,46 % | Rendement H20 : **−26** |

Ainsi, **26 > 22**, mais le chemin contient une baisse encore plus importante
que le résultat terminal : c'est **−31** qui est retenu dans la nouvelle liste.
La colonne `predicted_oracle_score_order_max_prices` reste une liste de prix
HIGH en dollars, arrondis à l'entier ; elle n'est pas transformée silencieusement
en pourcentages.

`movement_quality.lists.predicted_oracle_score_order_max_returns_pct` conserve
les symboles/positions, couverture, motifs d'omission, unité `PERCENT`,
statistique `MAX_ABSOLUTE_SIGNED_HIGH_LOW_RETURN`, règle de départage et
`value_details.<symbol>` : prix de référence précis, sommet/creux, leurs dates,
les deux pourcentages précis, côté/date dominants et disponibilité. Un
manquant n'est pas remplacé par zéro ou par le rendement H20 : mode `partial`
→ liste partielle ; mode `strict` → NULL. Joindre les listes par symbole,
**pas par indice seul** si leurs couvertures diffèrent.

Migration dédiée **0103_oatr_max_returns** ; SQL manuel :
`database/sql/ml/oracle_atr_max_returns_migration.sql`. Le bloc **Régime Marché
→ Alimenter l'étude Oracle × ATR** et le backfill des prix calculent désormais
aussi cette liste. La reprise ne saute une ancienne ligne COMPLETE v7 que si
la nouvelle liste est également renseignée.

Pour compléter les seules lignes existantes, en conservant les anciens prix,
rendements H20, sélections, macros et D1/D10 :

```powershell
python -u -m service.market.oracle_atr_peak_returns_backfill --output-dir artifacts/research/oracle_atr_max_prices/<nouveau-dossier> --start-date 2020-01-01 --end-date 2026-09-30 --date-batch-size 20 --apply
```

Le script relit les HIGH/LOW qualifiés et vérifie leur accord avec le sommet et
le prix J précis déjà archivés. Aucun appariement silencieux de prix corrigés
avec des anciens prix incompatibles. Sauvegarde Parquet/DDL avant ajout de la
colonne, UPDATE par clé complète et petites transactions ; contrôle concurrent
des anciennes listes/métadonnées/statuts avant chaque écriture. Sans `--apply`,
calcul et rapport seulement. Les anciens rendements finaux et les prix sources
ne sont pas modifiés. Suivi : `progress.json`, puis `report.json`.

### Arrondi des prix existants

Les **1 681 listes de prix non NULL** ont été arrondies en base et vérifiées
contre leur sauvegarde : prix précis et ordre conservés dans les métadonnées.
Pour la ligne du 10 février 2020, `[6.93,1.98,12.466733,32.55,7.11]` est devenu
**`[7,2,12,33,7]`**. Rapport/sauvegarde :
`artifacts/research/oracle_atr_max_prices/round-integers-20261011-v1/`.

### Remplissage du maximum absolu signé terminé

Les **1 695 dates existantes** ont été traitées : **1 681 listes renseignées**,
**461 142 valeurs qualifiées**, 1 106 listes COMPLETE et 575 PARTIAL. Les
**14 dates non évaluables** restent NULL ; aucun maximum provisoire inventé.
La ligne du 10 février 2020 conserve les rendements H20
`[-26,-30,6,-36,-13]` et les prix `[7,2,12,33,7]` ; sa nouvelle liste dominante
commence par **`[-31,-43,21,-48,-26]`**, symboles AMR/AR/ANAB/HOV/DAC dans le même
ordre. **166 tests ciblés/non-régression réussis**. Rapport et sauvegarde avant
les UPDATE :
`artifacts/research/oracle_atr_max_prices/dominant-returns-20261011-v1/`.
Le test préalable sur une date et sa sauvegarde avant ajout de la colonne
restent dans `dominant-returns-20261011-smoke/`. Aucun nouvel entraînement lancé.
Vérification complète dans `verification.json` : les **461 142 valeurs** sont
recalculées depuis leurs prix précis, les 1 695 clés et **36 anciennes colonnes**
(hors clés/statut/métadonnées/date de modification) sont identiques à la
sauvegarde ; toutes les métadonnées antérieures restent identiques également.

### Limite : amplitude dominante n'est pas résultat d'une position protégée

Ces listes restent descriptives. AMR fournit un contre-exemple utile : avec
entrée à l'ouverture de J+1 (**5,73 $**, le 11 février 2020), TP de **20 %** et
SL de **7 %**, les barres journalières placent le TP LONG le **20 février** avant
son SL le **27 février**. Le SL SHORT est atteint dès le **11 février**, avant
son TP le **6 mars**. Le creux dominant −31 % ne signifie donc pas qu'un SHORT
protégé aurait pu l'encaisser. Ceci vérifie l'ordre des journées, pas les fills
réels ni une performance après coûts. Les touches TP/SL au sein d'une même
bougie resteraient ambiguës.

Une cible future « TP atteint avant SL et avant l'échéance » est une hypothèse
distincte, à qualifier avec entrée J+1, gaps, coûts et résolution intraday.
TP/SL/horizon devront être configurables et figés dans les artefacts du modèle ;
un changement de barrière nécessitera un nouvel entraînement. **Cette nouvelle
cible de trading n'est pas implémentée ni entraînée ici.** Ne pas interpréter
la nouvelle liste rétrospective comme des labels de trades gagnants.

## Ajout du 11 octobre 2026 — prix maximal du chemin en ordre Oracle

Nouvelle colonne JSON : **`predicted_oracle_score_order_max_prices`**.
Elle utilise les **mêmes N=`evaluated_count` premiers scores Oracle** que
`predicted_oracle_score_order_returns_pct`, sélectionnés avant toute lecture du
futur, dans l'ordre décroissant de `proba_extreme` (égalité : symbole).
Ce n'est pas le TOP de l'intersection : comme la colonne de référence demandée,
ce sont les premiers Oracle de l'univers scoré ; N provient de l'intersection
évaluable. Aucun reclassement selon le prix maximal futur.

Chaque valeur est le **maximum des HIGH journaliers entre J+1 et J+H inclus**,
où H est l'horizon de l'artefact (20 dans l'étude actuelle), sur les séances NYSE.
J lui-même est exclu : une bougie connue le jour du signal n'est pas un mouvement
futur. Exemple sans ajustement : clôture J à 20 $, HIGH J+9 à 32 $, clôture J+20
à 15 $ → la nouvelle valeur est **32**, même si le rendement final est −25 %.
Il s'agit d'un **prix**, pas d'un rendement de +60 %, d'un score Oracle ou d'un
profit qu'une stratégie aurait effectivement encaissé.

Les prix sont comparables **sur l'échelle du prix de J** :

```text
high_comparable[t] = high[t] × (adj_close[t] / close[t])
                            / (adj_close[J] / close[J])
```

Même base d'ajustement que les labels, avec retour à l'échelle nominale de J.
Une division 2:1 ne fabrique donc pas une chute/moitié de sommet artificielle.
Cette base peut inclure les dividendes selon `adj_close` : elle n'est pas toujours
le cours brut coté à la date du sommet, ni une reconstruction certifiée des
opérations sur titres. Sans ajustement, c'est exactement le HIGH brut.
Le fallback `adj_close` absent → `close` suit le contrat des labels ; les autres
contrôles de chemin restent impératifs. Depuis le 11 octobre, la liste contient
des **prix arrondis à l'entier le plus proche**, règle `ROUND_HALF_UP` (6,93 → 7 ;
32,5 → 33), pas des pourcentages. Les prix non arrondis restent dans
`movement_quality.lists.predicted_oracle_score_order_max_prices.value_details`.
Un prix inférieur à 0,50 $ peut devenir 0 dans cette liste de présentation :
utiliser les valeurs précises pour tout calcul, jamais les entiers affichés.

Exemple vérifié en base : **10 février 2020, AMR**, premier au score Oracle de la
sélection : clôture J **5,67 $**, sommet **6,93 $ le 20 février**, soit **+22,22 %**
relativement à J, et rendement final arrondi **−26 % le 10 mars (J20)**. Ces deux
valeurs ne se contredisent pas : l'une est un prix intermédiaire en dollars,
l'autre un rendement terminal en pourcentage. Ce champ ne représente pas non
plus l'excursion absolue dominante high/low ; il conserve le sommet HIGH.

### Disponibilité et qualification

- Observation complète : barre J et chacune des H séances futures attendues,
  OHLC positif/cohérent, volume positif et `is_filled=0`.
- Source, instrument et type d'ajustement stables et identifiables ; aucune
  rupture d'identité répertoriée, ni saut ajusté inexpliqué ≥20x ou ≤1/20x.
- Rendement J→J+H cohérent avec le label archivé ; pas de fusion silencieuse
  entre les anciens rendements et des prix corrigés incompatibles.
- Disponible seulement à la séance suivante, comme le label Oracle. Pas de
  maximum provisoire affiché comme un maximum H20 définitif.
- Les grandes plages `high/low >=1.5` restent signalées pour revue : ce drapeau
  n'est ni une correction automatique ni une preuve indépendante des HIGH.

En mode `partial`, un chemin non qualifié est omis, **sans candidat de
remplacement**. En mode `strict`, un manquant laisse la liste entière à NULL.
Les trous de cette liste peuvent différer de ceux des rendements finaux :
connaître les deux clôtures terminales ne prouve pas les vingt HIGH intermédiaires.
Toujours joindre les valeurs par symbole/position, pas par seul indice entre
deux listes partielles. Les listes précédentes ne sont pas modifiées.

`movement_quality.lists.predicted_oracle_score_order_max_prices` expose :
sélection initiale, ordre des symboles réellement présents, positions initiales,
couverture, inconnus et motifs, unité, horizon/base d'ajustement ;
`value_details.<symbol>` conserve la date du sommet (première si égalité),
le prix de référence J, le facteur d'ajustement et les réserves de plage intraday.
Une réserve ajoute `INCOMPLETE_PREDICTED_MAX_PRICES` et un statut PARTIAL/INCOMPLETE.

**Information future rétrospective uniquement : jamais une feature disponible
à J, ni un filtre d'entrée live.** Le modèle Oracle, la sélection opérationnelle,
les prix sources et les labels ne sont pas modifiés.

### Mise en service et remplissage

SQL : `database/sql/ml/oracle_atr_max_prices_migration.sql` ; création à jour :
`database/sql/ml/oracle_atr_market_regime_daily.sql` ; migration Alembic
`0102_oatr_max_prices`, US uniquement. Ne pas lancer toutes les anciennes
migrations pour ajouter cette colonne, ni estampiller artificiellement la base.

Le bloc **Régime Marché → Alimenter l'étude Oracle × ATR** calcule désormais
cette liste automatiquement par tranches. Versions actuelles :
`oracle_atr_v7_path_max_prices` en partiel, `oracle_atr_v7_strict_max_prices` en
strict. Les mentions v5/v6 ci-dessous sont des états historiques ; une ancienne
ligne COMPLETE n'est plus suffisante pour sauter le calcul v7.

Remplissage ciblé des seules lignes déjà existantes, sans recalcul des anciens
rendements/proportions/sélections :

```powershell
python -u -m service.market.oracle_atr_peak_backfill --output-dir artifacts/research/oracle_atr_max_prices/<nouveau-dossier> --start-date 2020-01-01 --end-date 2026-09-30 --date-batch-size 20 --apply
```

Sans `--apply`, calcul/rapport seulement. Avant toute écriture : sauvegarde
complète des lignes de la fenêtre en Parquet et du DDL dans `protocol.json`.
Chaque tranche est validée séparément ; un arrêt conserve les précédentes.
Une relance dans un **nouveau** dossier peut recalculer les mêmes clés par UPDATE,
sans doublons. `progress.json`, `report.json` et les Parquet de tranche conservent
les résultats et réserves. Aucune écriture dans les autres tables.

### Remplissage réellement terminé le 11 octobre 2026

La colonne est ajoutée à la base US locale. Le journal Alembic, encore en 0088,
n'est pas estampillé et les migrations intermédiaires ne sont pas lancées.

Les **1 695 lignes existantes** de 2020 au 30 septembre 2026 sont traitées par
tranches de vingt. Résultat de la nouvelle liste :

- **1 681 listes renseignées**, soit **461 142 prix maximaux qualifiés** ;
- 1 106 listes COMPLETE et 575 PARTIAL (statut de la liste, pas forcément celui
  de toute la journée, dont les macros/anciennes listes peuvent avoir des réserves) ;
- **14 listes à NULL**, du 11 au 30 septembre 2026, non évaluables selon la
  disponibilité des labels H20 au 11 octobre. Recalcul après maturité/prix/labels
  requis ; ne pas remplir avec un maximum partiel de période.

Les omissions recensées concernent 1 015 chemins à barre manquante, remplie ou
invalide (dont volume/OHLC), 144 labels à sortie manquante et un label à entrée
manquante. Ce sont des occurrences titre/date, pas 1 160 titres distincts.

Vérifications en lecture seule : 1 681 listes contrôlées (taille, symboles,
positions originales, ordre, nombres positifs finis) ; recalcul indépendant
d'un sommet par année 2020–2026 depuis les barres. **39 anciennes colonnes**,
incluant les six listes de rendements et les proportions D1/D10, sont identiques
à la sauvegarde originale sur les 1 695 lignes. Aucun doublon ajouté.
117 tests ciblés/non-régression réussis.

Rapport terminé :
`artifacts/research/oracle_atr_max_prices/max-prices-20261011-v2/report.json`.
Le premier passage v1 est arrêté après 160 lignes persistées pour une
optimisation des conversions de prix. Les 160 listes sont identiques entre les
deux versions ; v2 recalcule toute la fenêtre. La sauvegarde **avant le premier
ajout et changement de métadonnées** reste en v1 (`study_before.parquet`, DDL
dans `protocol.json`) ; v2 conserve aussi son état de départ, déjà enrichi sur
les 160 premières lignes. Aucun modèle, batch planifié, prix source, label ou
ordre broker n'a été modifié.

## Ajout du 11 octobre 2026 — ordre Oracle de l'intersection

`intersection_oracle_score_order_returns_pct` contient les rendements réalisés
des mêmes titres que l'intersection **Oracle TOP20 ∩ ATR TOP20**, mais conservés
dans l'ordre décroissant de `proba_extreme` ; égalités départagées par symbole.
Pas de reclassement par rendement futur. Exemple : l'ordre prédit donne
`[1,-10,20]`, tandis que l'ordre d'amplitude réalisée donne `[20,-10,1]`.
Ces nombres sont des résultats futurs signés, en pourcentages arrondis à l'entier,
pas des scores/prévisions de rendement ni des profits de portefeuille.

En mode partiel, les rendements inconnus sont omis sans remplacer les titres,
en conservant l'ordre relatif. `movement_quality.lists` expose la sélection,
les symboles de chaque valeur, leurs positions initiales et les manquants.
En mode strict, une intersection incomplète laisse cette nouvelle liste à NULL.
L'ancienne `intersection_returns_pct` conserve son comportement historique.

SQL : `database/sql/ml/oracle_atr_intersection_score_order_migration.sql` ;
Alembic `0101_oatr_intersection_order` (US uniquement). Nouvelle version de calcul
`oracle_atr_v6_intersection_order` : les lignes anciennes seront recalculées à
la prochaine alimentation, même si elles étaient complètes en version v5.
L'ajout de colonne seul ne remplit pas les lignes historiques. Aucun recalcul
historique ni changement de modèle ou sélection live demandé ici.

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## À quoi sert cette table ?

`alpha_trade.oracle_atr_market_regime_daily` rapproche les indicateurs macro du
jour et les résultats futurs de la sélection **Oracle TOP20 ∩ ATR TOP20**.
Elle permet d’étudier les jours/régimes où les candidats deviennent plus souvent
D1 ou D10. Ce n’est ni une table de signaux de production, ni un backtest de
portefeuille. Un pourcentage D10 élevé ne mesure pas un profit net.

Depuis le 10 octobre, le mode **partiel explicite** est le défaut dans
`config.yaml`. Les règles « liste entière à NULL dès qu'un rendement manque »
décrites dans les anciens audits restent celles du mode `strict`, pas du mode
partiel. Voir la section « Mode partiel et contrôle des nouvelles entrées » en fin
de document. Les anciens résultats restent des constats historiques datés.

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
6. Choisir le mode partiel ou strict, puis examiner les séances complètes,
   partielles/incomplètes et la couverture détaillée dans `movement_quality`.

Le traitement se fait par tranches de **20 séances par défaut**, taille réglable
dans l’écran ou par `--date-batch-size`. Prix, scores et labels sont chargés pour
chaque tranche, puis celle-ci est enregistrée dans sa propre transaction. Une
progression indique la tranche en calcul puis sa confirmation de persistance.
Un échec ultérieur conserve les tranches précédentes ; seule la tranche non
validée doit être refaite.
Ne pas lancer plusieurs alimentations identiques en parallèle : cela n’apporte
aucun bénéfice. Par défaut, une relance saute les séances déjà `COMPLETE` pour la
même identité et version de calcul ; elle recalcule les séances absentes ou
`PARTIAL` ou `INCOMPLETE`. Ces dernières peuvent donc être réexaminées à chaque relance tant
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

- Migrations **0089 à 0095**, **0101** et **0102** nécessaires à cette table, ou exécution du SQL de création à jour
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
connus mais reste `PARTIAL` en mode partiel (`INCOMPLETE` en mode strict).
Il faut lire sa couverture avant de l’interpréter.

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

## Quatre listes comparatives — contrat initial strict, migration 0092

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
valeur stockée = arrondi entier de (100 × future_return)
0,082 → 8 % ; −0,075 → −8 %
JSON : [8,-8,7]
```

Après la sélection propre à chaque colonne, les valeurs sont triées par
**amplitude absolue décroissante**, en conservant leur signe. Le tableau
Oracle prédit n’est donc pas présenté dans l’ordre des scores Oracle ; la
sélection l’est, puis le tri final sert à comparer les amplitudes réalisées.
Les égalités de score, d’ATR ou d’amplitude sont départagées par symbole en
ordre lexical pour obtenir un résultat déterministe.

Depuis `oracle_atr_v4_integer_returns`, les cinq listes, y compris
`predicted_oracle_score_order_returns_pct`, stockent des nombres JSON entiers.
L'arrondi intervient après sélection et tri, à l'entier le plus proche ;
les demis sont éloignés de zéro (0,5 → 1 ; −0,5 → −1).
Ce n'est pas une troncature. Les rendements sources, statistiques D1/D10 et
ratios ne sont pas arrondis par cette évolution. L'ordre Oracle par score
reste inchangé pour la cinquième liste. Aucune migration de schéma requise.

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

### Ordre Oracle prédit conservé — ajout du 8 octobre 2026

`predicted_oracle_score_order_returns_pct` contient les mêmes N titres que
`predicted_oracle_top_returns_pct`, mais **sans reclassement par rendement réalisé**.
La position 1 correspond au plus grand `proba_extreme`, puis score décroissant ;
les ex æquo sont départagés par symbole croissant. N reste `evaluated_count`.
Les valeurs sont des rendements futurs réalisés signés en pourcentage, et non
des prédictions de rendement ou de sens. Exemple : scores A > B, rendements
A=+3 %, B=−8 % : nouvelle colonne `[3,-8]`, ancienne colonne `[-8,3]`.

Les mêmes exigences de labels s'appliquent : si un résultat du TOP N manque,
la nouvelle liste entière reste NULL, sans remplacement par un autre titre.
La colonne actuelle et ses règles de tri sont inchangées.

Schéma : migration Alembic **0094** ou SQL manuel
[`oracle_atr_score_order_migration.sql`](../../database/sql/ml/oracle_atr_score_order_migration.sql).
L'ajout du schéma seul ne remplit pas l'historique. Relancer le même bloc
**Alimenter l'étude Oracle × ATR** avec le même batch, univers et dates :
la version `oracle_atr_v4_integer_returns` recalcule les anciennes lignes v1/v2/v3,
par tranches et upsert sans doublons. Les séances complètes déjà en v4 sont
ignorées à la reprise. Aucun nouvel entraînement n'est nécessaire.

### Réparation des listes NULL — 9 octobre 2026

Le builder distingue désormais le calendrier **NYSE réel** de la présence des
prix : H20 compte vingt séances, y compris une séance dont toutes les barres
seraient absentes. La disponibilité est la séance suivant la sortie, même lorsque
la prochaine barre n'a pas été téléchargée. Exemple : 3 septembre 2026 → sortie
le 2 octobre → disponibilité le 5 octobre. Les barres `is_filled=1` ne peuvent
plus qualifier les extrémités d'une cible : ce ne sont pas des prix observés.

La réparation est dédiée à US/`alpha_trade`. Elle sauvegarde les labels des dates
concernées et les agrégats avant toute modification, répare la disponibilité,
reconstruit les journées dont la cible change et reprend l'étude par upsert de
vingt séances. La reconstruction `stored_membership` utilise **tous les symboles
originaux de chaque journée**, pas seulement l'intersection ni l'univers actuel.
Pour prolonger les labels d'un batch `static_bars`, la réparation reconstruit le
pool depuis **tous ses anciens labels**, puis exige de reproduire exactement
l'univers de la dernière journée historique à partir des barres. Ce contrat et
le pool sont archivés dans `static_extension_membership.json`. Seules les dates
dont la sortie H20 est déjà couverte par les prix et la disponibilité passée sont
prolongées. Un pool incompatible ou un univers dynamique reste bloqué plutôt
que remplacé par l'univers actuel ou les seuls titres scorés.

```powershell
python -u -m service.market.oracle_atr_repair `
  --batch-id model-factory-20261003082853-e98332 `
  --start-date 2020-01-01 --end-date 2026-09-30 `
  --symbol-source universe-file:univers_filtred_tradable.txt `
  --output artifacts/research/oracle_atr_null_repair/repair-YYYYMMDD-v1 `
  --apply --fetch-prices
```

Sans `--apply`, audit seul. `--fetch-prices` archive les relectures EODHD et leurs
splits avec empreinte SHA-256, **sans écriture dans les tables de prix**. Chaque
exécution exige un nouveau répertoire. `plan.json` décrit les dates affectées ;
`labels_before/` et `study_before.parquet` conservent les sauvegardes ;
`price_evidence_report.json` décrit les relectures ; `report.json` compare les
comptages avant/après. Une relecture fournisseur ne certifie pas à elle seule
l'identité d'un titre radié, ni un changement de ticker.

Les règles strictes restent intactes : prix futur inconnu, rupture non expliquée
ou H20 non disponible restent à `NULL`. Aucun remplacement de candidat, aucun
rendement zéro pour une radiation, aucun relâchement des contrôles pour remplir
les colonnes. Aucun modèle n'est modifié ou réentraîné ; aucune migration de
schéma n'est nécessaire.

### Résultat vérifié de la réparation `repair-20261009-v3`

Exécution terminée le 9 octobre 2026 à 23:53 Paris, statut
`COMPLETED_WITH_QUALIFICATION_RESERVES`. Rapport :
`artifacts/research/oracle_atr_null_repair/repair-20261009-v3/report.json`.
Les compteurs ont été revérifiés en base après l'exécution (1 695 journées).

| Liste | Journées NULL avant | Après |
| --- | ---: | ---: |
| TOP réel | 134 | 134 |
| Intersection Oracle × ATR | 19 | 15 |
| Premiers Oracle, tri par amplitude réalisée | 105 | 103 |
| Premiers ATR | 97 | 95 |
| Premiers Oracle, ordre du score prédit | 105 | 103 |

Travail effectivement appliqué : disponibilité du 3 septembre corrigée ;
7 149 labels reconstruits sur les 1er et 4 mai, 15 juin et 15 juillet 2026,
en conservant leurs univers quotidiens ; 5 274 labels ajoutés sur les
4, 8 et 9 septembre (5 265 qualifiés, neuf prix de sortie manquants).
134 agrégats recalculés et persistés, sans nouvel entraînement ni écriture
dans les tables de prix. La sélection de l'intersection est maintenant évaluable
sur ces quatre journées supplémentaires ; cela ne rend pas nécessairement les
autres listes complètes.

Les quinze journées du 10 au 30 septembre restent sans résultats évaluables.
Au moment du run, les prix s'arrêtaient au 7 octobre : la sortie H20 du
10 septembre nécessite la barre du 8 octobre ; les journées suivantes nécessitent
des sorties et disponibilités encore ultérieures. Ces dates doivent être
recalculées après acquisition des prix requis et maturité du label.

**Réserve de téléchargement à ne pas confondre avec un échec du recalcul :**
aucune des 88 relectures EODHD n'a abouti durant ce run. La première a échoué
techniquement, les 87 suivantes ont rencontré le circuit HTTP ouvert. Un smoke
ultérieur a identifié `SSL_CERTIFICATE_VERIFY_FAILED` (autorité locale manquante).
Avec la session vérifiée existante `common.verified_http.verified_session`, le
smoke ne rencontre plus l'erreur TLS, mais la fenêtre BK du 1er au 2 juin 2026
retourne zéro barre. Cela ne constitue ni une réparation de prix, ni une preuve
qu'un trou ou une radiation a été résolu. Ne jamais désactiver la vérification TLS.

L'inventaire initial porte sur 999 labels non qualifiés : 168 trous de sortie
intérieurs, 809 sorties au-delà de la dernière barre locale et 22 ruptures de
prix non expliquées, sur 88 symboles. Les sorties terminales ne sont pas toutes
des radiations certifiées. La prochaine action est la relecture ciblée avec TLS
vérifié, puis la qualification prix/identité avant toute correction des barres
et reconstruction des journées concernées. Le TOP réel reste NULL tant que
le périmètre scoré complet ne dispose pas des rendements qualifiés requis.

## Réparation du 10 octobre 2026 — fenêtre 30 mars / 30 septembre

La réparation est exécutée, mais **le remplissage intégral reste bloqué par les
prix manquants/non qualifiés et la maturité H20**. Ne pas la présenter comme une
suppression de tous les NULL.

- La relecture EODHD utilise désormais la session TLS vérifiée existante, sans
  désactivation des certificats. Les 51 symboles audités ont répondu avec au
  moins une barre, mais une réponse non vide n'implique pas que les sorties H20
  nécessaires soient présentes. Les réponses et les splits sont archivés avec
  leur empreinte SHA256.
- 201 274 labels de 113 dates sont reconstruits avec `stored_membership`, donc
  avec tous les membres originaux de chaque date, sans remplacer les titres
  dont le rendement est inconnu. 200 442 sont qualifiés, 832 restent invalides
  (825 sorties absentes, cinq entrées absentes, deux ruptures suspectes).
- Le 10 septembre est ajouté suivant le contrat statique vérifié : 1 758 labels,
  dont 1 746 qualifiés. Les 128 lignes de l'étude sont recalculées par tranches
  de vingt séances. Les anciens labels et agrégats sont sauvegardés avant SQL.
- Aucune barre source, aucun modèle ni aucun batch planifié n'est modifié.

Nombre de dates à NULL dans cette fenêtre (128 dates) :

| Liste | Avant | Après | Dates renseignées après |
| --- | ---: | ---: | ---: |
| TOP réel | 128 | 128 | 0 |
| Intersection Oracle/ATR | 15 | 14 | 114 |
| TOP prédit, trié par amplitude réalisée | 103 | 102 | 26 |
| TOP prédit, ordre du score conservé | 103 | 102 | 26 |
| TOP ATR | 95 | 93 | 35 |

Exemple du **30 mars 2026** : les listes prédites et ATR sont renseignées ; le
TOP réel reste inconnu à cause de SEMR, dont la sortie attendue est le 28 avril.
La relecture EODHD de ce symbole s'arrête au 27 avril. Une radiation, une fusion
ou un rachat éventuels doivent être qualifiés séparément : ni report du dernier
cours, ni rendement zéro, ni retrait rétroactif du titre.

Les **14 dates du 11 au 30 septembre** n'ont pas encore atteint leur date de
disponibilité selon le contrat actuel, au 10 octobre. Le 11 septembre sort le
9 octobre et devient disponible le 12 octobre ; le 30 septembre sort le
28 octobre et devient disponible le 29 octobre. Elles nécessiteront un nouveau
calcul après maturité et acquisition des prix, sans promesse de complétude.

Archives :

- `artifacts/research/oracle_atr_null_repair/repair-20261010-prices-v1/`
  (plan, réponses EODHD, dates de sortie reçues/manquantes) ;
- `artifacts/research/oracle_atr_null_repair/repair-20261010-rebuild-v1/`
  (backups, rapports de labels, `report.json`, `run.log`) ;
- `artifacts/research/oracle_atr_null_repair/missing-report-20261010-v1/`
  (`dates.json` : motifs et sélections manquantes par date ;
  `missing_prices.csv` : titres et sorties manquants ; `report.json` : synthèse).

Le nouvel outil `service.market.oracle_atr_missing_report` est en lecture seule.
Le correctif `service.market.oracle_atr_repair --rebuild-invalid-labels --apply`
recalcule explicitement les dates aux labels invalides, avec backup et univers
original. La présence de réserves ne déclenche aucune substitution automatique.
Tests ciblés : 77 tests réussis.

## Mode partiel et contrôle des nouvelles entrées — 10 octobre 2026

### Paramétrage et schéma

```yaml
oracle_atr_study:
  missing_returns_policy: partial  # partial | strict
new_entry_data_guard:
  min_sessions: 61
  publication_delay_minutes: 15
```

Migration Alembic : `0095_oracle_atr_partial_returns.py`. SQL équivalent :
`database/sql/ml/oracle_atr_partial_returns_migration.sql`. Le SQL de création
est à jour. Deux colonnes nouvelles : `missing_returns_policy` et
`movement_quality` (JSON). Elles sont ajoutées à la base US locale ; aucune base
CN/FR n'est modifiée. Le journal Alembic local étant encore en 0088, seules les
deux modifications de schéma ciblées sont appliquées : aucun estampillage
artificiel de la version ni lancement des autres migrations.

Dans **Régime Marché → Alimenter l’étude Oracle × ATR**, la case
**Ignorer les rendements manquants — listes partielles explicites** est cochée
par défaut conformément à la configuration. La commande expose
`--missing-returns-policy partial`. Décocher choisit `strict`.
`missing_returns_policy` enregistre **la règle choisie**, pas la complétude du
résultat. Il reste donc `partial` quand aucun rendement ne manque. Pour connaître
la qualité effective, lire `status`, `unknown_count` et les statuts/couvertures
de `movement_quality.lists`. Vérification en lecture seule du 10/10/2026 :
le 24/04/2023 est `COMPLETE`, avec 273 rendements connus par liste, zéro manquant
et 100 % de couverture, malgré la politique `partial`. Aucun recalcul ni
changement de politique n'est nécessaire pour cette ligne.
La nouvelle version est `oracle_atr_v5_partial_returns` (ou
`oracle_atr_v5_strict_returns`) : une ancienne ligne COMPLETE ne suffit donc pas
à sauter le nouveau calcul.

### Règles de qualité des listes

- Oracle et ATR : sélectionner les N=`evaluated_count` premiers **avant** de
  vérifier les rendements. Conserver seulement ceux connus, sans recruter un
  titre moins bien classé pour remplacer une inconnue.
- La liste `predicted_oracle_score_order_returns_pct` conserve l'ordre relatif
  des scores. Les positions originales sont archivées : si le premier est
  inconnu, la première valeur affichée peut correspondre au deuxième score.
- Les autres listes restent triées par amplitude réalisée, puis arrondies en
  pourcentages entiers signés. L'arrondi ne change pas leur classement.
- Le TOP réel partiel est **TOP20 réalisé parmi les titres évaluables**. Ce
  n'est pas le vrai TOP20 de l'univers complet : les titres manquants pourraient
  en faire partie. Sa couverture de référence est conservée séparément.
- `movement_quality.lists.<colonne>` donne : statut, nombre demandé/connu,
  couverture, symboles sélectionnés, symboles des valeurs dans leur ordre,
  positions originales, titres inconnus et motifs. Le TOP réel indique aussi
  la population de référence et ses manquants ; `selection_shortfall_count`
  signale un pool évaluable trop petit pour fournir N valeurs.
- Les D1/D10 restent ceux des labels du batch : aucune réaffectation des déciles
  sur les seuls titres connus. Les proportions ont toujours pour dénominateur
  `evaluated_count` ; leur couverture doit être lue avant toute comparaison.
- Une séance évaluable avec réserves devient `PARTIAL`. Sans résultat évaluable,
  elle reste `INCOMPLETE` et les listes à NULL, jamais des zéros inventés.
- La disponibilité H20 est vérifiée aussi contre le calendrier NYSE officiel,
  même si un label porte une date de disponibilité erronée. Une période non
  mature ne devient pas évaluable grâce au mode partiel.

### Recalcul réellement effectué

Fenêtre **30 mars–30 septembre 2026**, batch
`model-factory-20261003082853-e98332`, H20, fichier
`config/univers/univers_filtred_tradable.txt` tel que présent au lancement :
**1 790 titres**, empreinte
`27fb35535b1de472708606150a9d0b92b9c81bdb8dd51ae0a1e32dfd50f8255b`.

128 séances persistées par tranches de vingt : **114 PARTIAL / 14 INCOMPLETE**.
Chacune des cinq listes est renseignée sur les 114 séances évaluables. Les 14
séances du 11 au 30 septembre restent NULL pour maturité H20. Vérification SQL
en lecture seule : 570 listes vérifiées (taille, symboles, ordre, absence de
substitution, valeurs entières). Les anciennes études d'autres univers restent
intactes ; aucun titre n'est retiré par cette évolution.

Sauvegarde complète de la table et de son DDL avant migration :
`artifacts/research/oracle_atr_null_repair/partial-refresh-20261010-v1/`.
Premier lancement arrêté avant calcul par l'encodage de console Windows,
corrigé sans écriture d'agrégat. Recalcul terminé et rapport :
`artifacts/research/oracle_atr_null_repair/partial-refresh-20261010-v2/report.json`.
Le script de reprise bornée est `scripts/research/oracle_atr_partial_refresh.py`.
Aucun prix, label, modèle, batch planifié ni ordre broker n'a été modifié.

### Séparation impérative avec le live

Les listes sont des résultats **futurs et rétrospectifs**. Aucune n'est lue pour
autoriser une nouvelle entrée. Le contrôle opérationnel est indépendant :
voir [Contrôle strict des nouvelles entrées US](new_entry_data_guard.md).

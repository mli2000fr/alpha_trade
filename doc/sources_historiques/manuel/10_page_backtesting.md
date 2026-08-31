# 10. Page 🧪 Backtesting — préparer et tester une stratégie sur l'historique

> **But de ce chapitre** : produire un backtest reproductible, sans fuite
> d'information, à partir des mêmes données et règles que la stratégie. Le
> bouton final ne suffit pas : la qualité de l'historique, du Screener, du
> sentiment et du ML détermine la valeur du résultat.

## Ce que valide un bon backtest

Un backtest répond à une question précise : *avec les seules informations
connues à chaque date passée, la stratégie aurait-elle gardé une performance,
un risque et un nombre de transactions acceptables ?*

Il ne prédit pas un gain futur. Avant le paper trading, vérifiez au minimum :

- les frais et le slippage correspondent à votre compte ;
- les données sont historiques et **PIT** (*point in time* : aucune donnée
  future réutilisée) ;
- les résultats existent sur plusieurs régimes de marché ;
- les fenêtres hors échantillon du walk-forward restent cohérentes ;
- le nombre de trades est assez élevé pour ne pas conclure sur quelques
  coups de chance.

## Vue d'ensemble du parcours

| Ordre | Objectif | Page IHM | Action principale |
|---|---|---|---|
| 1 | Définir l'hypothèse et une période | 🧪 Backtesting | choisir les dates, capital et coûts |
| 2 | Importer les cours historiques | 🔄 Pipeline | auxiliaire **B3. Backfill historique EODHD** |
| 3 | Contrôler/nettoyer les données | 🔄 Pipeline | **Data Sanitizer Daily** |
| 4 | Reconstruire Screener et Selector à chaque date | 🧪 Backtesting | **🧱 Backfill scores history** |
| 5 | Publier l'univers tradable historique | 🔄 Pipeline | **🗓️ Publier l'univers tradable sur la période** |
| 6 | Construire ou vérifier le sentiment | 🔄 Pipeline puis 🧪 Backtesting | outils Event Sentiment, calibration et walk-forward |
| 7 | Entraîner/contrôler le ML | 🔄 Pipeline puis 🤖 ML / Prédictions | **Entraîner l'univers sélectionné** |
| 8 | Diagnostiquer puis retenir le Screener | 🧪 Backtesting puis 📊 Screening | **🧪 Lancer diagnose-screener** |
| 9 | Calibrer la fusion quant/ML/Kelly | 🧪 Backtesting | **🎯 Lancer calibrate-conviction-weights** |
| 10 | Lancer et analyser le replay final | 🧪 Backtesting | **🚀 Lancer le backtest** |

Les étapes 2 à 7 ne sont à refaire intégralement que lors de la création ou
de la mise à jour d'un historique. Les étapes 8 à 10 servent à comparer une
hypothèse ou une configuration.

## Exemple complet : stratégie swing US, 2022-01-01 à 2025-12-31

Cet exemple utilise un capital simulé de `4 000 $`, au plus 20 positions, des
données EODHD historiques et le mode `pipeline` pour privilégier la fidélité
au pipeline. Adaptez les dates, le capital et les coûts à votre propre cas ;
ne comparez jamais deux essais dont ces éléments diffèrent.

### 1. Fixer l'hypothèse avant de toucher aux paramètres

Écrivez d'abord une phrase, par exemple : « Je teste si le top 20 de
`final_score_sentiment`, avec ML et protections live-like, reste rentable
après coûts entre 2022 et 2025. »

Décidez une seule modification à la fois : un seuil Screener, un poids
sentiment, le nombre maximal de positions ou une règle de sortie. Gardez une
fenêtre finale hors échantillon que vous ne consultez pas pendant les
réglages.

### 2. Vérifier les prérequis techniques

1. Ouvrez **⚙️ Paramètres / Santé** puis l'onglet **Santé / Diagnostics**.
   Les accès DB et EODHD doivent être verts. Corrigez-les avant de lancer un
   historique.
2. Ouvrez **🔄 Pipeline**. Laissez le mode global sur `simulate` : le
   travail historique ne doit jamais envoyer d'ordre.
3. Dans **🧱 Bootstrap / maintenance Data Integrity**, ouvrez au besoin
   **B1. Import univers Alpaca** et cliquez **▶️ Lancer en arrière-plan**.
   Faites-le si l'univers de symboles n'a jamais été initialisé.

### 3. Importer les bars historiques

Les *bars* sont les OHLCV journaliers (ouverture, plus haut, plus bas,
clôture, volume). Le backtest exige la source historique
`eodhd_eod`; il échoue explicitement si elle manque.

1. Dans **🔄 Pipeline** → **🧱 Bootstrap / maintenance Data Integrity**,
   ouvrez **B3. Backfill historique EODHD**.
2. Saisissez une période qui couvre la période de test **et** le warm-up des
   indicateurs. Pour l'exemple, importez au moins `2020-01-01` à
   `2025-12-31`, afin de disposer de l'historique nécessaire avant 2022.
3. Gardez **B3 — mode écriture** activé afin de persister les bars dans la
   base, puis cliquez **▶️ Lancer en arrière-plan**. Attendez le statut
   `SUCCESS`/`COMPLETED` dans le **Centre d'exécution avancé**.
4. En cas de reprise ciblée, les blocs historiques de la page permettent de
   choisir une **Date de début**, une **Date de fin** et l'**Univers de
   symboles à synchroniser**. Ne lancez pas deux imports concurrents.

### 4. Assainir les données : Data Sanitizer Daily

Des trous de cotation, prix incohérents ou volumes anormaux faussent
directement les indicateurs et les performances.

1. Dans **🔄 Pipeline** → **🪜 Étapes pilotables**, ouvrez
   **2. Data Sanitizer Daily**.
2. Vérifiez la description et les dépendances dans le panneau, puis cliquez
   **▶️ Lancer en arrière-plan**.
3. Une fois terminé, ouvrez **📊 Screening**. Dans
   **1. Qualité amont & contexte pipeline**, contrôlez le dernier résumé de
   qualité avant de poursuivre.
4. Si le nettoyage indique des anomalies importantes, corrigez ou réimportez
   les données concernées ; ne les masquez pas par un réglage de stratégie.

### 5. Construire l'historique Stock Screener + Selector PIT

Le backtest `pipeline` ne doit pas utiliser les scores d'aujourd'hui pour une
date passée. Il lui faut un snapshot `stock_scores_history` pour chaque
séance, construit à partir de l'information disponible ce jour-là.

1. Ouvrez **🧪 Backtesting** → onglet **🧱 Backfill scores history**.
2. Renseignez **Date de début du backfill** et **Date de fin du backfill** ;
   pour l'exemple : `2022-01-01` et `2025-12-31`.
3. Saisissez le **Capital de référence pour le preset ($)** et choisissez le
   même **Preset capital PIT backfill** que celui du backtest final.
4. Pour un premier essai, renseignez **Limiter à N séances** avec `5` ou
   `10`. Vérifiez le résultat, puis retirez cette limite pour le run complet.
5. Gardez **Recalculer les dates déjà historisées** décoché sauf si vous
   avez changé le Screener, le Selector ou les données. Le cocher reconstruit
   les snapshots existants.
6. Cliquez **🧱 Lancer le backfill PIT** et attendez la fin du run dans le
   centre de suivi de cette page.

Le backfill rejoue le Screener puis l'Alpha Scanner (Selector) sur chaque
date. Il n'est pas équivalent à l'écran **📊 Screening**, qui sert à
consulter les résultats courants.

### 6. Publier l'univers tradable historique

Cette étape évite le biais de survivance : elle indique quels titres étaient
réellement éligibles à chaque date passée.

1. Dans **🔄 Pipeline** → **🪜 Étapes pilotables**, ouvrez
   **Publish Tradable Universe**.
2. Dans le bloc **📅 Publication historique sur période (backtest)**, saisissez
   les mêmes dates et le même **Preset capital** que dans le backfill.
3. Gardez la **Tolérance quote (jours)** cohérente avec les données
   disponibles. N'utilisez **Ignorer les quotes** que pour diagnostiquer une
   absence de quotes, jamais pour valider une stratégie exécutable.
4. Cliquez **🗓️ Publier l'univers tradable sur la période**.

Le panneau indique le nombre de séances NYSE publiées. Il requiert que le
snapshot PIT du Stock Screener existe déjà pour chaque séance : réalisez donc
le backfill de l'étape précédente avant cette publication.

### 7. Préparer et valider le sentiment

Le sentiment peut modifier le score et donc la sélection. Il doit être
historisé et calibré sans apprendre sur la période que l'on prétend tester.

1. Dans **🔄 Pipeline**, utilisez le panneau **News-Sentiement Traitement par
   étape** pour la fenêtre historique nécessaire :
   **Standard only** pour remplir le score standard, puis si nécessaire
   **Contextual only**, puis **Rebuild daily sentiment features only**.
2. Respectez l'ordre : import news brut, relevance des candidats, scoring
   standard, scoring contextuel, puis agrégation journalière ticker/secteur.
   Le bloc `7bis` est réservé au replay et à la maintenance ; il n'est pas
   lancé par le workflow cœur.
3. Dans **🧪 Backtesting** → **📰 Calibrate sentiment**, choisissez une
   période de calibration antérieure à votre test final, **Top N** et les
   **Horizons forward (CSV)**, puis cliquez
   **📰 Lancer calibrate-sentiment-weights**.
4. Validez la généralisation dans **🚶 Walk-forward sentiment** : choisissez
   les dates, `Min train days / fold` (par exemple `252`), `Test days / fold`
   (par exemple `63`), les coûts, le capital et le nombre de positions, puis
   cliquez **🚶 Lancer walk-forward-sentiment**.
5. Conservez les artefacts seulement si les folds hors échantillon sont
    stables. Le backtest détecte automatiquement les artefacts produits dans
    `artifacts/sentiment_walk_forward` ; vous pouvez alors laisser l'overlay
    walk-forward actif.

#### Exemple de découpage chronologique avec sentiment

Pour réserver `2025-01-01` à `2026-12-31` au backtest final, un découpage
cohérent est le suivant :

| Usage | Période | Action IHM |
|---|---|---|
| Apprentissage des poids sentiment | 2015-01-01 → 2020-12-31 | **🧪 Backtesting** → **📰 Calibrate sentiment** → **📰 Lancer calibrate-sentiment-weights** |
| Validation hors échantillon sentiment | 2021-01-01 → 2024-12-31 | **🧪 Backtesting** → **🚶 Walk-forward sentiment** → **🚶 Lancer walk-forward-sentiment** |
| Entraînement ML initial, incluant le régime COVID | 2015-01-01 → 2020-12-31 | **🔄 Pipeline** → **9. ML Train** → **Entraîner l'univers sélectionné** |
| Prédictions ML historiques PIT | 2021-01-01 → 2024-12-31 | **🔄 Pipeline** → **10. ML Predict** → **Prédire l'univers sélectionné** |
| Calibration et validation conviction | 2021-01-01 → 2024-12-31 | onglets **🎯 Calibrate conviction** puis **🔄 Walk-forward conviction** |
| Évaluation finale, jamais utilisée pour régler les paramètres | 2025-01-01 → 2026-12-31 | onglet **▶️ Backtest** → **🚀 Lancer le backtest** |

Dans **🚶 Walk-forward sentiment**, utilisez par exemple `Min train days /
fold = 504` et `Test days / fold = 126`. Le début `2021-01-01` laisse alors
deux années de séances pour apprendre dans les premiers folds, et les tests
hors échantillon couvrent ensuite 2023–2024.

#### Figer les poids sentiment retenus

Après validation, ne relancez plus **Calibrate sentiment** ni
**Walk-forward sentiment** avant le backtest final. L'IHM utilise
automatiquement en priorité
`artifacts/sentiment_walk_forward\latest_best_weights.json`. Ce fichier est
remplacé par le prochain walk-forward : le gel est donc actuellement
opérationnel, mais pas encore versionné dans l'IHM.

Pour mesurer la contribution du sentiment, faites ensuite deux runs finaux
identiques : **Mode sentiment** = `off`, puis `auto`. L'écart est une mesure
plus utile qu'un score isolé.

### 8. Préparer le ML et vérifier sa calibration

1. Dans **🔄 Pipeline** → **9. ML Train (Model Factory)**, ouvrez le panneau
   puis choisissez l'univers d'entraînement et cliquez
   **Entraîner l'univers sélectionné**. Pour la première constitution des
   modèles, utilisez un historique suffisamment long ; évitez d'entraîner
   avec des dates postérieures à la fenêtre évaluée.
2. Ouvrez **10. ML Predict** et cliquez **Prédire l'univers sélectionné**
   lorsque les prédictions PIT sont nécessaires.
3. Ouvrez **🤖 ML / Prédictions**. Contrôlez les runs, les métriques de
   validation et la calibration des probabilités. Un AUC élevé ne suffit pas
   si la precision des décisions `long` ou la calibration est médiocre.
4. Dans le backtest final, choisissez **Mode ML** = `auto` pour réutiliser
   les prédictions disponibles. Utilisez `rebuild-missing` seulement si les
   données et artefacts permettent une reconstruction PIT ; `off` sert de
   baseline sans ML.
5. Pour une analyse plus rigoureuse de la fusion quant/ML, ouvrez
   **🧪 Backtesting** → **🎯 Calibrate conviction**, définissez une période
   d'apprentissage puis cliquez **🎯 Lancer calibrate-conviction-weights**.
   Confirmez-la hors échantillon dans **🔄 Walk-forward conviction** avec
   `Min train days / fold`, `Test days / fold` et, si utile, `Step days`.

> **Calibration conviction/Kelly dans le backtest** : les outils
> `calibrate-conviction-weights` et `walk-forward-conviction` écrivent leurs
> résultats dans la table `weights_calibration_runs` (scope=`risk`). Le bouton
> **🚀 Lancer le backtest** expose désormais un contrôle opt-in
> **🎯 Calibration conviction/Kelly** (uniquement en Phase 2 `risk` ou
> `risk_execution`) :
>
> - **`off`** (défaut) : comportement standard, poids par défaut.
> - **`auto`** : charge automatiquement le dernier run éligible dont
>   `window_end ≤ start` du backtest (PIT-safe — aucun look-ahead). Si aucun
>   run éligible n'existe, le comportement standard est conservé avec un
>   avertissement explicite dans les logs et les métadonnées du run.
> - **`pinned`** : utilise un `run_id` explicite (sélectionnable dans
>   l'interface). Si `window_end > start`, le run échoue immédiatement pour
>   éviter tout look-ahead.
>
> Les poids appliqués (`score_weight`, `prediction_weight`, Kelly) et les
> métadonnées de calibration (run_id, window_start/end, statut) sont
> systématiquement enregistrés dans `report.json` sous la clé
> `conviction_calibration`, et dans les métadonnées du run IHM. Un résultat
> sans calibration explicite (mode `off`) est clairement distingué d'un
> résultat avec calibration appliquée.
>
> N'activez pas ce mode sans une calibration validée hors-échantillon
> (étapes 9 walk-forward conviction). Un run avec calibration in-sample
> produira un over-fit.

> Le choix **Stratégie ML PIT** =
> `walk-forward-train-then-predict` est actuellement explicitement non pris
> en charge et échoue volontairement. Utilisez les prédictions PIT
> persistées ou reconstruisez les manquantes selon les options disponibles.

### 9. Diagnostiquer et choisir la configuration Screener

Cette étape est recommandée quand vous modifiez des filtres de liquidité,
force relative, range ou le preset de capital.

1. Dans **🧪 Backtesting** → **🧪 Diagnose screener**, choisissez la période,
   le **Mode de balayage** (`oat` pour modifier un paramètre à la fois,
   `grid` pour comparer des combinaisons) et le preset.
2. Lancez **🧪 Lancer diagnose-screener**.
3. Ouvrez **🎯 Recommend screener**, utilisez le même répertoire/preset puis
   cliquez **🎯 Lancer recommend-screener**.
4. Dans **📊 Screening** → **2. Source d'artefacts screener**, choisissez les
   artefacts et consultez l'onglet **🎯 Recommandations**. Ne retenez une
   recommandation qu'après sa validation walk-forward/finale, pas seulement
   parce qu'elle maximise le Sharpe in-sample.

### 10. Lancer le backtest final

1. Ouvrez **🧪 Backtesting** → **▶️ Backtest**.
2. Dans **Preset de configuration**, choisissez `pipeline_live_like` ou
   `production_parity` pour rejouer un comportement proche du pipeline ; puis
   cliquez **Préremplir les options du backtest**. Sinon, renseignez chaque
   paramètre manuellement.
3. Saisissez **Date de début**, **Date de fin**, **Capital initial ($)** et
   le même **Preset capital PIT** que pendant le backfill.
4. Laissez **Aligner TP/SL/trailing sur la logique live** activé si l'objectif
   est la parité. Sinon seulement, définissez les protections fixes.
5. Renseignez des **Commission (bps)** et **Slippage explicite (bps)**
   prudents, ainsi que **Max positions**, le type de compte et `Swing only`
   s'ils correspondent au compte réel.
6. Choisissez **Mode moteur** = `pipeline`, **Mode PIT scores** = `exact` et
   une source de score cohérente, par exemple `final_score_sentiment`.
   `asof_latest` est un secours pour explorer un historique incomplet, pas le
   réglage de validation principal.
7. Gardez **Désactiver l'overlay walk-forward** décoché après une validation
   réussie des poids ; cochez-le uniquement pour comparer l'effet de cet
   overlay. Activez au besoin **Afficher le préflight couverture ML PIT**.
8. Cliquez **🚀 Lancer le backtest**. Consultez l'avancement, les logs et les
   artefacts depuis le centre de suivi de la page.

## Lire et décider à partir des résultats

Comparez une baseline simple, la variante sentiment, la variante ML et la
version complète avec exactement les mêmes dates, capital, coûts et limites.

| Indicateur | À examiner |
|---|---|
| CAGR / rendement | rendement après frais, pas un rendement brut |
| Sharpe et Sortino | régularité du rendement et pénalisation des baisses |
| Max drawdown | perte maximale supportable par votre capital et votre discipline |
| Nombre de trades | solidité statistique ; une poignée de trades ne prouve rien |
| Win rate et payoff | à lire ensemble, jamais séparément |
| Folds walk-forward OOS | stabilité hors échantillon, pas le meilleur fold |
| Écart avec/sans ML ou sentiment | contribution marginale réelle de chaque composant |

Ne promouvez pas une stratégie parce qu'un seul paramètre donne le meilleur
Sharpe. Préférez un plateau de paramètres voisins, des folds OOS cohérents,
des coûts pessimistes et une baisse maximale que vous accepteriez réellement.

## Checklist avant paper trading

- [ ] Bars EODHD, nettoyage et snapshots PIT couvrent toute la période.
- [ ] Univers tradable historique publié pour chaque séance.
- [ ] Screener/Selector, sentiment et ML ont été comparés à une baseline.
- [ ] Les poids sentiment et conviction ont été validés en walk-forward,
      sans réutiliser les folds test pour les régler.
- [ ] Frais, slippage, compte cash/margin, positions et protections reflètent
      le compte paper envisagé.
- [ ] Les résultats sont robustes sur une période hors échantillon et le
      drawdown est acceptable.
- [ ] La stratégie est testée ensuite en `paper`, avant tout passage `live`.

## Pièges courants

- **Backtest sans warm-up** : les indicateurs de début de période sont
  incomplets. Importez des bars antérieurs à la première date testée.
- **Scores actuels sur le passé** : utilisez le backfill PIT et le moteur
  `pipeline`, pas seulement la table de scores courante.
- **Optimisation sur le test** : chaque essai sur la même période finale
  réduit sa valeur hors échantillon.
- **Coûts trop faibles** : ajoutez commission et slippage réalistes.
- **Sentiment ou ML sans baseline** : comparez `off` et `auto`.
- **Walk-forward désactivé par défaut** : ne cochez
  **Désactiver l'overlay walk-forward** que pour une comparaison contrôlée.
- **Passage live après un bon graphique** : un backtest est suivi d'une phase
  paper, pas d'un ordre réel.

## Pour aller plus loin

- [04_page_pipeline.md](04_page_pipeline.md) — détails des étapes Pipeline
  et du traitement Event Sentiment.
- [05_page_screening.md](05_page_screening.md) — consulter les candidats et
  les artefacts Screener.
- [06_page_ml_predictions.md](06_page_ml_predictions.md) — métriques et
  gouvernance des modèles.
- [11_page_parity.md](11_page_parity.md) — vérifier la parité Backtest ↔
  Live.

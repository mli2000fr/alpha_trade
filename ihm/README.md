# IHM Opérateur — Alpha Trade

Dashboard de supervision Streamlit pour le pipeline de trading algorithmique Alpha Trade.

## Prérequis

- Python ≥ 3.12
- Variables d'environnement MySQL optionnelles : `LOGIN_DB`, `PASSWORD_DB`
- MySQL démarré avec la base `alpha_trade`
- Dépendances installées : `pip install -r requirements.txt`

## Lancement

```powershell
python -m streamlit run ihm/app.py
```

L'application s'ouvre par défaut sur `http://localhost:8501`.

## Connexion base de données

L'IHM peut maintenant se connecter à MySQL de deux façons :

1. via les variables d'environnement `LOGIN_DB` / `PASSWORD_DB` ;
2. via le formulaire **🗄️ Connexion DB** disponible dans la sidebar et dans la page **⚙️ Paramètres / Santé**.

Vous pouvez y renseigner :

- l'hôte MySQL ;
- le nom de la base ;
- le login ;
- le mot de passe.

Cela évite que les pages `Execution`, `Corporate Actions`, `ML`, etc. paraissent vides quand les identifiants système ne sont pas définis.

## Structure des pages

La sidebar est ordonnée **de haut en bas selon le flux opératoire principal** :

`🏠 Vue d'ensemble` → `🔄 Pipeline` → `📊 Screening` → `🤖 ML / Prédictions` → `⚖️ Risk` → `🚀 Execution` → `📑 Corporate Actions`

Les pages **hors workflow quotidien** sont volontairement regroupées en fin de navigation :

`🧪 Backtesting` → `🗃️ Administration DB` → `⚙️ Paramètres / Santé`

| Page | Description |
|---|---|
| 🏠 Vue d'ensemble | KPI, alertes, top candidats, santé DB |
| 🔄 Pipeline | Workflow quotidien 1→14 + steps auxiliaires Data Integrity (`import_alpaca_assets`, `update_sector`), lancement en arrière-plan, arrêt, historique, comparaison, téléchargement des logs et résumés métier |
| 📊 Screening | Table `stock_scores` avec filtres (symbole, secteur, candidat, score, sentiment) + lecture directe des recommandations screener par objectif (robuste, offensif, bear, exécutable) |
| 🤖 ML / Prédictions | Runs training, métriques, prédictions LSTM |
| ⚖️ Risk | Décisions de risque, portefeuille cible, synthèse par secteur |
| 🚀 Execution | Vue canonique run-scopée : targets snapshot, requests, ordres broker, fills, positions/lots, TCA, réconciliation ; contexte compte en lecture secondaire |
| 📑 Corporate Actions | Événements CA, applications, dividendes cumulés |
| 🧪 Backtesting | Formulaire complet des commandes `backtesting run`, `backfill-scores-history`, `diagnose-screener` et `recommend-screener`, lancement en arrière-plan, logs centralisés, KPIs auto-rafraîchis et graphique live des artefacts |
| 🗃️ Administration DB | Outils d'inspection / maintenance SQL et plan de vidage contrôlé |
| ⚙️ Paramètres / Santé | Variables d'env, connexion DB, dépendances, version Python |

## Pilotage des pipelines

La page **🔄 Pipeline** permet désormais :

- de lancer le **workflow quotidien complet 1→14** dans l'ordre métier ;
- de lancer aussi des steps **hors workflow** pour le bootstrap / la maintenance Data Integrity ;
- de lancer une étape **en arrière-plan** sans bloquer la navigation dans l'IHM ;
- d'**arrêter** un run actif lancé depuis l'interface ;
- de consulter un **historique centralisé** des exécutions IHM ;
- de comparer deux runs et leurs logs ;
- de filtrer l'affichage des logs par **`stdout` / `stderr` / `tout`** ;
- de **télécharger** les fichiers de logs produits par chaque run.

Le bloc de paramètres expose aussi les options réellement supportées côté backend pour :

- `Alpha Scanner` (`chunk-size`, `selection-size`, `max-workers`, seuils stricts de liquidité/prix/RS/ATR/spread/earnings, `sector-cap-ratio`, `log-level`) ;
- `event_sentiment` (`start-utc`, `end-utc`, `symbols`) ;
- `signal_aggregator` (`trade-date`, `all-symbols`, `sentiment-weight`, `macro-weight`, `lookback-days`, `min-news-count`, `time-decay-half-life-days`, `log-level`) ;
- `sync_latest_quotes` (`limit`, `batch-size`) ;
- `sync_earnings_calendar` (`from-date`, `to-date`, `limit`, `sleep-seconds`) ;
- `update_sector` (`limit`, `sleep-seconds`, `log-every`).

Pour `Alpha Scanner`, l'IHM transmet explicitement les valeurs affichées au launcher `python -m selector.alpha_scanner ...` afin de reproduire le profil partagé strict `STRICT_SWING_CASH_FILTERS` ou de le surcharger proprement. Dans cette UI, `0` sur `max workers` signifie **auto**.

Pour `event_sentiment`, laisser les symboles vides signifie : reprendre automatiquement l'univers candidat `stock_scores.is_candidate = 1`. Pour `signal_aggregator`, la page réutilise le champ global `trade date` quand il est renseigné et calcule le poids quantitatif implicite `1 - sentiment_weight - macro_weight` comme le backend.

La carte `Alpha Scanner` inclut également un diagnostic de dépendances métier pour `stock_quote_snapshots` et `stock_earnings_calendar` :

- badge visuel par step de sync ;
- métriques `latest_date`, `% couverture`, `N symboles` ;
- seuils vert / orange / rouge éditables depuis la page `⚙️ Paramètres / Santé` (et toujours accessibles depuis `🔄 Pipeline`) ;
- presets applicables en un clic : `Swing Cash Pro`, `Agressif`, `Tolérant` ;
- croisement explicite `style opératoire × régime de marché` (`normal`, `faible`, `très sélectif`) ;
- expander expliquant les états rouge/orange ;
- commandes correctives et boutons d'action rapide pour relancer les deux syncs ;
- bouton `Alpha Scanner` réellement désactivé quand **les deux** dépendances sont rouges ;
- message post-succès rappelant que le cache IHM peut nécessiter ~60s, avec option `Rafraîchir maintenant`.

Le même diagnostic est aussi affiché en **lecture seule** dans les pages **🏠 Vue d'ensemble** et **📊 Screening** pour rendre immédiatement visible l'état des dépendances du scan strict.

Les valeurs par défaut proposées sont orientées **swing cash pro** :

- `Sync Latest Quotes` : orange si couverture < `85%`, rouge si < `60%`, orange si snapshot > `1` jour, rouge si > `3` jours ;
- `Sync Earnings Calendar` : orange si couverture < `15%`, rouge si < `5%`, orange si horizon futur < `14` jours, rouge si < `7` jours.

La page `⚙️ Paramètres / Santé` permet aussi d'appliquer un preset selon **deux axes simultanés** :

- **style opératoire** : `Swing Cash Pro` / `Agressif` / `Tolérant` ;
- **régime de marché** : `Marché normal` / `Marché faible` / `Marché très sélectif`.

Exemple : `Agressif × Marché faible` ou `Swing Cash Pro × Marché très sélectif`.

Quand un script écrit un résumé structuré préfixé par `::alpha_trade_run_summary::`, l'IHM l'extrait automatiquement pour alimenter :

- les cartes de résumé métier du run ;
- l'agrégation du workflow parent ;
- les blocs récents de `Overview` et `Screening`.

Cela couvre notamment `stock_screener` et `Alpha Scanner`, ce qui permet d'afficher côté IHM des métriques comme la taille de sélection demandée, le nombre de titres retenus, le nombre de secteurs couverts, le fill ratio ou encore le cap sectoriel utilisé.

Cela couvre aussi `event_sentiment` et `signal_aggregator`, avec des métriques comme le nombre de symboles résolus, les articles fetchés/landed, les lignes de features journalières générées, le nombre de symboles mis à jour par la fusion sentiment ou encore le score sentiment moyen/max agrégé.

Les logs IHM sont persistés sous `artifacts/ihm_pipeline_runs/`.

Les runs de backtesting lancés depuis l'IHM sont persistés sous `artifacts/ihm_backtesting_runs/`.

## Focus page Exécution

La page **🚀 Execution** privilégie désormais la lecture des tables canoniques de la chaîne d'exécution pour le `exec_run_id` sélectionné :

- `execution_targets_snapshot`
- `execution_order_requests`
- `execution_broker_orders`
- `execution_broker_fills`
- `execution_positions`
- `execution_position_lots`
- `execution_reconciliation_results`

Le contexte plus large du compte (positions broker les plus récentes, positions/lots reconstruits au scope compte) reste affiché dans des zones secondaires explicites afin d'éviter de mélanger la vérité du run avec un état de compte plus global.

## Recommandations screener côté dashboard

Quand les artefacts suivants existent dans `artifacts/screener_diagnostics/` :

- `scenario_recommendations_by_objective.csv`
- `recommendation_summary_by_objective.json`
- `metadata.json`

l'IHM expose automatiquement :

- un **résumé compact** sur la page **🏠 Vue d'ensemble** ;
- un **bloc détaillé** sur la page **📊 Screening** avec les leaders par objectif et le leaderboard phase 7.

Cette phase 8 ne relance pas le diagnostic depuis l'interface :
elle **lit les artefacts existants** produits par `python -m backtesting diagnose-screener` ou `python -m backtesting recommend-screener`.

## Lancement screener depuis l'IHM

La page **🔄 Pipeline** expose désormais aussi l'étape quotidienne `stock_screener` avec les options backend réellement disponibles (`chunk-size`, `max-workers`, `benchmark`, seuils de liquidité/RS/range, fenêtre de passe 1, mode 2 passes).

En complément, la page **🧪 Backtesting** permet aussi de lancer directement depuis Streamlit :

- `python -m backtesting diagnose-screener`
- `python -m backtesting recommend-screener`

Chaque lancement :

- s'exécute en arrière-plan ;
- alimente le même centre de logs/historique que les autres runs backtesting ;
- peut réécrire les artefacts sous `artifacts/screener_diagnostics/` pour rafraîchir automatiquement la page **📊 Screening**.

## Limitations connues

- **Pilotage encadré** : la page Pipeline peut lancer/arrêter des sous-processus, mais les autres pages restent orientées supervision
- Si la DB est indisponible, les pages affichent un diagnostic clair et un formulaire de connexion
- Si une table SQL n'existe pas encore, la page correspondante affiche un message indiquant un schéma ou une migration manquante
- Le cache Streamlit est configuré à 60 secondes (TTL) sur les requêtes DB


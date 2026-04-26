# IHM — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `ihm/` et les commandes utiles pour :

- lancer l'interface opérateur Streamlit,
- superviser les modules du pipeline Alpha Trade,
- piloter certains traitements en arrière-plan depuis l'interface,
- diagnostiquer pourquoi une page paraît vide ou incomplète.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `ihm/__init__.py` | Package Python |
| `ihm/app.py` | Point d'entrée Streamlit et routage des pages |
| `ihm/README.md` | Documentation rapide de l'IHM |
| `ihm/pages/overview.py` | Vue d'ensemble, KPI et statut global |
| `ihm/pages/pipeline.py` | Pilotage du workflow quotidien, des steps auxiliaires Data Integrity et du centre d'exécution |
| `ihm/pages/backtesting.py` | Pilotage du backtesting et du backfill depuis l'IHM |
| `ihm/pages/screening.py` | Consultation `stock_scores` |
| `ihm/pages/risk.py` | Décisions de risque et portefeuille cible |
| `ihm/pages/execution.py` | Runs d'exécution, événements, fills et positions broker |
| `ihm/pages/corporate_actions.py` | Événements CA, applications et cash ledger |
| `ihm/pages/ml.py` | Runs d'entraînement et prédictions ML |
| `ihm/pages/settings.py` | Paramètres, santé, diagnostics environnement |
| `ihm/services/pipeline_runner.py` | Construction et pilotage des sous-processus pipeline |
| `ihm/services/backtesting_runner.py` | Lancement et suivi des runs backtesting |
| `ihm/services/process_registry.py` | Registre des processus et historique IHM |
| `ihm/services/db.py` | Accès DB côté IHM |
| `run.py` | Lanceur racine recommandé : `python run.py` |

### Pages disponibles

L'application référence les pages suivantes :

- Vue d'ensemble
- Pipeline
- Backtesting
- Screening
- Risk
- Execution
- Corporate Actions
- ML / Prédictions
- Paramètres / Santé

---

## 2. Prérequis

### 2.1 Dépendances et environnement

#### Obligatoires

- Python 3.12+
- `streamlit`
- dépendances du projet installées

#### Recommandés

- base MySQL accessible
- variables d'environnement DB définies, ou saisie via le formulaire IHM

### 2.2 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

L'IHM peut aussi fonctionner sans ces variables si l'utilisateur renseigne la connexion DB via les formulaires prévus dans la sidebar et la page paramètres.

### 2.3 Répertoires d'artefacts utilisés

- `artifacts/ihm_pipeline_runs/`
- `artifacts/ihm_backtesting_runs/`

Ces dossiers servent à historiser les runs lancés depuis l'interface et leurs logs.

---

## 3. Commandes utiles

### Lancement recommandé depuis la racine du projet

```powershell
python run.py
```

### Lancement manuel équivalent

```powershell
python -m streamlit run ihm/app.py
```

### URL locale par défaut

```text
http://localhost:8501
```

---

## 4. Comment fonctionne le module

### 4.1 Point d'entrée

`ihm/app.py` :

1. configure Streamlit ;
2. affiche la sidebar ;
3. propose le formulaire de connexion DB ;
4. résout le compte Alpaca sélectionné s'il y en a plusieurs ;
5. route vers la page choisie.

### 4.2 Sélecteur multi-comptes

Si plusieurs comptes Alpaca sont configurés dans `service.alpaca.accounts.AccountRegistry`, l'IHM affiche un sélecteur dans la sidebar.

Les pages liées à l'exécution, au risque ou aux corporate actions peuvent alors filtrer les données par `account_id`.

### 4.3 Pilotage de pipeline

La page `Pipeline` s'appuie principalement sur :

- `ihm/services/pipeline_runner.py` pour décrire les steps disponibles et construire les commandes ;
- `ihm/services/process_registry.py` pour lancer les sous-processus en arrière-plan, suivre leurs logs et historiser les runs ;
- `ihm/services/run_summary.py` pour normaliser les résumés métier affichés dans l'IHM.

La page est désormais organisée en **3 zones fonctionnelles**.

#### 4.3.1 Paramètres d'exécution partagés

Le bloc `⚙️ Paramètres d'exécution` regroupe les options communes à plusieurs steps :

- `trade_date / as-of` ;
- equity du module Risk ;
- mode d'exécution `simulate|paper|live` ;
- `risk_run_id` optionnel pour Execution ;
- options broker/exécution (`allow_outside_rth`, `auto_rebalance`, type de compte, règle PDT, `swing_only`) ;
- options `modelFactory` (accélérateur, challengers, modèle global, sélection du champion, optimisation seuil/target) ;
- options `Screener` pour `stock_screener` ;
- options `Data Integrity` pour quotes / earnings / fondamentaux.

Pour `Execution`, l'IHM expose explicitement :

- type de compte `margin|cash` ;
- règle `PDT auto|off` ;
- option `swing_only` ;
- rappel métier de l'impact de ces choix sur le buying power et le comportement des exits.

Pour la zone `Data Integrity`, l'IHM expose désormais les options backend réellement disponibles :

- `sync_latest_quotes`
  - `--limit`
  - `--batch-size`
- `sync_earnings_calendar`
  - `--from-date`
  - `--to-date`
  - `--limit`
  - `--sleep-seconds`
- `update_sector`
  - `--limit`
  - `--sleep-seconds`
  - `--log-every`

Pour la zone `Screener`, l'IHM expose aussi les options backend réellement disponibles côté `python -m screener.stock_screener` :

- `--chunk-size`
- `--max-workers` (`0` dans l'IHM = auto)
- `--benchmark`
- `--liquidity-threshold-usd`
- `--min-relative-strength-index`
- `--historical-range-lookback-days`
- `--min-historical-range-score`
- `--first-pass-window-days`
- `--disable-two-pass-loading` (piloté par une checkbox inverse "chargement en 2 passes")

Important :

- dans l'IHM, une valeur `0` sur un champ `limit` signifie **univers complet éligible** ;
- si la fenêtre custom earnings n'est pas activée, la commande conserve le défaut backend `J-7 -> J+30`.

#### 4.3.2 Workflow quotidien 1 → 14

Le workflow complet exécute automatiquement, dans cet ordre :

1. `import_alpaca_bar`
2. `data_sanitizer_daily`
3. `stock_screener`
4. `sync_latest_quotes`
5. `sync_earnings_calendar`
6. `alpha_scanner`
7. `sentiment_pipeline`
8. `signal_aggregator`
9. `ml_train`
10. `ml_predict`
11. `risk_management`
12. `execution`
13. `corporate_actions_sync`
14. `corporate_actions_apply`

Le workflow 1→14 correspond au pipeline quotidien opérable depuis l'IHM.

Le watcher de protections n'est **pas** la 15e étape du workflow. Il apparaît désormais dans la page `Pipeline` comme un bloc pédagogique **12.bis** placé juste après `Execution` pour rappeler :

- quand le lancer ;
- dans quel ordre le positionner ;
- et comment le lancer selon le contexte (run once, service local, Task Scheduler, NSSM).

Le bloc affiche aussi un lien explicite vers `doc/watcher.md` afin qu'un nouvel opérateur puisse ouvrir immédiatement le guide dédié depuis l'IHM.

Règle simple :

- `1 → 11` préparent la journée ;
- `12 execution` crée les protections à surveiller ;
- le **watcher** se lance juste après `Execution` ;
- `13 → 14 corporate actions` peuvent s'exécuter pendant que le watcher tourne.

L'étape `Alpha Scanner` continue d'être lancée via :

```powershell
python -m selector.alpha_scanner
```

L'IHM expose désormais les options CLI opérationnelles réellement supportées par ce point d'entrée, notamment :

- `chunk-size`
- `selection-size`
- `max-workers`
- `liquidity-threshold`
- `min-close`
- `max-volatility-ratio`
- `min-relative-strength-index`
- `min-high-52w-proximity`
- `min-weekly-trend-score`
- `min-atr-pct-20`
- `max-atr-pct-20`
- `min-market-cap`
- `min-beta-126`
- `max-spread-bps`
- `earnings-blackout-days`
- `max-anomaly-count`
- `sector-cap-ratio`
- `log-level`

Point important :

- `0` sur `max workers` dans l'IHM signifie **auto** ;
- le profil partagé `STRICT_SWING_CASH_FILTERS` reste la base implicite côté backend, et les valeurs saisies dans l'IHM sont transmises explicitement pour reproduire ou surcharger ce profil ;
- le launcher IHM consomme aussi désormais le `run_summary` structuré de `alpha_scanner` (taille demandée, titres retenus, secteurs, fill ratio, workers, cap sectoriel).

L'IHM exécute donc bien `sync_latest_quotes` puis `sync_earnings_calendar` **avant** `alpha_scanner`, ce qui prépare `stock_quote_snapshots` et `stock_earnings_calendar` pour les filtres aval (`spread_bps`, `earnings_blackout`).

Les étapes suivantes du workflow, `sentiment_pipeline` puis `signal_aggregator`, sont elles aussi alignées sur les points d'entrée backend :

```powershell
python -m event_sentiment ...
python -m event_sentiment.signal_aggregator ...
```

Pour `sentiment_pipeline`, l'IHM expose désormais les options réellement supportées par `event_sentiment.cli` :

- `--start-utc`
- `--end-utc`
- `--symbols`

Pour `signal_aggregator`, l'IHM expose désormais :

- `--trade-date`
- `--all-symbols`
- `--sentiment-weight`
- `--macro-weight`
- `--lookback-days`
- `--min-news-count`
- `--time-decay-half-life-days`
- `--log-level`

Points importants :

- si `symbols` est laissé vide côté IHM, `event_sentiment` recharge automatiquement les candidats depuis `stock_scores.is_candidate = 1` ;
- `signal_aggregator` réutilise le champ global `trade date` de la page quand il est renseigné ;
- le poids quantitatif reste implicite et vaut `1 - sentiment_weight - macro_weight`, conformément au backend ;
- l'IHM consomme aussi désormais les `run_summary` structurés de `sentiment_pipeline` et `signal_aggregator` pour afficher des métriques comme `resolved_symbols`, `fetched_articles`, `loaded_symbols`, `updated_symbols`, `signal_active_symbols` ou `avg_final_score_sentiment` dans `Pipeline`, `Overview` et `Screening`.

La carte `Alpha Scanner` expose aussi un **diagnostic de dépendances** basé sur le contenu réel des tables SQL :

- badge visuel pour `Sync Latest Quotes` et `Sync Earnings Calendar` ;
- métriques exactes `latest_date`, `% couverture` et `N symboles` ;
- seuils vert / orange / rouge éditables depuis la page `Settings` (et conservés aussi dans `Pipeline`) ;
- presets applicables en un clic : `Swing Cash Pro`, `Agressif`, `Tolérant` ;
- sélecteur de régime de marché : `normal`, `faible`, `très sélectif` ;
- expander expliquant pourquoi l'état est `rouge` / `orange` ;
- rappel des commandes correctives :
  - `python -m dataIntegrityEngine.sync_latest_quotes`
  - `python -m dataIntegrityEngine.sync_earnings_calendar`
- actions rapides directement dans l'IHM pour lancer ces deux synchronisations.

Règle d'UX opérateur : si **les deux** dépendances sont rouges en même temps, le bouton `Lancer en arrière-plan` de `Alpha Scanner` est réellement désactivé jusqu'à correction. Si une seule dépendance est dégradée, l'IHM affiche un avertissement mais ne verrouille pas le scan.

Après succès d'une action rapide, l'IHM rappelle que les indicateurs peuvent rester mis en cache environ **60 secondes** (`st.cache_data(ttl=60)`) et propose un bouton `Rafraîchir maintenant` pour invalider le cache SQL côté dashboard.

Ce même diagnostic est réutilisé en lecture seule dans les pages `Overview` et `Screening`, afin d'exposer les mêmes badges, métriques et commandes correctives hors de la page `Pipeline`.

Les valeurs par défaut livrées dans l'IHM sont orientées **swing cash pro** :

- `Sync Latest Quotes` : orange si couverture < `85%`, rouge si couverture < `60%`, orange si snapshot > `1` jour, rouge si > `3` jours ;
- `Sync Earnings Calendar` : orange si couverture < `15%`, rouge si couverture < `5%`, orange si horizon futur < `14` jours, rouge si < `7` jours.

L'IHM ne force donc pas un choix "style OU marché" : le preset effectif peut être le croisement des deux axes, par exemple `Swing Cash Pro × Marché très sélectif` ou `Tolérant × Marché faible`.

#### 4.3.3 Steps auxiliaires Data Integrity hors workflow

La page expose aussi une zone `Bootstrap / maintenance Data Integrity` avec deux steps additionnels, **hors workflow quotidien 1→14** :

- `B1. Import univers Alpaca`
  - commande : `python -m dataIntegrityEngine.import_alpaca_assets`
  - usage : bootstrap ou rafraîchissement de `stock_metadata`
- `B2. Mise à jour fondamentaux`
  - commande : `python -m dataIntegrityEngine.update_sector ...`
  - usage : enrichissement `sector` / `market_cap` via Finnhub

Ces steps sont utiles lors :

- d'une remise à zéro de la base ;
- d'un rebootstrap de l'univers ;
- d'un rattrapage ciblé des fondamentaux.

Ils sont volontairement séparés du workflow quotidien pour ne pas les rejouer systématiquement chaque jour.

#### 4.3.4 Centre d'exécution & d'investigation

La page `Pipeline` embarque aussi un centre live de supervision :

- liste des runs actifs ;
- arrêt manuel d'un run ou d'un workflow ;
- inspection des logs `stdout`, `stderr` ou combinés ;
- comparaison de deux runs ;
- téléchargement des logs ;
- historique centralisé persistant des runs IHM.

Les runs sont persistés sous :

- `artifacts/ihm_pipeline_runs/` pour les pipelines ;
- `artifacts/ihm_backtesting_runs/` pour le backtesting.

#### 4.3.5 Résumés métier structurés

Quand un script écrit sur stdout une ligne préfixée par :

```text
::alpha_trade_run_summary::
```

le registre IHM extrait ce JSON et l'associe au run.

Cela permet ensuite :

- l'affichage d'un résumé métier compact dans la page `Pipeline` ;
- l'agrégation run-level sur le workflow parent ;
- l'exposition de métriques récentes dans `Overview` et `Screening`.

Les steps Data Integrity qui publient maintenant ce résumé structuré sont notamment :

- `import_alpaca_assets`
- `import_alpaca_bar`
- `data_sanitizer_daily`
- `update_sector`
- `sync_latest_quotes`
- `sync_earnings_calendar`

#### 4.3.6 Import manuel de news

Sous l'étape `Sentiment Pipeline`, l'IHM expose un sous-panneau `Import des news brutes` permettant de lancer :

```powershell
python event_sentiment/importe_news.py --start-date ... --end-date ...
```

Ce sous-run est utile pour réinjecter une plage de news spécifique avant de relancer le pipeline de sentiment.

#### 4.3.7 Bloc watcher post-exécution dans `Pipeline`

Entre l'étape `12. Execution` et les étapes `13-14` de Corporate Actions, la page `Pipeline` affiche désormais un bloc `12.bis` qui sert de mémo opérateur.

Il rappelle :

- que le watcher se lance **après** `Execution` ;
- qu'il peut tourner pendant les Corporate Actions ;
- quels modes de lancement privilégier (`once`, service local, Task Scheduler, NSSM) ;
- et quelles commandes utiliser pour un nouvel arrivant.

#### 4.3.8 Supervision Ops et packaging Windows

La page `Supervision Ops` ajoute maintenant une vue Windows **strictement read-only** pour le watcher :

- statut réel `Task Scheduler` ;
- statut réel du service Windows / NSSM ;
- sources de logs Windows détectées ;
- import lecture seule de ces logs ;
- métadonnées du bridge PowerShell allowlisté.

Important :

- l'IHM peut **superviser** le packaging Windows ;
- l'IHM ne peut pas **installer**, **désinstaller**, **start/stop** un service Windows externe ni exécuter du PowerShell arbitraire.

### 4.4 Pilotage du backtesting

La page `Backtesting` utilise des services dédiés pour :

- lancer `backtesting run`,
- lancer `backfill-scores-history`,
- suivre les logs et artefacts produits.

### 4.5 Nature de l'IHM

Le cockpit reste majoritairement orienté :

- **supervision**,
- **diagnostic**,
- **déclenchement contrôlé** de sous-processus.

Il ne remplace pas la logique métier des modules back-end eux-mêmes.

### 4.6 Page Execution

La page `Execution` affiche pour chaque `exec_run_id` :

- le statut global du run ;
- les événements et fills ;
- les positions broker ;
- et, quand disponible, le snapshot de contraintes appliquées (`account_type`, `PDT effectif`, `swing_only`, budget broker observé).

---

## 5. Pourquoi une page peut paraître vide

### 5.1 Problème de connexion DB

Causes fréquentes :

1. variables d'environnement DB absentes ;
2. MySQL indisponible ;
3. mauvais host / base / credentials saisis ;
4. schéma incomplet.

### 5.2 La table attendue n'existe pas encore

Certaines pages dépendent de tables spécifiques :

- `stock_scores` pour `Screening`
- `risk_decisions` / `portfolio_targets` pour `Risk`
- `execution_runs` et tables liées pour `Execution`
- tables CA pour `Corporate Actions`
- tables ML pour `ML`

Si ces tables sont absentes, la page doit surtout être comprise comme un indicateur de schéma manquant ou de pipeline non encore exécuté.

### 5.3 Aucun artefact IHM n'apparaît

Causes fréquentes :

1. aucun run n'a encore été lancé depuis l'IHM ;
2. le répertoire `artifacts/ihm_pipeline_runs/` ou `artifacts/ihm_backtesting_runs/` n'a pas encore été créé ;
3. le processus a échoué avant d'écrire ses logs.

---

## 6. Vérifications utiles

### Vérifier que Streamlit se lance correctement

```powershell
python run.py
```

### Vérifier que les répertoires d'artefacts IHM existent

```powershell
Get-ChildItem "C:\Users\MLI\PycharmProjects\alpha_trade\artifacts"
```

### Vérifier les pages disponibles dans le code

```powershell
Get-ChildItem "C:\Users\MLI\PycharmProjects\alpha_trade\ihm\pages"
```

### Vérifier les services de pilotage disponibles

```powershell
Get-ChildItem "C:\Users\MLI\PycharmProjects\alpha_trade\ihm\services"
```

---

## 7. Tests

### Tests ciblés IHM

```powershell
python -m pytest tests/test_app.py tests/test_run.py tests/test_ihm_pipeline_runner.py tests/test_ihm_backtesting_runner.py tests/test_ihm_metrics.py -q -o addopts=""

python -m pytest tests/test_ihm_process_registry.py tests/test_data_integrity_run_summaries.py -q -o addopts=""
```

### Tests des pages

```powershell
python -m pytest tests/test_pages_overview.py tests/test_pages_pipeline.py tests/test_pages_screening.py tests/test_pages_execution.py tests/test_pages_corporate_actions.py tests/test_pages_ml.py tests/test_pages_settings.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé pour un usage opérateur :

1. lancer l'IHM avec `python run.py` ;
2. valider la connexion DB depuis la sidebar ;
3. sélectionner le bon compte Alpaca si plusieurs sont configurés ;
4. utiliser la page `Pipeline` pour l'orchestration et la page `Backtesting` pour les runs research.

### Séquence recommandée

```powershell
python run.py
```


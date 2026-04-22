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
| `ihm/pages/pipeline.py` | Pilotage des étapes quotidiennes |
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

La page `Pipeline` s'appuie sur `ihm/services/pipeline_runner.py` pour construire les commandes des étapes :

1. import bars,
2. sanitize daily,
3. screener,
4. alpha scanner,
5. sentiment pipeline,
6. signal aggregator,
7. ml train,
8. ml predict,
9. risk management,
10. execution,
11. corporate actions sync,
12. corporate actions apply.

Pour l'étape `Execution`, l'IHM expose aussi les contraintes de compte/trading :

- type de compte `margin|cash` ;
- règle `PDT auto|off` ;
- option `swing_only`.

Pour l'étape `Alpha Scanner`, l'IHM lance désormais directement la commande standard suivante :

```powershell
python -m selector.alpha_scanner
```

Le workflow complet 1→12 réutilise exactement cette même commande pour l'étape 4. Le profil strict partagé `STRICT_SWING_CASH_FILTERS` est donc appliqué de manière implicite et homogène entre CLI, IHM et backfill PIT.

L'interface affiche un résumé explicite de ces contraintes avant lancement afin que l'opérateur comprenne pourquoi un run `cash` peut se comporter différemment d'un run `margin`.

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
Get-ChildItem "C:\Users\PC MLI\PycharmProjects\alpha_trade\artifacts"
```

### Vérifier les pages disponibles dans le code

```powershell
Get-ChildItem "C:\Users\PC MLI\PycharmProjects\alpha_trade\ihm\pages"
```

### Vérifier les services de pilotage disponibles

```powershell
Get-ChildItem "C:\Users\PC MLI\PycharmProjects\alpha_trade\ihm\services"
```

---

## 7. Tests

### Tests ciblés IHM

```powershell
python -m pytest tests/test_app.py tests/test_run.py tests/test_ihm_pipeline_runner.py tests/test_ihm_backtesting_runner.py tests/test_ihm_metrics.py -q -o addopts=""
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


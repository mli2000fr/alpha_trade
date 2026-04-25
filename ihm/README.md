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

| Page | Description |
|---|---|
| 🏠 Vue d'ensemble | KPI, alertes, top candidats, santé DB |
| 🔄 Pipeline | 12 étapes du pipeline quotidien (1→1a→2→…→6→6a→6b→7→8→8a), lancement en arrière-plan, arrêt, historique, comparaison et téléchargement des logs |
| 🧪 Backtesting | Formulaire complet des commandes `backtesting run` et `backfill-scores-history`, lancement en arrière-plan, logs centralisés, KPIs auto-rafraîchis et graphique live des artefacts |
| 📊 Screening | Table `stock_scores` avec filtres (symbole, secteur, candidat, score, sentiment) + lecture directe des recommandations screener par objectif (robuste, offensif, bear, exécutable) |
| ⚖️ Risk | Décisions de risque, portefeuille cible, synthèse par secteur |
| 🚀 Execution | Runs d'exécution, événements, fills, positions broker |
| 📑 Corporate Actions | Événements CA, applications, dividendes cumulés |
| 🤖 ML / Prédictions | Runs training, métriques, prédictions LSTM |
| ⚙️ Paramètres / Santé | Variables d'env, connexion DB, dépendances, version Python |

## Pilotage des pipelines

La page **🔄 Pipeline** permet désormais :

- de lancer une étape **en arrière-plan** sans bloquer la navigation dans l'IHM ;
- d'**arrêter** un run actif lancé depuis l'interface ;
- de consulter un **historique centralisé** des exécutions IHM ;
- de comparer deux runs et leurs logs ;
- de filtrer l'affichage des logs par **`stdout` / `stderr` / `tout`** ;
- de **télécharger** les fichiers de logs produits par chaque run.

Les logs IHM sont persistés sous `artifacts/ihm_pipeline_runs/`.

Les runs de backtesting lancés depuis l'IHM sont persistés sous `artifacts/ihm_backtesting_runs/`.

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

## Limitations connues

- **Pilotage encadré** : la page Pipeline peut lancer/arrêter des sous-processus, mais les autres pages restent orientées supervision
- Si la DB est indisponible, les pages affichent un diagnostic clair et un formulaire de connexion
- Si une table SQL n'existe pas encore, la page correspondante affiche un message indiquant un schéma ou une migration manquante
- Le cache Streamlit est configuré à 60 secondes (TTL) sur les requêtes DB


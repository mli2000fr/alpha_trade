# IHM Opérateur — Alpha Trade

Dashboard de supervision Streamlit pour le pipeline de trading algorithmique Alpha Trade.

## Prérequis

- Python ≥ 3.12
- Variables d'environnement : `LOGIN_DB`, `PASSWORD_DB` (MySQL)
- MySQL démarré avec la base `alpha_trade`
- Dépendances installées : `pip install -r requirements.txt`

## Lancement

```powershell
python -m streamlit run ihm/app.py
```

L'application s'ouvre par défaut sur `http://localhost:8501`.

## Structure des pages

| Page | Description |
|---|---|
| 🏠 Vue d'ensemble | KPI, alertes, top candidats, santé DB |
| 🔄 Pipeline | 10 étapes du pipeline quotidien (1→1a→2→…→8→8a) |
| 📊 Screening | Table `stock_scores` avec filtres (symbole, secteur, candidat, score, sentiment) |
| ⚖️ Risk | Décisions de risque, portefeuille cible, synthèse par secteur |
| 🚀 Execution | Runs d'exécution, événements, fills, positions broker |
| 📑 Corporate Actions | Événements CA, applications, dividendes cumulés |
| 🤖 ML / Prédictions | Runs training, métriques, prédictions LSTM |
| ⚙️ Paramètres / Santé | Variables d'env, connexion DB, dépendances, version Python |

## Limitations connues

- **Lecture seule** : aucune action destructive, aucun ordre soumis depuis l'IHM
- Si la DB est indisponible, les pages affichent un message d'erreur clair sans crash
- Si une table SQL n'existe pas encore, la page correspondante affiche "Aucune donnée disponible"
- Le cache Streamlit est configuré à 60 secondes (TTL) sur les requêtes DB


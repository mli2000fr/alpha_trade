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
| 🔄 Pipeline | 10 étapes du pipeline quotidien (1→1a→2→…→8→8a) |
| 📊 Screening | Table `stock_scores` avec filtres (symbole, secteur, candidat, score, sentiment) |
| ⚖️ Risk | Décisions de risque, portefeuille cible, synthèse par secteur |
| 🚀 Execution | Runs d'exécution, événements, fills, positions broker |
| 📑 Corporate Actions | Événements CA, applications, dividendes cumulés |
| 🤖 ML / Prédictions | Runs training, métriques, prédictions LSTM |
| ⚙️ Paramètres / Santé | Variables d'env, connexion DB, dépendances, version Python |

## Limitations connues

- **Lecture seule** : aucune action destructive, aucun ordre soumis depuis l'IHM
- Si la DB est indisponible, les pages affichent un diagnostic clair et un formulaire de connexion
- Si une table SQL n'existe pas encore, la page correspondante affiche un message indiquant un schéma ou une migration manquante
- Le cache Streamlit est configuré à 60 secondes (TTL) sur les requêtes DB


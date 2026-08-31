# 2. Premiers pas dans l'IHM — visite guidée

> Objectif : comprendre la structure de l'interface. **Aucun lancement** ici,
> on regarde uniquement.

## 2.1 Vue d'ensemble de l'écran

Quand l'IHM s'ouvre dans votre navigateur, l'écran est divisé en **2 zones** :

```
┌──────────────────┬─────────────────────────────────────────┐
│                  │                                         │
│   SIDEBAR        │                                         │
│   (à gauche)     │   ZONE PRINCIPALE                       │
│                  │   (le contenu de la page)               │
│   - menu         │                                         │
│   - compte       │                                         │
│   - DB           │                                         │
│                  │                                         │
└──────────────────┴─────────────────────────────────────────┘
```

## 2.2 La sidebar (menu de gauche)

Elle contient **6 sections** dépliables :

| Section | Pages | Quand l'utiliser |
|---|---|---|
| 🏠 **Accueil** | Vue d'ensemble | Démarrage de la journée, KPI |
| 🔄 **Workflow & Orchestration** | Pipeline · Supervision Ops | Lancer le cycle quotidien |
| 📈 **Trading** | Execution · Risk · Comptes Alpaca | Voir et gérer les ordres |
| 🔬 **Analyse & Recherche** | Screening · Backtesting · Parité · ML | Étudier la stratégie |
| ⚙️ **Configuration** | Paramètres / Santé | Ajuster les réglages |
| 🛡️ **Conformité & Admin** | Compliance & Audit · Tax · Sandbox health · Corporate Actions · DB Admin · Glossaire | Tâches périodiques |

> 💡 **Astuce** : utilisez en priorité la section **Accueil** pour vérifier
> l'état du système avant de lancer quoi que ce soit.

## 2.3 Le sélecteur de compte Alpaca

Toujours dans la sidebar (en haut). Si vous avez créé plusieurs comptes
Alpaca (par exemple un paper et un live), choisissez celui sur lequel vous
voulez travailler **avant** d'aller sur les pages Risk / Execution.

> ⚠️ Le compte sélectionné s'applique à **toutes** les pages. Vérifiez-le
> systématiquement avant un passage d'ordre.

## 2.4 Le formulaire de connexion à la DB

Si vous voyez « ❌ Base de données indisponible », cliquez sur l'icône
🔧 dans la sidebar, saisissez `login=alpha` / `password=choisissez_un_mdp`
(cf. [01_demarrage_rapide.md](01_demarrage_rapide.md)) et **Tester la connexion**.

## 2.5 Le bandeau d'environnement

En haut à droite de chaque page :

| Badge | Signification |
|---|---|
| 🟢 **PAPER** | Vous êtes en simulation Alpaca (aucun argent réel n'est engagé) |
| 🔴 **LIVE** | Vous êtes en argent réel (chaque ordre coûte de l'argent) |
| 🟡 **SIMULATE** | Pipeline en mode simulation locale (ne touche même pas le broker) |

> 🛑 **Avant chaque action sur la page Execution, regardez ce badge.**

## 2.6 La page d'accueil (Vue d'ensemble)

C'est la première page affichée. Elle contient :

1. **KPI globaux** : nombre de candidats, dernier run pipeline, dernier run
   d'exécution, P&L (gain/perte) du jour, etc.
2. **Statut du dernier pipeline** : ✅ vert si tout est OK, 🟠 orange si un
   step a échoué, 🔴 rouge si rien n'a tourné aujourd'hui.
3. **Top candidats du jour** : tableau des meilleures opportunités
   identifiées par le scanner.
4. **Diagnostic rapide** : alerte si une dépendance manque (provider down,
   etc.).

## 2.7 Codes couleur récurrents

| Couleur | Signification générale |
|---|---|
| 🟢 vert | OK, à jour, sain |
| 🟡 jaune | Avertissement, action recommandée mais non bloquante |
| 🟠 orange | Dégradé, à surveiller |
| 🔴 rouge | Bloquant, intervention requise |
| ⚪ gris | Absent, jamais exécuté |

## 2.8 Boutons fréquents

| Bouton | Effet |
|---|---|
| **Lancer** / **Run** | Exécute la commande |
| **Rafraîchir** | Recharge les données depuis la DB |
| **Annuler** | Coupe le processus en cours |
| **Voir logs** | Ouvre les logs détaillés |
| **Exporter CSV** | Télécharge les données affichées |

## 2.9 Mode avancé

Certaines pages ont en haut une case « **🔧 Mode avancé** ». **Laissez-la
décochée** au début : elle révèle des paramètres techniques inadaptés à un
débutant.

## 2.10 Et maintenant ?

- Avant tout lancement, lisez [03_workflow_quotidien.md](03_workflow_quotidien.md).
- Familiarisez-vous avec le vocabulaire : [30_glossaire_financier.md](30_glossaire_financier.md).
- Si vous avez ~2 000 €, lisez impérativement
  [20_gestion_petit_capital_2000eur.md](20_gestion_petit_capital_2000eur.md)
  **avant** votre premier pipeline.


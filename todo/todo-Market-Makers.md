# PROMPT POUR OPTIMISATION STRATÉGIQUE - SYSTÈME ALPHA TRADE

## CONTEXTE
Tu es un ingénieur expert en trading algorithmique et Python. L'objectif est d'optimiser le moteur "Alpha Trade" pour anticiper des anomalies saisonnières et macroéconomiques détectées en 2025 (notamment le creux d'avril-mai).

## ANALYSE DES DOCUMENTS FOURNIS
1. **DOC_FONCTIONNELLE.md** : Architecture Swing Trade sur actions US, exécution via Alpaca, scoring multi-facteurs (Sentiment + ML).
2. **DOC_TECHNIQUE.md** : Pipeline de backtesting, gestion des phases de fidélité, et structure des scripts (`run_execution.py`, `backfill-scores-history`).
3. **LOGS/EXPORT** : Détection d'un drawdown majeur en avril-mai 2025 lié aux taux US, à la fiscalité (Tax Day) et à des rejets de "notional" (positions < 150$).

## TÂCHES À ACCOMPLIR

### 1. Intégration des Patterns Saisonniers
Proposer une implémentation pour les patterns suivants :
- **Tax Day (Avril) :** Réduction automatique de l'exposition globale (multiplier de risque).
- **Yield Correlation :** Filtre dynamique excluant les secteurs Tech/Growth si le 10Y US Treasury monte trop vite.
- **Santa Claus Rally & January Effect :** Augmentation du levier ou élargissement du screener.

### 2. Optimisation du Risque et du Capital
- Modifier la logique d'allocation dans `phase2_mode: risk_execution` pour recalculer dynamiquement `max_positions` afin d'éviter l'erreur `Notional insuffisant < 150$`.
- Implémenter un "Sentiment Circuit Breaker" qui passe le portefeuille en mode "Cash Only" si le score agrégé descend sous un seuil critique.

### 3. Filtre "Corporate Actions"
- Utiliser le module `corporate_actions.md` pour forcer un score négatif sur les titres en période d'Earnings (fenêtre +/- 2 jours).

## FORMAT DE SORTIE ATTENDU
Génère un fichier `todo_pattern.md` structuré comme suit :
1. **Modifications Code :** Extraits Python précis pour les modules `backtesting/` et `execution/`.
2. **Configuration YAML :** Nouveaux paramètres à ajouter dans `config.yaml`.
3. **Tests de Validation :** Scénarios de backtest pour valider la résistance au printemps 2025.

---
*Instructions prioritaires : Maintenir la compatibilité avec EODHD et Alpaca. Ne pas introduire de latence dans le pipeline temps réel.*

# Analyse Alpha Trade : Pattern Printemps 2025

## 1. Synthèse de l'Anomalie Constatée
L'analyse du backtest sur l'année 2025 révèle une dégradation significative de la performance entre **avril et mai 2025**.

**Métriques de la période :**
- **Début de baisse :** Autour du 1er avril 2025.
- **Drawdown maximum sur la période :** -13.06%
- **Facteurs identifiés :** Cumul de l'effet saisonnier "Tax Day", durcissement monétaire de la Fed et saturation des limites de risque de l'algorithme.

---

## 2. Analyse des Causes (Marché USA)

### A. Facteurs Macroéconomiques
1. **Tax Day Sell-off (15 Avril) :** Pression vendeuse cyclique aux USA liée aux liquidations pour paiements d'impôts.
2. **Pivot Hawkish de la Fed :** En mai 2025, la résilience de l'inflation a poussé les taux obligataires à la hausse, pénalisant les valeurs de croissance (Growth) identifiées dans vos logs (CRWD, ANET, UBER).
3. **Saison des Résultats T1 :** Phénomène de "Buy the rumor, sell the news" après les publications d'avril.

### B. Facteurs Techniques (Logs Alpha Trade)
- **Saturation Risk :** Atteinte récurrente des limites `max_positions` (5) et `max_gross_exposure`.
- **Erreurs de Notional :** Rejets d'ordres (`Notional insuffisant < 150$`) dus à la baisse du capital total, empêchant la stratégie de se relancer sur les signaux de rebond.

---

## 3. Stratégies d'Anticipation et Optimisation

Pour éviter de subir ce mouvement à l'avenir, voici les modifications logiques recommandées pour le **Model Factory** et le module de **Sentiment**.

### Règle 1 : Filtre de Régime (Sentiment)
Intégrer un "Coupe-circuit" basé sur le score de sentiment agrégé :
- **Condition :** Si le `Sentiment_Score_7D` (moyenne mobile) chute brutalement alors que les prix stagnent.
- **Action :** Réduction automatique de `max_positions` de 5 à 2 ou passage en mode "Cash Only".

### Règle 2 : Corrélation aux Taux (Yield Filter)
- **Condition :** Si le rendement du Trésor US à 10 ans (10Y Yield) augmente de > 5% sur une fenêtre de 5 jours.
- **Action :** Blacklist temporaire des secteurs Tech/Growth dans le Model Factory.

### Règle 3 : Gestion Dynamique du Capital
Ajuster la taille des positions pour éviter les rejets de type "Notional" :
- **Logique :** Recalculer le nombre de slots disponibles selon le capital restant pour que chaque ligne reste > 150$.

---

## 4. Conclusion du Backtest
Le mouvement d'avril-mai 2025 n'était pas une défaillance de prédiction pure, mais une **crise de liquidité et de taux**. L'ajout d'une couche "Macro-Sentiment" permettrait à l'application Alpha Trade de passer en mode défensif avant que le drawdown ne s'accentue.

*Document généré pour analyse de stratégie quantitative - Alpha Trade System.*

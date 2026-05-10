# PROMPT : IMPLÉMENTATION DES PATTERNS CYCLIQUES (LIVE & BACKTEST) - ALPHA TRADE PRO

## 1. OBJECTIF
Transformer "Alpha Trade" en un système "Market-Aware" capable d'ajuster son exposition en temps réel (Live) et en simulation (Backtest). La logique doit être centralisée pour garantir la fidélité de l'exécution.

## 2. ARCHITECTURE TECHNIQUE (CENTRALISATION)

### A. Création du `service/market/regime_manager.py`
Ce module doit être le "cerveau" décisionnel consulté par `Screener` et `RiskManager`.
1. **Filtres de Calendrier (Saisonnalité & Smart Money) :**
   - **Baisse Systémique (Tax Day & September Dip) :** Réduction du multiplicateur de risque (`risk_mult`).
   - **Rallyes (Santa Rally, January Effect) :** Augmentation de l'agressivité.
   - **Manipulation Institutionnelle (OpEx & Month-End) :** Hausse du seuil de sentiment requis pour filtrer les faux signaux.

2. **Filtres Macro en Temps Réel :**
   - **Yield Monitor :** Si les taux 10Y US montent de >5% en 5j (données via Alpaca/EODHD), blacklist automatique des secteurs Tech/Growth en Live.
   - **Earnings Shield :** Interdiction stricte d'ouvrir une position sur un ticker à J-2 ou J+2 des résultats (via `corporate_actions`).

### B. Intégration dans le flux d'Exécution (`run_execution.py`)
Le script `run_execution.py` doit appeler le `regime_manager` au début de chaque cycle :
- **Ajustement du Capital :** Recalculer `max_positions` et `cash_per_trade` dynamiquement pour éviter les rejets de "Notional insuffisant < 150$" vus dans les logs de 2025.
- **Circuit Breaker :** Si le score de sentiment global est trop bas (Sentiment < -0.3), le mode Live doit automatiquement passer en "Close Only" (ne pas ouvrir de nouveaux trades).

## 3. CONFIGURATION (`config.yaml`)
Ajouter une section globale pour piloter ces filtres :
```yaml
market_regimes:
  enabled: true # Actif en Live et en Backtest
  enforce_min_notional: 155
  yield_protection: true
  patterns:
    tax_day: {start: "04-10", end: "04-20", risk_mult: 0.5}
    sept_slump: {start: "09-15", end: "10-15", risk_mult: 0.4}
    institutionnal_opex: {rule: "3rd_friday", sentiment_boost: 0.2}
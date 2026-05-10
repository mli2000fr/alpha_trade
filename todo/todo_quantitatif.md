# PROMPT : ARCHITECTE TRADING QUANTITATIF - SYSTÈME ALPHA TRADE "INSTITUTIONAL GRADE"

## 1. MISSION
Refondre le moteur d'exécution pour transformer Alpha Trade en un système capable de rivaliser avec les flux institutionnels. Le système doit être "conscient" de son environnement avant d'engager le capital de 2000$.

## 2. IMPLÉMENTATIONS PRIORITAIRES (MÉTIER)

### A. Phase 0 : Diagnostic de Marché (The Sentinel)
Avant tout scan du Screener, `regime_manager.py` doit valider :
1. **Volatilité (VIX) :** Si VIX > 25 ou si la courbe est inversée (Short-term > Long-term), passage en "Capital Preservation" (Max 1 position, Stops serrés).
2. **Liquidité (Calendrier Institutionnel) :**
   - **Blackout Buybacks :** (2 sem. avant Earnings) -> Réduction du score ML de 30%.
   - **Tax Day (10-20 Avril) & Sept. Slump (15 Sep-15 Oct) :** Multiplicateur de risque à 0.4.
   - **OpEx (3ème vendredi) :** Pas d'entrée en position pour éviter la volatilité technique.

### B. Gestion de Portefeuille Intelligente
1. **Filtre de Corrélation Sectorielle :** Maximum 2 tickers par secteur (ex: Tech, Healthcare, Energy).
2. **Dynamic Position Sizing (Anti-Rejet Alpaca) :**
   - Calcul mathématique : `allowed_slots = floor(total_equity / 155)`.
   - Si `allowed_slots < max_positions_config`, le système s'ajuste automatiquement pour ne jamais envoyer d'ordre < 150$.

### C. Filtre de Taux (Macro-Overlay)
- Si le rendement du 10Y US Treasury monte de >5% en 5 jours, le système doit automatiquement "Blacklister" les tickers à haut Beta et le secteur Growth du Screener.

## 3. MODIFICATIONS TECHNIQUES ATTENDUES
1. **Nouveau module :** `service/market/regime_manager.py` (Centralise VIX, Yields, Calendrier).
2. **Update `RiskManager` :** Intégrer le `risk_multiplier` calculé par la Phase 0 dans la taille finale de position.
3. **Update `run_execution.py` :** Créer un "Pre-flight Check" qui affiche un résumé du contexte de marché avant de lancer le screener.

## 4. LIVRABLES
- Code source Python robuste et commenté.
- Mise à jour du `config.yaml` avec les nouveaux seuils.
- Procédure de test simulant les conditions de crash d'Avril-Mai 2025.

---
*Note : Maintenir la stricte parité entre le mode BACKTEST et le mode LIVE.*
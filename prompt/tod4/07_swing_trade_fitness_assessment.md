# 07 — Adéquation métier pure swing trade

Date : mai 2026

---

## Verdict global

**Alpha Trade est bien adapté au swing trading actions US.** L'architecture, les paramètres, les contraintes et les garde-fous sont conçus pour le swing, pas pour le day trading ou l'investissement long terme.

**Note adéquation swing trade : 8.0 / 10**

---

## 1. Forces pour le swing trade

### 1.1 Horizon de détention adapté
- `swing_only=True` sur tous les presets → interdit le day trading
- Signaux basés sur des données daily (OHLCV, screener, Minervini)
- Fenêtre de sentiment de 5 jours glissants, cohérente avec le swing

### 1.2 Filtres de sélection orientés swing
- Critères Minervini (tendance long terme, force relative)
- VCP (contraction de volatilité — setup classique de swing)
- Filtre ATR (1.5%–6%) : exclut les titres trop peu volatils (pas assez de mouvement) et trop volatils (risque excessif)
- Earnings blackout : évite les gaps de résultats, risque majeur en swing

### 1.3 Gestion du risque calibrée swing
- Sizing ATR : budget de risque basé sur la volatilité récente, adapté au swing
- Trailing stop ATR dynamique (mode `dynamic_atr`) : suivi de tendance
- Take-profit à +8%, stop à -5% : ratios risque/rendement raisonnables pour du swing
- Break-even après 2 ATR : sécurise les gains

### 1.4 Exécution compatible swing
- Ordres market/limit avec buffer configurable
- Délai inter-ordres (350ms paper/live) : évite les pics de marché
- Pas de exigence de fill immédiat (timeout 120-180s)
- Protections broker-side (stop + take-profit) avec OCO logique

### 1.5 Backtesting réaliste
- Convention `signal J → entrée open J+1` : exécution réaliste, pas de look-ahead
- Contraintes cash/margin/swing : reflète les vraies limites de compte
- Swing_only interdit les ventes intraday dans le backtest

---

## 2. Faiblesses pour le swing trade

### 2.1 Absence de stratégies de sortie multiples
- Un seul take-profit et un seul stop par position
- Pas de sortie partielle (scale-out) pour gérer le risque dynamiquement
- Pas de ré-entrée après sortie sur un titre qui reste dans l'univers

### 2.2 Pas de gestion du hold time minimum/maximum
- Aucune règle ne force un temps de détention minimum (ex: 2 jours)
- Aucune règle ne force une sortie après N jours sans performance

### 2.3 Indicateurs exclusivement daily
- Pas de confirmation intraday pour l'entrée (ex: attendre un pullback)
- Pas d'analyse de volume intraday pour valider le setup

### 2.4 Pas d'analyse de régime de marché swing-spécifique
- La couche Market-Aware existe mais n'est pas spécifiquement calibrée pour le swing
- Pas d'indicateur de « swingabilité » du marché (ex: VIX range-bound)

### 2.5 Univers potentiellement restreint en périodes calmes
- Les filtres stricts peuvent produire un univers vide en marchés peu directionnels
- Pas de stratégie alternative quand le swing n'est pas favorable

---

## 3. Adéquation par composant

| Composant | Adéquation swing | Note | Commentaire |
|---|---|---|---|
| Screener | Bonne | 7.5/10 | Force relative et range historique pertinents |
| Selector (Minervini/VCP) | Excellente | 9/10 | Critères conçus par un swing trader (Minervini) |
| Sentiment | Bonne | 7/10 | Fenêtre 5j adaptée, mais bruit possible |
| ML (LSTM + challengers) | Moyenne | 6/10 | Peut sur-optimiser sur des patterns non swing-spécifiques |
| Risk (sizing ATR/Kelly) | Très bonne | 8.5/10 | ATR est le standard pour le sizing swing |
| Execution | Excellente | 9/10 | Protections OCO, trailing stop, swing_only |
| Corporate Actions | Bonne | 8/10 | Dividendes bien gérés pour le swing |
| Backtesting | Très bonne | 8.5/10 | Contraintes réalistes, PIT, convention J+1 |
| Market-Aware | Bonne | 7.5/10 | Régime, trailing ATR, earnings shield |

---

## 4. Comparaison avec les pratiques professionnelles swing

| Pratique pro | Alpha Trade |
|---|---|
| Univers filtré par liquidité ET volatilité | ✅ Oui (dollar volume ET ATR) |
| Entrée sur setup technique (Minervini, VCP) | ✅ Oui |
| Sizing basé sur la volatilité (ATR) | ✅ Oui |
| Stop loss technique (ATR multiple) | ✅ Oui |
| Take-profit défini à l'avance | ✅ Oui (8% fixe) |
| Trailing stop pour suivre la tendance | ✅ Oui (mode dynamique) |
| Gestion des événements binaires (earnings) | ✅ Oui (blackout) |
| Tenue de compte des dividendes | ✅ Oui (cash ledger) |
| Backtesting réaliste (frais, spread, contraintes compte) | ✅ Oui |
| Journal de trading structuré | ✅ Oui (tables d'exécution) |
| Analyse post-trade (TCA) | ✅ Oui |
| Multi-stratégies selon le régime | ⚠️ Partiel (couche Market-Aware) |
| Gestion du risque corrélation | ✅ Oui |
| Scale-out (sorties partielles) | ❌ Non |
| Pyramiding (renforcement sur gain) | ❌ Non |
| Short selling | ❌ Non |

---

## 5. Risques spécifiques au swing trading avec Alpha Trade

| Risque | Probabilité | Impact | Atténuation existante |
|---|---|---|---|
| Gap overnight défavorable | Élevée | Moyen | Earnings blackout, mais pas de gap filter hors earnings |
| Univers vide en marché range-bound | Moyenne | Élevé | Aucune (pas de stratégie alternative) |
| Whipsaw (faux breakouts) en forte volatilité | Moyenne | Moyen | Filtre volatility_ratio, mais stop serré |
| Frais de transaction sur petits comptes | Élevée sur micro-comptes | Élevé | Presets ajustés mais encore optimistes |
| Slippage au market open | Élevée | Faible | Ordre d'entrée open J+1, pas d'atténuation slippage |

---

## 6. Recommandations pour améliorer l'adéquation swing

1. **Ajouter un filtre de gap overnight** : ne pas entrer si le gap par rapport à la clôture précédente dépasse X%
2. **Implémenter des sorties partielles (scale-out)** : 50% au take-profit, 50% en trailing
3. **Ajouter une règle de hold time minimum** : 2-3 jours pour éviter les micro-swings
4. **Développer un indicateur de « swingabilité » du marché** : VIX range-bound, tendance des indices
5. **Créer une stratégie alternative « cash » ou « defensive »** quand le swing n'est pas favorable
6. **Ajouter un filtre de gap dans le backtesting** pour éviter les entrées sur gaps défavorables
7. **Calibrer les take-profit par la volatilité** (ex: 2 ATR) plutôt qu'un % fixe de 8%

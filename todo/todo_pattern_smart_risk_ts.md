# PROMPT : OPTIMISATION DU RISK MANAGEMENT - TRAILING STOP ADAPTATIF ET SYNC EXTERNE

## 1. CONTEXTE
L'application "Alpha Trade" applique actuellement un Trailing Stop (TS) fixe de 5.0% pour les titres achetés hors application. L'objectif est de remplacer ce "rattrapage" par un **TS dynamique basé sur la volatilité (ATR)** pour coller à la réalité du marché institutionnel.

## 2. RÈGLES MÉTIERS À IMPLÉMENTER

### A. TS Dynamique basé sur l'ATR (Average True Range)
Au lieu de `TS = 5.0%`, le `RiskManager` doit calculer le stop selon la formule institutionnelle :
- **Calcul :** `TS_Distance = ATR(14) * Multiplier`.
- **Multiplier suggéré :** 2.0 ou 3.0 (à rendre paramétrable dans `config.yaml`).
- **Logique :** Si un titre est très volatil (ex: NVDA), le TS sera de 8%. S'il est stable (ex: KO), il sera de 3%. Cela évite de se faire sortir par le "bruit" de marché.

### B. Module de Rattrapage (External Order Sync)
Lorsqu'un titre est détecté comme "acheté hors application" (via le scan Alpaca) :
1. **Identification du Ticker :** Récupérer l'ATR actuel du titre via EODHD/Alpaca.
2. **Calcul du TS "Smart" :** Appliquer le TS basé sur l'ATR au lieu des 5.0% génériques.
3. **Mise à jour automatique :** Envoyer l'ordre `replace_order` ou `update_stop` à Alpaca pour synchroniser le stop réel avec le calcul de l'app.

### C. Protection Institutionnelle "Time-Based"
- **Breakeven Automatique :** Si le profit latent dépasse 2 * ATR, remonter automatiquement le TS au prix d'entrée (Break Even).
- **End-of-Day Check :** À 15h50 EST, vérifier si la volatilité du jour a modifié l'ATR de manière significative et ajuster les stops pour le lendemain.

## 3. MODIFICATIONS TECHNIQUES ATTENDUES

### A. Update `service/market/risk_manager.py`
- Ajouter une fonction `get_atr_based_stop(ticker, multiplier=2.5)`.
- Modifier la phase de "rattrapage" pour qu'elle appelle cette fonction.

### B. Update `config.yaml`
Ajouter les paramètres de volatilité :
```yaml
risk_management:
  trailing_stop:
    mode: "dynamic_atr"  # remplace "fixed"
    atr_period: 14
    atr_multiplier: 2.5
    fallback_fixed_pct: 5.0 # Uniquement si l'ATR est indisponible
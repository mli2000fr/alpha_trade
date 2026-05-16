# 07 — Swing Trade Fitness Assessment — Alpha Trade

> **Date** : mai 2026 | Question : l'application est-elle vraiment adaptée au swing trading US réel ?

---

## 1. Évaluation globale de l'adéquation swing trade

**Score fitness swing trade : 7/10**

L'application est conçue explicitement pour le swing trading US (NYSE/NASDAQ), horizon de quelques jours à quelques semaines, positions long uniquement. Elle couvre les contraintes critiques du style : PDT rule, cash/margin, swing_only, exécution end-of-day.

---

## 2. Ce qui est well-fitted pour le swing trade US

### 2.1 Convention d'exécution correcte
- **Signal J → entrée open J+1** : évite le look-ahead biais
- **Swing only** option : interdit la revente le jour même
- **PDT rule** implémentée côté backtesting ET exécution réelle
- **Cash settlement T+1** simulé en backtest et appliqué en exécution via `non_marginable_buying_power`

### 2.2 Filtres techniques pertinents pour swing trade
- **Minervini trend score** : 7 critères (close > MA150, MA150 > MA200, etc.) — méthodologie éprouvée pour identifier des leaders en tendance haussière
- **VCP (Volatility Contraction Pattern)** : compression avant breakout — signal classique swing
- **Filtre ATR 1.5–6%** : exclut les titres trop calmes (peu de momentum) et trop volatils (risque de spike imprévisible). Pertinent pour swing.
- **Blackout earnings 3 jours** : évite les positions binaires avant résultats
- **Filtre beta ≥ 0.8** : cible des titres directionnels, pas les valeurs défensives

### 2.3 Risk management swing-compatible
- **ATR sizing** (risque 1% par trade) : approche standard swing traders professionnels
- **Trailing stop ATR dynamique** : disponible, break-even à 2R
- **Corrélation filter** : réduit le risque de concentration sectorielle camouflée
- **Circuit breaker** drawdown 15% + perte daily 5% : protections standard swing desk

### 2.4 Backtesting rigoureux
- Phases de fidélité 2/3/4/5/7 pour rapprocher le backtest du live
- Diagnostic screener : analyse pourquoi l'univers est plein/vide selon les régimes
- Walk-forward hors échantillon

---

## 3. Ce qui manque ou est sous-optimal pour le swing trade réel

### 3.1 Absences critiques

**a) Pas de gestion des entrées sur breakout intraday**  
Le pipeline est entièrement end-of-day. Sur un swing trade Minervini, l'entrée idéale est un pivot intraday (breakout avec volume). Une entrée à l'open J+1 peut être :
- déjà trop chère si le titre a monté de 3–5% overnight
- mal positionnée par rapport au pivot

**Mitigation** : En pratique, l'entrée open J+1 avec `limit_price_buffer_bps: 10` atténue ce risque. L'ordre limit évite les ouvertures gap-up excessives.

**b) Pas de short selling**  
Le swing trade est naturellement long-only sur bull market, mais en rotation sectorielle ou en régime baissier, les shorts permettent de bénéficier des rotations. L'application est 100% long.

**c) Pas de streaming de prix en temps réel**  
Le polling (2s) pour les fills est correct pour des ordres quotidiens mais ne permet pas de gérer des ajustements intrajournaliers des stops. Le watcher post-exécution pallie partiellement ce manque.

### 3.2 Limites spécifiques aux petits comptes swing

**d) Capital < 5 000 $ : univers souvent vide**  
Avec les filtres du profil strict (close ≥ 10$, ADV ≥ 30M$, market_cap ≥ 2Md$), un petit compte cash swing de 4 000 $ n'a accès qu'à 3–4 positions × 1 000 $ chacune. Si les 3–4 candidats disponibles ce jour-là sont tous blackoutés earnings ou en excès de volatilité, le pipeline produit 0 candidats → portefeuille vide.

**Mitigation** : Les presets petits comptes relâchent les filtres (ce qui crée d'autres risques). C'est un compromis difficile.

**e) `risk_min_position_notional: 150 USD` sur micro-compte**  
Sur un ordre de 150 USD, le spread de 40–80 bps représente 60–120 cents d'impact. Pour un objectif de profit de 8%, le coût total (entrée + sortie) est ~1.6–2.4% → ratio coût/objectif 20–30%. Marginal pour swing trade court.

### 3.3 ML / Signal qualité

**f) LSTM per-symbol sur historique potentiellement court**  
Sur un titre qui a 252–504 jours d'historique available, l'LSTM est entraîné sur un ensemble limité. Le risque d'overfitting est réel. Un swing trade basé sur une proba ML issué d'un modèle overfit peut générer de faux signaux de conviction.

**g) Sentiment FinBERT : qualité variable**  
Le modèle `ProsusAI/finbert` est entraîné sur des articles financiers généraux. Sur des news très techniques ou spécifiques à un secteur (biotechs, utilities), l'interprétation peut être imprécise.

**h) Biais positif FinBERT historique**  
Le modèle finbert a un léger biais positif sur les articles de presse d'entreprise (press releases, earnings beats). Ce biais peut sur-scorer des articles neutres ou légèrement négatifs.

---

## 4. Adéquation par type de compte / situation

| Profil | Adéquation | Limitations |
|---|---|---|
| Compte paper, 10k–50k$, margin | ✅ Très bien | Pipeline complet exploitable |
| Compte cash, 5k–25k$ | ✅ Bien | PDT évité, swing_only, univers parfois restreint |
| Micro-compte ≤ 2k $ | 🟡 Fragile | Frais relatifs élevés, univers souvent vide |
| Grand compte live ≥ 50k$ | ✅ Bi | Manque alerting push, monitoring live, SSL |
| Multi-comptes paper + live | ✅ Supporté | Isolation par account_id, CLI `--account` |

---

## 5. Réalisme des trailing stops et protections

| Configuration | Réalisme | Commentaire |
|---|---|---|
| Stop fixe 5% | ✅ Standard | Acceptable pour swing de quelques jours |
| Take-profit fixe 8% | ✅ Standard | R:R 1.6:1 avec stop 5% → acceptable |
| Trailing stop ATR × 2.5 | ✅ Excellent | ATR-based > fixe pour swing trade actif |
| Break-even à 2R | ✅ Professionnel | Protection capital une fois profitable |
| Stop initial → trailing (watcher) | ✅ Bonne idée | Latence post-fill possible (batch polling) |

**Observation** : Le trailing stop ATR est désactivé par défaut (`enabled: false`). En paper, il devrait être activé pour valider son comportement avant live.

---

## 6. Risque de sur-ajustement du pipeline

Le pipeline a de nombreux paramètres configurables (40+ par preset). Le risque de "curve fitting" sur les presets via backtest est réel. Pour mitiger :
- Utiliser le walk-forward sentiment calibration déjà implémenté
- Valider chaque preset sur une période hors échantillon de 6+ mois
- Ne pas modifier trop fréquemment les paramètres entre les runs

---

## 7. Verdict fitness swing trade

**Le pipeline est adapté au swing trading US discipliné, à condition de :**

1. ✅ Utiliser des comptes ≥ 5 000 $ pour avoir un univers viable
2. ✅ Lancer le pipeline après 18h00 EST (bulk EOD fiable)
3. ✅ Exécuter toutes les 14 étapes dans l'ordre strict
4. ✅ Surveiller régulièrement l'IHM pour détecter les alertes
5. ⚠️ Activer le trailing stop ATR avant de passer live
6. ⚠️ Effectuer un backfill PIT complet avant tout backtest sérieux
7. ⚠️ Valider la calibration sentiment au moins tous les trimestres
8. ❌ Ne pas utiliser le micro-compte preset sans correction des paramètres


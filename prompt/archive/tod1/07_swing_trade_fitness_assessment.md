# 07 — Swing Trade Fitness Assessment — Alpha Trade

> **Date** : mai 2026 | Question : l'application est-elle vraiment adaptée au swing trading US réel ?

---

## 1. Évaluation globale de l'adéquation swing trade

**Score fitness swing trade : 8.0/10** *(+0.5 post-Sprint S4 : widget PnL quotidien IHM opérationnel, walk-forward risk params disponible)*

L'application est conçue explicitement pour le swing trading US (NYSE/NASDAQ), horizon de quelques jours à quelques semaines, positions long uniquement. Elle couvre les contraintes critiques du style : PDT rule, cash/margin, swing_only, exécution end-of-day. L'alerting email automatique sur circuit_breaker est opérationnel depuis Sprint S3, ce qui améliore la surveillance en production réelle. Depuis Sprint S4, le PnL latent des positions ouvertes est visible directement dans la page Overview de l'IHM (A-021 ✅).

---

## 2. Ce qui est well-fitted pour le swing trade US

### 2.1 Convention d'exécution correcte
- **Signal J → entrée open J+1** : évite le look-ahead biais
- **Swing only** option : interdit la revente le jour même
- **PDT rule** implémentée côté backtesting ET exécution réelle (presets margin : `pdt_rule: "auto"` ✅ Sprint S2)
- **Cash settlement T+1** simulé en backtest et appliqué en exécution via `non_marginable_buying_power`

### 2.2 Filtres techniques pertinents pour swing trade
- **Minervini trend score** : 7 critères (close > MA150, MA150 > MA200, etc.) — méthodologie éprouvée pour identifier des leaders en tendance haussière
- **VCP (Volatility Contraction Pattern)** : compression avant breakout — signal classique swing
- **Filtre ATR 1.5–6%** : exclut les titres trop calmes (peu de momentum) et trop volatils (risque de spike imprévisible). Pertinent pour swing.
- **Blackout earnings 3 jours** : évite les positions binaires avant résultats
- **Filtre beta ≥ 0.8** : cible des titres directionnels, pas les valeurs défensives
- **`selector_min_close: 10.0 USD` uniformisé** sur tous les presets ✅ Sprint S2

### 2.3 Risk management swing-compatible
- **ATR sizing** (risque 1% par trade) : approche standard swing traders professionnels
- **Trailing stop ATR dynamique** : disponible, break-even à 2R
- **Corrélation filter** : réduit le risque de concentration sectorielle camouflée
- **Circuit breaker** drawdown 15% + perte daily 5% : protections standard swing desk
- **Alerting email automatique** sur déclenchement circuit_breaker ✅ Sprint S3

### 2.4 Backtesting rigoureux
- Phases de fidélité 2/3/4/5/7 pour rapprocher le backtest du live
- Diagnostic screener : analyse pourquoi l'univers est plein/vide selon les régimes
- Walk-forward hors échantillon avec bornes business enforced [0.05, 0.40] ✅ Sprint S3
- **ParquetCache** opérationnel (`--use-cache`) : backtests > 2 ans 3x–10x plus rapides ✅ Sprint S3
- **Bootstrap Monte Carlo** accessible (`--bootstrap-samples 1000`) ✅ Sprint S3
- **Walk-forward paramètres risk** : `walk_forward_risk_params()` — grid-search ATR/Kelly/correlation ✅ Sprint S4

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

**d) ~~Pas de PnL quotidien dans l'IHM~~** (A-021 **✅ RÉSOLU Sprint S4**)  
~~L'opérateur doit consulter les tables DB manuellement pour consulter le P&L du jour.~~  
Le widget PnL latent (section 0 de la page Overview) affiche `broker_positions_snapshots.unrealized_pnl` agrégé. Gracieux en l'absence de positions (paper trading).

### 3.2 Limites spécifiques aux petits comptes swing

**e) Capital < 5 000 $ : univers souvent vide**  
Avec les filtres du profil strict (close ≥ 10$, ADV ≥ 30M$, market_cap ≥ 2Md$), un petit compte cash swing de 4 000 $ n'a accès qu'à 3–4 positions × 1 000 $ chacune. Si les 3–4 candidats disponibles ce jour-là sont tous blackoutés earnings ou en excès de volatilité, le pipeline produit 0 candidats → portefeuille vide.

**Mitigation** : Les presets petits comptes relâchent les filtres (ce qui crée d'autres risques). C'est un compromis difficile.

**f) `risk_min_position_notional: 150 USD` sur petit compte (capital_0_5000)**  
Sur un ordre de 150 USD, le spread de 40–80 bps représente 60–120 cents d'impact. Pour un objectif de profit de 8%, le coût total (entrée + sortie) est ~1.6–2.4% → ratio coût/objectif 20–30%. Marginal pour swing trade court.

### 3.3 ML / Signal qualité

**g) LSTM per-symbol sur historique potentiellement court**  
Sur un titre qui a 252–504 jours d'historique available, l'LSTM est entraîné sur un ensemble limité. Le risque d'overfitting est réel. Un swing trade basé sur une proba ML issué d'un modèle overfit peut générer de faux signaux de conviction.

**h) Sentiment FinBERT : qualité variable**  
Le modèle `ProsusAI/finbert` est entraîné sur des articles financiers généraux. Sur des news très techniques ou spécifiques à un secteur (biotechs, utilities), l'interprétation peut être imprécise.

**i) Biais positif FinBERT historique**  
Le modèle finbert a un léger biais positif sur les articles de presse d'entreprise (press releases, earnings beats). Ce biais peut sur-scorer des articles neutres ou légèrement négatifs.

---

## 4. Adéquation par type de compte / situation

| Profil | Adéquation | Limitations |
|---|---|---|
| Compte paper, 10k–50k$, margin | ✅ Très bien | Pipeline complet exploitable, alerting email actif ✅ S3 |
| Compte cash, 5k–25k$ | ✅ Bien | PDT évité, swing_only, min_close=10$ uniformisé ✅ S2, univers parfois restreint |
| Micro-compte ≤ 2k $ | 🟡 Fragile | Frais relatifs élevés, univers souvent vide, max_positions=3 ✅ S1 |
| Grand compte live ≥ 50k$ | ✅ Bien | Alerting push email activé ✅ S3 ; alertes IHM réconciliation + market_cap TTL ; SSL activable ✅ S1 |
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
- Utiliser le walk-forward sentiment calibration déjà implémenté avec bornes enforced [0.05, 0.40] ✅ Sprint S3
- **Utiliser `walk_forward_risk_params()` pour optimiser ATR/Kelly/correlation hors échantillon** ✅ Sprint S4
- Valider chaque preset sur une période hors échantillon de 6+ mois
- Utiliser le Bootstrap Monte Carlo (`--bootstrap-samples 1000`) pour quantifier la robustesse statistique ✅ Sprint S3
- Ne pas modifier trop fréquemment les paramètres entre les runs

---

## 7. Verdict fitness swing trade

**Le pipeline est adapté au swing trading US discipliné, à condition de :**

1. ✅ Utiliser des comptes ≥ 5 000 $ pour avoir un univers viable
2. ✅ Lancer le pipeline après 18h00 EST (bulk EOD fiable)
3. ✅ Exécuter toutes les 14 étapes dans l'ordre strict
4. ✅ Surveiller régulièrement l'IHM pour détecter les alertes (+ alerting email automatique actif ✅ S3)
5. ✅ Visualiser le PnL latent en temps réel depuis la page Overview ✅ S4
6. ✅ Activer le trailing stop ATR avant de passer live
7. ✅ Effectuer un backfill PIT complet avant tout backtest sérieux
8. ✅ Valider la calibration sentiment au moins tous les trimestres
9. ✅ Utiliser `--bootstrap-samples` pour valider la robustesse statistique avant tout changement de preset
10. ✅ Utiliser `walk_forward_risk_params()` pour optimiser ATR/Kelly/correlation avant live ✅ S4
11. ⚠️ Le micro-compte preset est désormais cohérent (max_positions=3 ✅ S1) mais reste fragile sur l'univers

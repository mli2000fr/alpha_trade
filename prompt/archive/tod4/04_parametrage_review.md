# 04 — Revue détaillée des paramétrages et presets de capital

Date : mai 2026

---

## 1. Profil strict canonique (`STRICT_SWING_CASH_FILTERS`)

Source : `core/filter_profiles.py`

| Paramètre | Valeur | Commentaire |
|---|---|---|
| `min_close` | 10.0 $ | Prix plancher raisonnable pour swing US |
| `min_avg_dollar_volume_20d` | 30 M$ | Liquidité confortable |
| `max_volatility_ratio` | 0.90 | Exclut les spikes de volatilité |
| `min_relative_strength_index` | 100 | Exige une surperformance relative |
| `min_high_52w_proximity` | 0.75 | Proche du plus haut annuel |
| `min_weekly_trend_score` | 1.0 | Tendance hebdomadaire bullish |
| `min_atr_pct_20` | 1.5 % | Volatilité minimale pour swing |
| `max_atr_pct_20` | 6.0 % | Plafond de volatilité |
| `min_market_cap` | 2 Md$ | Exclut les small caps |
| `min_beta_126` | 0.8 | Comportement directionnel suffisant |
| `max_spread_bps` | 40 bps | Spread exécutable |
| `earnings_blackout_days` | 3 | Évite les événements binaires |
| `require_above_ma200` | True | Tendance long terme haussière |

**Verdict** : Profil cohérent et bien calibré pour du swing trading US de qualité. Les seuils sont raisonnables et correctement justifiés.

---

## 2. Analyse par tranche de capital

### Tranche 0 → 2 000 € (`capital_0_2000`)

| Paramètre | Valeur | Cohérence |
|---|---|---|
| `risk_per_trade_pct` | 1.0 % | ✅ Adapté |
| `risk_max_positions` | 3 | ✅ Concentration réaliste |
| `risk_min_position_notional` | 500 $ | ✅ Ticket minimum |
| `risk_max_drawdown_pct` | 7 % | ✅ Strict, adapté |
| `execution_account_type` | cash | ✅ Discipline de capital adaptée |
| `execution_swing_only` | true | ✅ |
| `selector_min_close` | 10 $ | ✅ Cohérent profil strict |
| `selector_min_beta_126` | 0.65 | ⚠️ Relâché vs strict (0.80) |
| `selector_max_spread_bps` | 80 | ⚠️ Très permissif vs strict (40) |
| `selector_min_market_cap` | 500 M$ | ⚠️ Relâché vs strict (2 Md$) |
| `selector_liquidity_threshold` | 5 M$ | ⚠️ Relâché vs strict (30 M$) |

**Verdict** : **Fragile** — Le preset est très relâché pour éviter un univers vide, mais cela introduit des candidats de qualité inférieure (petites capitalisations, spreads larges, beta faible). Le risque est qu'un petit compte se retrouve avec des positions peu liquides et coûteuses en frais. Les frais de transaction à 25 bps recommandés en backtest sont probablement sous-estimés pour des ordres à 500 $ sur des titres à spread 80 bps.

---

### Tranche 2 001 → 5 000 $ (`capital_2001_5000`)

| Paramètre | Valeur | Cohérence |
|---|---|---|
| `risk_per_trade_pct` | 1.25 % | ✅ |
| `risk_max_positions` | 4 | ✅ Acceptable |
| `risk_min_position_notional` | 150 $ | ⚠️ Très bas, frais élevés |
| `risk_max_drawdown_pct` | 8 % | ✅ Strict |
| `execution_account_type` | cash | ✅ |
| `selector_min_close` | 10 $ | ✅ |
| `selector_liquidity_threshold` | 10 M$ | ⚠️ Toujours sous le strict (30 M$) |
| `selector_min_beta_126` | 0.70 | ⚠️ |
| `selector_max_spread_bps` | 60 | ⚠️ |
| `selector_min_market_cap` | 1 Md$ | ⚠️ Sous le strict (2 Md$) |

**Verdict** : **Fragile** — Le `min_position_notional` à 150 $ expose à des frais de transaction disproportionnés. Sur un compte à 2 500 $, 150 $ représente 6% du capital par ligne, ce qui est élevé mais acceptable si les frais sont maîtrisés. Les filtres selector restent significativement relâchés.

---

### Tranche 5 001 → 10 000 $ (`capital_5001_10000`)

| Paramètre | Valeur | Cohérence |
|---|---|---|
| `risk_per_trade_pct` | 1.75 % | ✅ |
| `risk_max_positions` | 6 | ✅ |
| `risk_min_position_notional` | 200 $ | ⚠️ Encore bas |
| `selector_liquidity_threshold` | 15 M$ | ⚠️ |
| `selector_min_beta_126` | 0.75 | Proche du strict |
| `selector_max_spread_bps` | 55 | ⚠️ |
| `selector_min_market_cap` | 1.5 Md$ | Proche du strict |

**Verdict** : **Cohérent mais perfectible** — La transition vers le profil strict est amorcée. Le `min_position_notional` et les spreads restent un peu permissifs mais le risque est modéré.

---

### Tranche 10 001 → 25 000 $ (`capital_10001_25000`)

| Paramètre | Valeur | Cohérence |
|---|---|---|
| `risk_per_trade_pct` | 1.5 % | ✅ |
| `risk_max_positions` | 8 | ✅ |
| `risk_min_position_notional` | 300 $ | Acceptable |
| `execution_account_type` | cash | ✅ |
| `selector_liquidity_threshold` | 20 M$ | Proche du strict |
| `selector_min_beta_126` | 0.80 | ✅ Égal au strict |
| `selector_max_spread_bps` | 50 | Proche du strict (40) |
| `selector_min_market_cap` | 2 Md$ | ✅ Égal au strict |

**Verdict** : **Cohérent** — Bonne convergence vers le profil strict. Le principal risque est l'absence de Kelly (non activé avant 25 k$) qui pourrait améliorer le sizing.

---

### Tranche 25 001 → 50 000 $ (`capital_25001_50000`)

| Paramètre | Valeur | Cohérence |
|---|---|---|
| `risk_per_trade_pct` | 1.25 % | ✅ |
| `risk_max_positions` | 12 | ✅ |
| `risk_min_position_notional` | 400 $ | ✅ |
| `execution_account_type` | margin | ✅ |
| `risk_enable_kelly` | true | ✅ |
| `selector_liquidity_threshold` | 25 M$ | Proche du strict |
| `selector_max_spread_bps` | 45 | Proche du strict (40) |

**Verdict** : **Cohérent** — Bon équilibre entre diversification et contraintes. L'activation de Kelly est pertinente à ce niveau de capital. La transition vers margin est correctement gérée.

---

### Tranche 50 001 → 100 000 $ (`capital_50001_100000`)

| Paramètre | Valeur | Cohérence |
|---|---|---|
| `risk_per_trade_pct` | 1.0 % | ✅ Standard |
| `risk_max_positions` | 15 | ✅ |
| `risk_min_position_notional` | 500 $ | ✅ |
| `risk_enable_kelly` | true | ✅ |
| `selector_max_spread_bps` | 40 | ✅ Égal au strict |

**Verdict** : **Cohérent** — C'est le preset swing standard du projet. Tous les paramètres sont alignés avec le profil strict.

---

### Tranche 100 001 $+ (`capital_100001_plus`)

| Paramètre | Valeur | Cohérence |
|---|---|---|
| `risk_per_trade_pct` | 0.8 % | ✅ Conservateur |
| `risk_max_positions` | 18 | ✅ |
| `risk_min_position_notional` | 750 $ | ✅ |
| `selector_min_close` | 12 $ | ✅ Plus strict |
| `selector_max_volatility_ratio` | 0.85 | ✅ Plus strict |
| `selector_min_beta_126` | 0.90 | ✅ Plus strict |
| `selector_max_spread_bps` | 35 | ✅ Plus strict |
| `selector_min_market_cap` | 3 Md$ | ✅ Plus strict |
| `selector_earnings_blackout_days` | 4 | ✅ Plus strict |

**Verdict** : **Cohérent** — Preset conservateur bien calibré pour un grand compte. Les seuils plus stricts que le profil canonique sont justifiés par la recherche de qualité supérieure.

---

## 3. Problèmes de cohérence inter-presets

### 3.1 Monotonie des seuils

Les seuils sont globalement monotones (plus stricts quand le capital augmente), ce qui est correct. Quelques exceptions :

- `risk_max_drawdown_pct` : 7% (micro) → 8% → 10% → 12% → 14% → 15% → 18% : **cohérent** (plus tolérant quand le capital augmente)
- `risk_correlation_threshold` : 0.92 → 0.90 → 0.88 → 0.85 → 0.82 → 0.80 → 0.78 : **cohérent** (plus strict quand le capital augmente)
- `selector_min_ibd_rs_rank` : 90 → 95 → 98 → 100 → 100 → 100 → 102 : **cohérent**

### 3.2 Problème de cohérence : `risk_max_drawdown_pct` micro-compte

Le micro-compte a un drawdown max de 7%, plus strict que les tranches supérieures. C'est **intentionnel et justifié** (protection du petit capital), mais cela signifie qu'un petit compte sera stoppé plus souvent, potentiellement au pire moment. Le commentaire dans le YAML le documente.

### 3.3 Point de cohérence : tranches < 25k$ en cash

C'est cohérent : les comptes cash reposent sur le settled cash et `swing_only`. L'ancien commentaire de compatibilité était redondant.

### 3.4 Cohérence avec le swing trade

Tous les presets ont `execution_swing_only: true`, ce qui est cohérent avec l'objectif swing trade du projet.

---

## 4. Cohérence avec les contraintes réelles d'exécution

### 4.1 Spreads et liquidité

- Les presets petits comptes acceptent des spreads jusqu'à 80 bps. Sur un ordre de 500 $, 80 bps = 4 $ de spread, soit 0.8% du montant. C'est élevé mais acceptable en swing (l'horizon est de plusieurs jours).
- Le preset micro-compte (`capital_0_2000`) recommande 25 bps de frais en backtest. Avec un spread de 80 bps, le coût total aller-retour est de (80 + 25) × 2 = 210 bps = 2.1%. C'est significatif et réduit l'espérance de gain.

### 4.2 Contraintes de compte

- Presets < 25k$ : `execution_account_type: cash` → settled cash et discipline swing. ✅
- Presets ≥ 25k$ : `execution_account_type: margin`. ✅
- Le preset `capital_25001_50000` démarre à `min_equity: 25000.01`, ce qui reste cohérent avec la bascule margin documentée à l'époque. ✅

---

## 5. Risques spécifiques par tranche

| Tranche | Risque principal | Sévérité |
|---|---|---|
| 0 → 2 000 € | Univers trop permissif → positions illiquides, frais élevés | Moyen |
| 2 001 → 5 000 $ | `min_position_notional=150$` → frais disproportionnés | Moyen |
| 5 001 → 10 000 $ | Transition progressive acceptable | Faible |
| 10 001 → 25 000 $ | Pas d'accès au Kelly (pertinent vu le capital) | Faible |
| 25 001 → 50 000 $ | Transition margin correctement gérée | Faible |
| 50 001 → 100 000 $ | Standard, peu de risques | Très faible |
| 100 001 $+ | Conservateur, bien calibré | Très faible |

---

## 6. Recommandations

1. **Revoir le preset micro-compte** : augmenter `min_market_cap` à 1 Md$ et `max_spread_bps` à 60 pour réduire le risque d'illiquidité, quitte à avoir un univers plus restreint mais de meilleure qualité.
2. **Revoir `min_position_notional` à 150 $** : le passer à 250 $ minimum pour réduire l'impact des frais fixes.
3. **Documenter les écarts** entre chaque preset et le profil strict canonique, avec justification explicite dans `capital_presets.yaml`.
4. **Ajouter un test de cohérence** qui valide que les overrides des presets ne violent pas les contraintes de sécurité (ex: spread max > 100 bps, min_close < 5 $).
5. **Vérifier la cohérence des frais de backtest** : les `backtesting_slippage_bps_stress` et `backtesting_commission_bps_stress` doivent être cohérents avec les spreads acceptés dans le preset.

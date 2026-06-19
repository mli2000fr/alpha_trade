# 04 — Paramétrage Review

> **Revue détaillée des configurations et presets de capital**

---

## 1. Synthèse par tranche de capital

### Tranche 0 → 2 500 $ (`capital_0_2000_eur`)

| Aspect | Valeur | Évaluation |
|---|---|---|
| `execution_account_type` | `cash` | ✅ Adapté |
| `execution_swing_only` | `false` | ❌ **Incohérent** — devrait être `true` |
| `risk_max_positions` | 3 | ✅ Réaliste |
| `risk_max_position_weight` | 0.35 | ⚠️ Élevé mais assumé pour micro-compte |
| `risk_min_position_notional` | 500$ | ✅ OK |
| `risk_per_trade_pct` | 1% | ✅ OK |
| `selector_liquidity_threshold` | 5 M$ | ⚠️ Relâché mais justifié |
| `selector_min_beta_126` | 0.65 | ⚠️ Très relâché |
| `selector_max_spread_bps` | 80 | ⚠️ Large, exécution dégradée |
| `selector_max_volatility_ratio` | 1.0 | ⚠️ Aucun filtre de volatilité |
| `risk_correlation_threshold` | 0.92 | ⚠️ Très permissif |
| `risk_enable_kelly` | `false` | ✅ Adapté |

**Verdict** : **Fragile** — Le preset est conçu pour ne pas vider l'univers mais les relâchements sont tellement importants que la qualité de sélection est compromise. Le `swing_only=false` est une erreur. Le `max_volatility_ratio=1.0` laisse passer tous les titres.

---

### Tranche 2 501 → 5 000 $ (`capital_0_5000`)

| Aspect | Valeur | Évaluation |
|---|---|---|
| `execution_account_type` | `cash` | ✅ Adapté |
| `execution_swing_only` | `false` | ❌ **Incohérent** |
| `risk_max_positions` | 6 | ✅ Réaliste |
| `risk_max_position_weight` | 0.20 | ✅ OK |
| `risk_min_position_notional` | 150$ | ❌ **Inférieur au min Alpaca (155$)** |
| `selector_liquidity_threshold` | 10 M$ | ⚠️ Acceptable |
| `selector_min_beta_126` | 0.70 | ⚠️ Relâché |
| `selector_max_spread_bps` | 60 | ⚠️ Large |
| `risk_correlation_threshold` | 0.90 | ⚠️ Permissif |
| `risk_enable_kelly` | `false` | ✅ Adapté |

**Verdict** : **Fragile** — Le `min_position_notional` à 150$ est inapplicable. Le `swing_only=false` expose à des violations de settlement.

---

### Tranche 5 001 → 10 000 $ (`capital_5001_10000`)

| Aspect | Valeur | Évaluation |
|---|---|---|
| `execution_account_type` | `cash` | ✅ Adapté |
| `execution_swing_only` | `false` | ❌ **Incohérent** |
| `risk_max_positions` | 8 | ✅ Réaliste |
| `risk_max_position_weight` | 0.18 | ✅ OK |
| `risk_min_position_notional` | 200$ | ⚠️ OK mais limite basse |
| `selector_max_volatility_ratio` | 0.95 | ⚠️ Légèrement relâché |
| `selector_min_beta_126` | 0.75 | ⚠️ Relâché |
| `risk_correlation_threshold` | 0.88 | ⚠️ Permissif |
| `risk_enable_kelly` | `false` | ✅ Adapté |

**Verdict** : **Cohérent mais perfectible** — Les filtres se resserrent progressivement. Le `swing_only=false` reste le point noir.

---

### Tranche 10 001 → 25 000 $ (`capital_10001_25000`)

| Aspect | Valeur | Évaluation |
|---|---|---|
| `execution_account_type` | `cash` | ✅ Adapté |
| `execution_swing_only` | `false` | ❌ **Incohérent** |
| `risk_max_positions` | 10 | ✅ Bon |
| `risk_max_position_weight` | 0.15 | ✅ Bon |
| `risk_min_position_notional` | 300$ | ✅ OK |
| `selector_max_volatility_ratio` | 0.9 | ✅ Strict |
| `selector_min_beta_126` | 0.8 | ✅ Aligné strict |
| `selector_max_spread_bps` | 50 | ✅ Acceptable |
| `risk_correlation_threshold` | 0.85 | ✅ OK |
| `risk_enable_kelly` | `false` | ✅ Adapté |
| `risk_score_weight` | 0.4 | ⚠️ Bascule à 60% ML — non justifié |

**Verdict** : **Cohérent mais perfectible** — Proche du profil strict canonique. Le passage à 60% ML à ce niveau de capital est discutable.

---

### Tranche 25 001 → 50 000 $ (`capital_25001_50000`)

| Aspect | Valeur | Évaluation |
|---|---|---|
| `execution_account_type` | `margin` | ⚠️ Transition brutale |
| `execution_swing_only` | `false` | ⚠️ Pourquoi désactiver ? |
| `risk_max_positions` | 14 | ✅ Bon |
| `risk_max_position_weight` | 0.12 | ✅ Bon |
| `risk_enable_kelly` | `true` | ✅ Cohérent avec la doctrine (≥25k$) |
| `risk_score_weight` | 0.4 (60% ML) | ⚠️ Poids ML dominant |
| `selector_max_spread_bps` | 45 | ✅ Bon |

**Verdict** : **Cohérent mais perfectible** — Le passage à `margin` est justifié par la doctrine PDT mais le `swing_only=false` est inexpliqué. Les paramètres de drawdown breaker sont toujours identiques aux autres tranches.

---

### Tranche 50 001 → 100 000 $ (`capital_50001_100000`)

| Aspect | Valeur | Évaluation |
|---|---|---|
| `execution_account_type` | `margin` | ✅ Adapté |
| `execution_swing_only` | `false` | ⚠️ Inexpliqué |
| `risk_max_positions` | 17 | ✅ Bon |
| `risk_max_drawdown_pct` | 0.19 | ⚠️ Plus permissif que les petites tranches (0.15) |
| `risk_enable_kelly` | `true` | ✅ OK |
| `selector_liquidity_threshold` | 30 M$ | ✅ Bon |
| `selector_max_spread_bps` | 40 | ✅ Aligné strict |

**Verdict** : **Cohérent** — Preset standard du projet, bien équilibré. Le `max_drawdown_pct=0.19` est plus élevé que les petites tranches, ce qui est contre-intuitif (un grand compte peut se permettre un drawdown plus faible en valeur absolue).

---

### Tranche 100 001 $+ (`capital_100001_plus`)

| Aspect | Valeur | Évaluation |
|---|---|---|
| `execution_account_type` | `margin` | ✅ Adapté |
| `execution_swing_only` | `false` | ⚠️ Inexpliqué |
| `risk_max_positions` | 20 | ✅ Bon |
| `risk_max_drawdown_pct` | 0.20 | ⚠️ Le plus élevé de tous les presets |
| `risk_per_trade_pct` | 0.8% | ✅ Prudent |
| `selector_liquidity_threshold` | 40 M$ | ✅ Strict |
| `selector_min_close` | 12$ | ✅ Strict |
| `selector_max_volatility_ratio` | 0.85 | ✅ Très strict |
| `selector_min_beta_126` | 0.90 | ✅ Strict |
| `selector_max_spread_bps` | 35 | ✅ Très strict |
| `risk_correlation_threshold` | 0.78 | ✅ Strict |
| `risk_enable_kelly` | `true` | ✅ OK |

**Verdict** : **Cohérent** — Preset le plus strict, adapté aux grands comptes. Les filtres selector sont plus exigeants que le profil strict canonique, ce qui est justifié.

---

## 2. Cohérence inter-presets

### Points de cohérence ✅
- Progression globalement logique des seuils de liquidité (5M → 40M$)
- Progression du nombre de positions (3 → 20)
- Diminution du poids max par position (35% → 8%)
- Activation de Kelly à partir de 25k$ (conformément à la doctrine S6)
- Resserrement progressif des filtres selector

### Points d'incohérence ❌
1. **`execution_swing_only=false` partout** : Aucun preset n'active le swing-only, en contradiction avec la doctrine swing du projet
2. **Paramètres de drawdown breaker identiques** : `degraded_entry_allocation_pct=0.025`, `ramp_up_max_pct=0.8` pour toutes les tranches
3. **`max_drawdown_pct` croissant avec le capital** : 0.15 (micro) → 0.20 (100k$+), ce qui est contre-intuitif
4. **Transition cash→margin brutale à 25k$** : Pas de période de transition ou de warning
5. **Premier preset en EUR, les autres en USD** : Ambiguïté de devise
6. **`risk_min_position_notional` décroissant puis croissant** : 500 → 150 → 200 → 300 → 400 → 500 → 750 — le preset 2k-5k$ a la valeur la plus basse

---

## 3. Cohérence avec les contraintes réelles d'exécution

| Contrainte | Statut |
|---|---|
| Min notionnel Alpaca (~155$) | ❌ Preset 2k-5k$ à 150$ — cf. A-CAP-003 |
| PDT rule (25k$ min pour day trading) | ✅ Transition margin à 25k$ |
| Swing-only pour comptes cash | ❌ Non activé — cf. A-CAP-001 |
| Liquidité suffisante pour la taille de position | ⚠️ Pas de vérification croisée taille/volume |
| Spreads compatibles avec les tailles | ⚠️ Spreads relâchés sur petits comptes |

---

## 4. Cohérence avec les profils stricts canoniques

Le profil `STRICT_SWING_CASH_FILTERS` (`core/filter_profiles.py`) définit :
- `min_close=10.0`, `min_avg_dollar_volume_20d=30M`, `max_volatility_ratio=0.9`
- `min_relative_strength_index=100`, `min_high_52w_proximity=0.75`, `min_weekly_trend_score=1.0`
- `min_atr_pct_20=0.015`, `max_atr_pct_20=0.06`, `min_market_cap=2B`
- `min_beta_126=0.8`, `max_spread_bps=40`, `earnings_blackout_days=0`

**Presets alignés avec le strict** :
- `capital_10001_25000` : Très proche, écarts justifiés
- `capital_50001_100000` : Aligné sur les critères principaux

**Presets significativement divergents** :
- `capital_0_2000_eur` : Écarts majeurs sur 12 critères — justifiés mais risqués
- `capital_0_5000` : Écarts sur 9 critères
- `capital_100001_plus` : Plus strict que le canonique (justifié)

Tous les écarts sont documentés dans les `strict_profile_justifications` du YAML, ce qui est une bonne pratique. ✅

---

## 5. Recommandations globales

1. **Activer `execution_swing_only=true` sur tous les presets** (ou a minima sur les comptes cash)
2. **Différencier les paramètres de drawdown breaker** par tranche de capital
3. **Remonter `risk_min_position_notional` à ≥155$** pour le preset 2k-5k$
4. **Uniformiser la devise** de référence (USD)
5. **Documenter le rationnel du seuil cash→margin** à 25k$
6. **Réviser `max_drawdown_pct`** pour qu'il soit dégressif avec le capital (un grand compte devrait être plus strict, pas moins)
7. **Ajouter un test automatisé** de cohérence inter-presets dans la CI

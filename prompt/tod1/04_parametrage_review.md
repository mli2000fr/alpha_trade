# 04 — Revue des Paramétrages — Alpha Trade

> **Date** : mai 2026 | Fichiers : `config.yaml`, `config/capital_presets.yaml`

---

## 1. `config.yaml` — Revue globale

### 1.1 Base de données

```yaml
database:
  host: localhost
  port: 3306
  user: "${LOGIN_DB}"
  password: "${PASSWORD_DB}"
  name: alpha_trade
```

**Verdict** : ✅ Cohérent — credentials via env, pas de plain text. Pool (2+3) raisonnable pour usage single-machine.  
**SSL** : ✅ Activable via `DB_SSL_CA_PATH` env var (`database/connection.py:97-111`). Non activé par défaut (LAN dev non cassé) — documenter la procédure dans le runbook opérateur.

---

### 1.2 Alpaca multi-comptes

```yaml
alpaca:
  accounts:
    - id: default / test1 / test2 (paper)
```

**Verdict** : ✅ Cohérent — 3 comptes paper configurés, credentials via placeholders. Aucun compte live actif (commenté).  
**Observation** : `test1` et `test2` semblent être des comptes de test permanent. Leur cycle de vie (utilisation, désactivation) mérite documentation.

---

### 1.3 Risk global

```yaml
risk:
  max_drawdown: 0.15       # 15%
  max_daily_loss: 0.05     # 5%
```

**Verdict** : ✅ Cohérent avec les presets. Ce sont les valeurs par défaut du preset 50k–100k.  
**Observation** : Ces valeurs globales sont écrasées par les presets de capital. Leur rôle de "floor de sécurité" quand aucun preset n'est sélectionné est documenté mais pas testé explicitement.

---

### 1.4 Market regimes

```yaml
market_regimes:
  enabled: true
  macro_provider: eodhd
  vix: { enabled: true, high_threshold: 25.0 }
  yields: { enabled: false }
  earnings_shield: { enabled: false }
  buyback_blackout: { enabled: false }
  patterns: { tax_day: false, sept_slump: false, ... }
```

**Verdict** : 🟡 Cohérent mais restrictif. La plupart des patterns et protections avancées sont désactivés. La couche Market-Aware est donc partiellement active :
- **Active** : VIX threshold, sentiment circuit breaker
- **Inactif** : yields, earnings shield, buyback blackout, tous les patterns calendaires

**Risque** : Un opérateur qui lit la documentation complète peut croire que `santa_rally` ou `sept_slump` sont actifs alors qu'ils sont tous à `enabled: false`.  
**Recommandation** : Ajouter commentaires dans config.yaml : "# patterns désactivés par défaut — activer progressivement après validation backtest"

---

### 1.5 Provider OHLCV

```yaml
market_data:
  bars_provider: eodhd
  fallback_on_failure: true
```

**Verdict** : ✅ Cohérent — EODHD comme primaire, fallback activé. Convention `data_adjustment='split'` cohérente dans tout le code.

---

### 1.6 EODHD config

```yaml
eodhd:
  daily_quota: 100000
  soft_quota_warn: 80000
  bulk_publish_offset_hours: 2
  splits_cache_ttl_days: 7
  circuit_breaker: { consecutive_failures: 5, cooldown_minutes: 30 }
```

**Verdict** : ✅ Cohérent — quotas bien dimensionnés pour le plan All-In-One EODHD (100k calls/jour). Circuit breaker présent.  
**Observation** : `bulk_publish_offset_hours: 2` signifie que le bulk EOD n'est fiable qu'à partir de 18h00 EST le jour J. Un run de 17h00 pourrait lire des données incomplètes.

---

### 1.7 Conviction weights

```yaml
conviction:
  quant_weight: 0.75
  sentiment_weight: 0.15
  macro_weight: 0.10
```

**Verdict** : ✅ Cohérent avec `DOC_FONCTIONNELLE.md §3.3` (75%/15%/10%). Valeurs raisonnables pour swing trade US.  
**Observation** : La pondération conviction (risk) est 40% quant + 60% ML — différente de ces poids signal_aggregator. Clarifier dans la doc que ces deux pondérations jouent à des niveaux différents (score signal vs conviction portefeuille).

---

### 1.8 Trailing stop

```yaml
risk_management:
  trailing_stop:
    enabled: false
    mode: dynamic_atr
    atr_multiplier: 2.5
    break_even_after_atr_multiple: 2.0
```

**Verdict** : 🟡 Configuration cohérente mais désactivée (`enabled: false`). Le stop initial reste fixe à 5% par défaut.  
**Risque** : En paper trading, ne pas utiliser le trailing stop ATR dynamique prive d'un outil de gestion des sorties plus adaptatif. Recommandé d'activer en paper d'abord.

---

## 2. `config/capital_presets.yaml` — Revue par tranche

### 2.1 Tranche `0 → 2 000 €` (`capital_0_2000_eur`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 10 | ❌ **Incohérent** — description dit "3 lignes" |
| `risk_min_position_notional` | 150 USD | ⚠️ Trop bas — frais relatifs élevés |
| `risk_per_trade_pct` | 1.5% | ✅ Prudent |
| `risk_max_drawdown_pct` | 7% | ✅ Très strict pour micro-compte |
| `execution_account_type` | cash | ✅ Correct pour micro-compte EU |
| `execution_pdt_rule` | off | ✅ Correct (cash account) |
| `execution_swing_only` | true | ✅ Correct |
| `selector_min_close` | 10.0 USD | ✅ Aligné profil strict |
| `selector_min_market_cap` | 500M USD | ⚠️ Trop bas — peut inclure des small caps peu liquides |
| `selector_max_spread_bps` | 80 bps | ⚠️ Très permissif — coût d'exécution élevé |
| `selector_min_beta_126` | 0.65 | ✅ Relâché mais acceptable |

**Verdict** : **Fragile → Incohérent** sur `max_positions`. Corriger `max_positions: 3` est non-négociable. `selector_min_market_cap: 500M$` est trop bas pour un swing trade discipliné sur petit compte.

---

### 2.2 Tranche `2 001 → 5 000 $` (`capital_0_5000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 4 | ✅ Cohérent avec capital |
| `risk_min_position_notional` | 150 USD | ⚠️ Trop bas |
| `risk_per_trade_pct` | 2% | ⚠️ Légèrement élevé (~40–100 USD risqués) |
| `risk_max_drawdown_pct` | 8% | ✅ Strict |
| `selector_min_close` | 5.0 USD | ❌ **Sous le profil strict** (10.0) |
| `selector_min_market_cap` | 1B USD | ✅ Acceptable |
| `selector_max_spread_bps` | 60 bps | ⚠️ Encore permissif |
| `selector_min_beta_126` | 0.70 | ✅ |

**Verdict** : **Fragile** — `selector_min_close: 5.0` est le défaut le plus dangereux. Actions à 5–8 USD avec spread de 60 bps → coût d'exécution de 1.2% par aller-retour minimum, destructeur d'alpha sur swing trade.

---

### 2.3 Tranche `5 001 → 10 000 $` (`capital_5001_10000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 6 | ✅ |
| `risk_min_position_notional` | 200 USD | ✅ Acceptable |
| `risk_per_trade_pct` | 1.75% | ✅ |
| `risk_max_drawdown_pct` | 10% | ✅ |
| `selector_min_close` | 7.0 USD | ⚠️ Encore sous 10$ |
| `selector_min_market_cap` | 1.5B USD | ✅ |
| `selector_max_spread_bps` | 55 bps | ✅ Correct |
| `selector_min_beta_126` | 0.75 | ✅ |

**Verdict** : **Cohérent mais perfectible** — `min_close: 7.0` encore sous le seuil optimal de 10$. Sinon progression logique.

---

### 2.4 Tranche `10 001 → 25 000 $` (`capital_10001_25000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 8 | ✅ |
| `risk_min_position_notional` | 300 USD | ✅ |
| `risk_per_trade_pct` | 1.5% | ✅ (150–375 USD risqués) |
| `risk_max_drawdown_pct` | 12% | ✅ |
| `execution_account_type` | cash | ✅ (PDT évité) |
| `execution_pdt_rule` | off | ✅ (cash) |
| `selector_min_close` | 8.0 USD | ⚠️ Encore sous 10$ |
| `selector_min_market_cap` | 2B USD | ✅ Profil strict |
| `selector_max_spread_bps` | 50 bps | ✅ |

**Verdict** : **Cohérent** — transition vers les paramètres standard bien gérée. `min_close: 8.0` encore légèrement en dessous du profil strict canonique.

---

### 2.5 Tranche `25 001 → 50 000 $` (`capital_25001_50000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 12 | ✅ |
| `risk_min_position_notional` | 400 USD | ✅ |
| `risk_per_trade_pct` | 1.25% | ✅ |
| `risk_max_drawdown_pct` | 14% | ✅ |
| `execution_account_type` | margin | ✅ (> 25k$) |
| `execution_pdt_rule` | off | ❌ **Devrait être `auto`** — compte margin, si equity chute < 25k$ |
| `execution_swing_only` | true | ✅ |
| `selector_min_close` | 10.0 USD | ✅ Aligné profil strict |
| `selector_min_market_cap` | 2B USD | ✅ |
| `selector_max_spread_bps` | 45 bps | ✅ |

**Verdict** : **Cohérent mais perfectible** — PDT rule off sur margin est le défaut principal. Sinon, preset bien calibré.

---

### 2.6 Tranche `50 001 → 100 000 $` (`capital_50001_100000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 15 | ✅ |
| `risk_min_position_notional` | 500 USD | ✅ |
| `risk_per_trade_pct` | 1% | ✅ Standard |
| `risk_max_drawdown_pct` | 15% | ✅ Aligné `config.yaml` global |
| `execution_account_type` | margin | ✅ |
| `execution_pdt_rule` | off | ❌ Devrait être `auto` |
| `selector_min_close` | 10.0 USD | ✅ |
| `selector_min_market_cap` | 2B USD | ✅ |
| `selector_max_spread_bps` | 40 bps | ✅ Aligné profil strict |
| `risk_correlation_threshold` | 0.80 | ✅ Standard |
| `risk_enable_kelly` | false | ⚠️ Kelly désactivé sur tous les presets |

**Verdict** : **Cohérent** — preset de référence du projet. Seul PDT rule off restant à corriger.

---

### 2.7 Tranche `100 001 $+` (`capital_100001_plus`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 18 | ✅ |
| `risk_min_position_notional` | 750 USD | ✅ |
| `risk_per_trade_pct` | 0.8% | ✅ Conservateur |
| `risk_max_drawdown_pct` | 18% | ⚠️ Notable — tolérance plus large que les autres tranches |
| `execution_account_type` | margin | ✅ |
| `execution_pdt_rule` | off | ❌ Devrait être `auto` |
| `selector_min_close` | 12.0 USD | ✅ Plus strict |
| `selector_min_market_cap` | 3B USD | ✅ Large caps uniquement |
| `selector_max_spread_bps` | 35 bps | ✅ Très strict |
| `risk_correlation_threshold` | 0.78 | ✅ Plus strict |
| `trailing_r_multiple` | 1.1 | ✅ Légèrement plus agressif |

**Verdict** : **Cohérent** — preset grand compte bien calibré. `max_drawdown: 18%` est élevé mais justifiable sur grand compte avec plus de diversification. PDT rule off restant à corriger.

---

## 3. Synthèse globale des paramétrages

| Tranche | Verdict | Issues principales |
|---|---|---|
| 0 → 2 000 € | **Incohérent** | max_positions=10 vs "3 lignes", min_market_cap trop bas |
| 2 001 → 5 000 $ | **Fragile** | min_close=5$ (risque frais), PDT OK (cash) |
| 5 001 → 10 000 $ | **Cohérent mais perfectible** | min_close=7$ encore |
| 10 001 → 25 000 $ | **Cohérent** | min_close=8$ |
| 25 001 → 50 000 $ | **Cohérent mais perfectible** | PDT rule off sur margin |
| 50 001 → 100 000 $ | **Cohérent** | PDT rule off, Kelly désactivé |
| 100 001 $+ | **Cohérent** | PDT rule off, max_drawdown 18% notable |

### Actions prioritaires

1. **P1** : Corriger `capital_0_2000_eur.risk_max_positions: 3`
2. **P2** : Uniformiser `selector_min_close: 10.0` sur les 3 premières tranches
3. **P2** : Passer `execution_pdt_rule: auto` sur les 3 tranches margin
4. **P3** : Activer Kelly (au moins sur presets ≥ 50k$) avec `max_kelly_fraction: 0.25` comme garde-fou
5. **P3** : Activer trailing stop ATR en paper (au moins `capital_50001_100000` et `capital_100001_plus`)


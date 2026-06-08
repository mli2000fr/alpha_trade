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
| `risk_max_positions` | ~~10~~ → **3** | ✅ **Corrigé Sprint S1** — description "3 lignes" maintenant cohérente |
| `risk_min_position_notional` | ~~150 USD~~ → **500 USD** | ✅ **Corrigé Sprint S1** — frais relatifs acceptables (500 USD × 1 USD Alpaca = 0.2%) |
| `risk_per_trade_pct` | 1.5% | ✅ Prudent |
| `risk_max_drawdown_pct` | 7% | ✅ Très strict pour micro-compte |
| `execution_account_type` | cash | ✅ Correct pour micro-compte EU |
| `execution_account_type` + `execution_swing_only` | cash + true | ✅ Correct pour un micro-compte discipliné — **clarifié Sprint S1** ✅ |
| `execution_swing_only` | true | ✅ Correct |
| `selector_min_close` | 10.0 USD | ✅ Aligné profil strict |
| `selector_min_market_cap` | 500M USD | ⚠️ Trop bas — peut inclure des small caps peu liquides |
| `selector_max_spread_bps` | 80 bps | ⚠️ Très permissif — coût d'exécution élevé |
| `selector_min_beta_126` | 0.65 | ✅ Relâché mais acceptable |

**Verdict** : ✅ **Corrigé Sprint S1** — `risk_max_positions: 3`, `risk_min_position_notional: 500.0 USD`, conventions cash clarifiées. Tests de non-régression 13/13 passent.

---

### 2.2 Tranche `2 001 → 5 000 $` (`capital_0_5000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 4 | ✅ Cohérent avec capital |
| `risk_min_position_notional` | 150 USD | ⚠️ Trop bas |
| `risk_per_trade_pct` | 2% | ⚠️ Légèrement élevé (~40–100 USD risqués) |
| `risk_max_drawdown_pct` | 8% | ✅ Strict |
| `selector_min_close` | ~~5.0 USD~~ → **10.0 USD** | ✅ **Corrigé Sprint S2** — aligné STRICT_SWING_CASH_FILTERS.min_close=10.0 |
| `selector_min_market_cap` | 1B USD | ✅ Acceptable |
| `selector_max_spread_bps` | 60 bps | ⚠️ Encore permissif |
| `selector_min_beta_126` | 0.70 | ✅ |

**Verdict** : ✅ **`selector_min_close` corrigé Sprint S2** — `10.0 USD` aligné profil strict. Actions < 10$ éliminées (frais relatifs disproportionnés sur Alpaca).

---

### 2.3 Tranche `5 001 → 10 000 $` (`capital_5001_10000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 6 | ✅ |
| `risk_min_position_notional` | 200 USD | ✅ Acceptable |
| `risk_per_trade_pct` | 1.75% | ✅ |
| `risk_max_drawdown_pct` | 10% | ✅ |
| `selector_min_close` | ~~7.0 USD~~ → **10.0 USD** | ✅ **Corrigé Sprint S2** — aligné profil strict |
| `selector_min_market_cap` | 1.5B USD | ✅ |
| `selector_max_spread_bps` | 55 bps | ✅ Correct |
| `selector_min_beta_126` | 0.75 | ✅ |

**Verdict** : ✅ **`selector_min_close` corrigé Sprint S2** — `10.0 USD`. Progression logique entre tranches maintenue.

---

### 2.4 Tranche `10 001 → 25 000 $` (`capital_10001_25000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 8 | ✅ |
| `risk_min_position_notional` | 300 USD | ✅ |
| `risk_per_trade_pct` | 1.5% | ✅ (150–375 USD risqués) |
| `risk_max_drawdown_pct` | 12% | ✅ |
| `execution_account_type` | cash | ✅ |
| `execution_swing_only` | true | ✅ |
| `selector_min_close` | ~~8.0 USD~~ → **10.0 USD** | ✅ **Corrigé Sprint S2** — aligné profil strict |
| `selector_min_market_cap` | 2B USD | ✅ Profil strict |
| `selector_max_spread_bps` | 50 bps | ✅ |

**Verdict** : ✅ **`selector_min_close` corrigé Sprint S2** — `10.0 USD`. Transition vers paramètres standard bien gérée.

---

### 2.5 Tranche `25 001 → 50 000 $` (`capital_25001_50000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 12 | ✅ |
| `risk_min_position_notional` | 400 USD | ✅ |
| `risk_per_trade_pct` | 1.25% | ✅ |
| `risk_max_drawdown_pct` | 14% | ✅ |
| `execution_account_type` | margin | ✅ (> 25k$) |
| `execution_account_type` | margin | ✅ **Corrigé Sprint S2** — tranche margin clarifiée |
| `execution_swing_only` | true | ✅ |
| `selector_min_close` | 10.0 USD | ✅ Aligné profil strict |
| `selector_min_market_cap` | 2B USD | ✅ |
| `selector_max_spread_bps` | 45 bps | ✅ |

**Verdict** : ✅ **Contraintes margin clarifiées Sprint S2** — tranche cohérente pour usage margin.

---

### 2.6 Tranche `50 001 → 100 000 $` (`capital_50001_100000`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 15 | ✅ |
| `risk_min_position_notional` | 500 USD | ✅ |
| `risk_per_trade_pct` | 1% | ✅ Standard |
| `risk_max_drawdown_pct` | 15% | ✅ Aligné `config.yaml` global |
| `execution_account_type` | margin | ✅ |
| `execution_swing_only` | true | ✅ |
| `selector_min_close` | 10.0 USD | ✅ |
| `selector_min_market_cap` | 2B USD | ✅ |
| `selector_max_spread_bps` | 40 bps | ✅ Aligné profil strict |
| `risk_correlation_threshold` | 0.80 | ✅ Standard |
| `risk_enable_kelly` | false | ⚠️ Kelly désactivé sur tous les presets |

**Verdict** : ✅ **Preset de référence clarifié Sprint S2** — toutes les anomalies P2 résolues.

---

### 2.7 Tranche `100 001 $+` (`capital_100001_plus`)

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `risk_max_positions` | 18 | ✅ |
| `risk_min_position_notional` | 750 USD | ✅ |
| `risk_per_trade_pct` | 0.8% | ✅ Conservateur |
| `risk_max_drawdown_pct` | 18% | ⚠️ Notable — tolérance plus large que les autres tranches |
| `execution_account_type` | margin | ✅ |
| `execution_swing_only` | true | ✅ |
| `selector_min_close` | 12.0 USD | ✅ Plus strict |
| `selector_min_market_cap` | 3B USD | ✅ Large caps uniquement |
| `selector_max_spread_bps` | 35 bps | ✅ Très strict |
| `risk_correlation_threshold` | 0.78 | ✅ Plus strict |
| `trailing_r_multiple` | 1.1 | ✅ Légèrement plus agressif |

**Verdict** : ✅ **Preset grand compte clarifié Sprint S2**. `max_drawdown: 18%` est élevé mais justifiable sur grand compte avec plus de diversification.

---

## 3. Synthèse globale des paramétrages

| Tranche | Verdict | Issues principales |
|---|---|---|
| 0 → 2 000 € | ✅ **Corrigé Sprint S1** | max_positions=3 ✅, min_notional=500$ ✅, conventions cash clarifiées ✅ |
| 2 001 → 5 000 $ | ✅ **Corrigé Sprint S2** | min_close=10$ ✅ (was 5$) |
| 5 001 → 10 000 $ | ✅ **Corrigé Sprint S2** | min_close=10$ ✅ (was 7$) |
| 10 001 → 25 000 $ | ✅ **Corrigé Sprint S2** | min_close=10$ ✅ (was 8$) |
| 25 001 → 50 000 $ | ✅ **Corrigé Sprint S2** | tranche margin clarifiée ✅ |
| 50 001 → 100 000 $ | ✅ **Corrigé Sprint S2** | tranche margin clarifiée ✅, Kelly désactivé (P3) |
| 100 001 $+ | ✅ **Corrigé Sprint S2** | tranche margin clarifiée ✅, max_drawdown 18% notable |

### Actions prioritaires

1. ✅ ~~**P1** : Corriger `capital_0_2000_eur.risk_max_positions: 3`~~ — **FAIT Sprint S1**
2. ✅ ~~**P2** : Uniformiser `selector_min_close: 10.0` sur toutes les tranches~~ — **FAIT Sprint S2**
3. ✅ ~~**P2** : Clarifier les tranches margin sur les 3 presets concernés~~ — **FAIT Sprint S2**
4. **P3** : Activer Kelly (au moins sur presets ≥ 50k$) avec `max_kelly_fraction: 0.25` comme garde-fou
5. **P3** : Activer trailing stop ATR en paper (au moins `capital_50001_100000` et `capital_100001_plus`)


# 04 — Revue de paramétrage (presets capitaux + configs)

> Sources : `config.yaml`, `config/capital_presets.yaml`,
> `selector/strict_filter_profiles.py` (référencé par les tests),
> `tests/test_capital_preset_*`.

## 1. Vue d'ensemble — monotonie attendue

| Clé | Sens souhaité quand equity ↑ | Observation |
|---|---|---|
| `risk_per_trade_pct` | ↓ (plus d'equity, moins de % par trade) | ✅ 1.5 → 0.8 % |
| `risk_max_positions` | ↑ | ✅ 3 → 18 |
| `risk_max_position_weight` | ↓ | ✅ 0.35 → 0.08 |
| `risk_max_sector_weight` | ↓ | ✅ 0.55 → 0.25 |
| `risk_min_position_notional` | ↑ | ✅ 500 → 750 |
| `risk_max_drawdown_pct` | ↑ (gros compte plus patient) | ✅ 7 → 18 % — *à justifier doc* |
| `risk_max_daily_loss_pct` | ↑ légèrement | ✅ 2.5 → 5 % |
| `risk_correlation_threshold` | ↓ (plus stricte) | ✅ 0.92 → 0.78 |
| `screener_min_relative_strength_index` | ↑ | ✅ 90 → 102 |
| `selector_min_high_52w_proximity` | ↑ | ✅ 0.55 → 0.78 |
| `selector_min_weekly_trend_score` | ↑ | ✅ 0.65 → 0.95 |
| `selector_max_spread_bps` | ↓ | ✅ 80 → 35 |
| `selector_min_close` | stable ≥ 10 | ⚠️ 10 sur 0–25k$ — restrictif micro (A-008) |
| `selector_max_anomaly_count` | ↓ | ⚠️ 28 → 18 : *plus le compte est petit, plus on tolère* → A-014 |

## 2. Audit par tranche

### 2.1 — `0 → 2 000 €` (`capital_0_2000_eur`)

| Aspect | Constat |
|---|---|
| risk_per_trade 1.5 % × 3 lignes = 4.5 % equity exposé | **Fragile** : un crash sectoriel sur deux lignes corrélées peut détruire 6–8 %. |
| min_position_notional 500 $ + 3 lignes = ~1500 $ déployés sur 2150 $ | OK mais cash buffer faible. |
| execution_pdt_rule "off" car cash | Correct (PDT ne s'applique pas en cash). |
| screener_min_relative_strength_index 90 + selector_min_close 10 + min_market_cap 500M$ | **Univers très restreint** : risque universe vide en regime baissier. |
| selector_max_anomaly_count 28 | **Incohérent** (A-014). |
| trailing_stop fixé via execution_trailing_r_multiple 1.0 | OK mais pas de protection BE automatique côté config. |

**Verdict : ⚠️ Fragile.** Acceptable pédagogiquement, dangereux si l'opérateur
prend les défauts comme paramétrage swing sérieux. **Recommandation** :
mode "discovery" explicite ou warning IHM "ce preset assume une perte de
30 % acceptable sur 6 mois".

### 2.2 — `2 001 → 5 000 $` (`capital_0_5000`)

| Aspect | Constat |
|---|---|
| risk_per_trade 2 % × 4 lignes = 8 % equity exposé théorique | **Limite haute**. |
| min_position_notional 150 $ | OK mais frais relatifs très forts. |
| selector_min_close 10 (réaligné STRICT, A-007 fix doc) | Correct. |
| Univers selector | Médiocre densité. |

**Verdict : ⚠️ Fragile mais réaliste**. Demande discipline opérateur.

### 2.3 — `5 001 → 10 000 $` (`capital_5001_10000`)

| Aspect | Constat |
|---|---|
| 1.75 % × 6 = 10.5 % exposé | Acceptable swing standard. |
| min_position_notional 200 $ | OK. |
| sector_cap 0.35 | Correct. |

**Verdict : ✅ Cohérent mais perfectible** (Kelly off, A-006).

### 2.4 — `10 001 → 25 000 $` (`capital_10001_25000`)

| Aspect | Constat |
|---|---|
| 1.5 % × 8 = 12 % exposé | Standard swing. |
| Univers selector large ouvert (selection_size=35) | OK. |
| execution_account_type cash + PDT off | OK car < 25 k$ (PDT margin only). |

**Verdict : ✅ Cohérent**. Tranche pivot où l'application devient pleinement
investissable.

### 2.5 — `25 001 → 50 000 $` (`capital_25001_50000`)

| Aspect | Constat |
|---|---|
| 1.25 % × 12 = 15 % exposé | Diversification correcte. |
| margin + PDT "auto" | ✅ A-006 fix. |
| selector_max_spread_bps 45 | OK. |

**Verdict : ✅ Cohérent — preset cible production opérateur autonome.**

### 2.6 — `50 001 → 100 000 $` (`capital_50001_100000`)

| Aspect | Constat |
|---|---|
| 1 % × 15 = 15 % exposé | Standard pro discret. |
| Tous seuils proches du profil strict canonique | ✅. |

**Verdict : ✅ Cohérent — preset nominal du projet.**

### 2.7 — `100 001 $ +` (`capital_100001_plus`)

| Aspect | Constat |
|---|---|
| 0.8 % × 18 = 14.4 % exposé | Diversification très large. |
| max_drawdown 18 % | **Très généreux** — à documenter. |
| selector filtres les plus stricts | OK. |

**Verdict : ✅ Cohérent**. Recommandation : ajouter sous-tranches
500k$+, 1M$+ si usage réel évolue.

## 3. Cohérence globale config.yaml

| Bloc | Constat |
|---|---|
| `risk: max_drawdown 0.15 / max_daily_loss 0.05` | Cohérent avec tranche 50–100k. |
| `market_regimes.enabled: true` | ✅ activé — bonne valeur par défaut. |
| `market_regimes.vix.high_threshold: 25.0` | Standard. |
| `market_regimes.macro_provider: eodhd` | ⚠️ A-007. |
| `market_regimes.earnings_shield.enabled: false` | À documenter pourquoi off par défaut (sentiment_circuit_breaker préféré ?). |
| `risk_management.trailing_stop.enabled: false` | ⚠️ trailing manuel ; documenter contexte d'activation. |
| `market_data.bars_provider: eodhd` + `fallback_on_failure: true` | OK mais A-013. |
| `conviction: quant 0.75 / sentiment 0.15 / macro 0.10` | Cohérent doc, sentiment poids modeste = prudent. |

## 4. Conclusions par "Cohérent / Fragile / Dangereux"

| Tranche | Verdict |
|---|---|
| 0 → 2 000 € | **Fragile** |
| 2 001 → 5 000 $ | **Cohérent mais fragile** |
| 5 001 → 10 000 $ | **Cohérent mais perfectible** |
| 10 001 → 25 000 $ | **Cohérent** |
| 25 001 → 50 000 $ | **Cohérent** |
| 50 001 → 100 000 $ | **Cohérent** (preset nominal) |
| 100 001 $ + | **Cohérent** |

Aucun preset n'est jugé **dangereux en production** ; deux sont **fragiles**
(0–2k€, 2–5k$) et demandent une communication explicite à l'opérateur.

## 5. Recommandations transverses

1. Renommer `selector_min_relative_strength_index` → `selector_min_ibd_rs_rank` (A-028).
2. Inverser `selector_max_anomaly_count` (monotonie correcte) — A-014.
3. Documenter pourquoi Kelly reste off (A-006).
4. Default `macro_provider: composite` (A-007).
5. Ajouter test propriété global "monotonie 7 tranches" avec assertions
   strictes par clé (`tests/test_capital_presets.py` à étendre).


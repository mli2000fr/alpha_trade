# 04 — Revue détaillée des paramétrages

## 1. `config.yaml` racine

| Section | Constat | Verdict |
|---|---|---|
| `database` (lignes 1-6) | Valeurs par défaut `user`/`pass` mais le code les rejette via `core.secrets`. | ✅ cohérent (secrets en env) |
| `alpaca.api_key/secret_key` (10-11) | Valeurs littérales `"PK..."` / `"..."` rétrocompat | ⚠️ **anti-pattern**, à supprimer (A-013) |
| `alpaca.accounts` (16-36) | 3 comptes paper `default/test1/test2`, `live1` commenté | ✅ propre, placeholders `${VAR}` |
| `risk.max_drawdown=0.15` (39) | Seuil global, **non override par préset** | ⚠️ A-011 (P1) |
| `risk.max_daily_loss=0.05` (40) | idem | ⚠️ A-011 (P1) |
| `market_data.bars_provider=eodhd` (51) | Provider primaire actuel | ⚠️ doc non alignée (A-003, A-004, A-005) |
| `market_data.fallback_on_failure=true` (52) | Flag de fallback | ⚠️ comportement réel à documenter |
| `eodhd.enabled=false` (55) | **Clé jamais lue par le code applicatif** | ❌ **A-002 (P0) — paramètre fantôme** |
| `eodhd.cache_dir`, `daily_quota`, `circuit_breaker`, etc. | OK | ✅ |

## 2. `config/capital_presets.yaml` — analyse par tranche

### Tranche **0 → 5 000 $** (`capital_0_5000`)

| Catégorie | Valeur | Évaluation |
|---|---|---|
| `risk_per_trade_pct` | 0.02 (2 %) | Élevé pour swing strict, mais rationnel pour faire « vivre » un petit compte |
| `risk_max_positions` | 4 | Concentration assumée |
| `risk_max_position_weight` | 0.20 | OK petit compte |
| `risk_max_sector_weight` | 0.40 | Permissif (40 %) |
| `risk_min_position_notional` | 150 $ | **Tension** avec ATR strict ⇒ A-010 |
| `risk_correlation_threshold` | 0.90 | Permissif (laisse passer titres très corrélés) |
| `risk_enable_kelly` | false | ✅ prudent |
| `execution_account_type` | cash | ✅ pas de PDT |
| `execution_pdt_rule` | "off" | ✅ |
| `execution_swing_only` | true | ✅ |
| `execution_trailing_r_multiple` | 1.0 | ✅ swing classique |
| `screener_liquidity_threshold_usd` | 5e6 | Faible mais cohérent petit compte |
| `screener_min_relative_strength_index` | 95.0 | Très élevé |
| `selector_min_close` | 5 $ | Permissif |
| `selector_min_relative_strength_index` | 95.0 | Très exigeant pour petit compte (vs strict canonique 100) |
| `selector_min_market_cap` | 1e9 | Mid cap+ obligatoire |
| `selector_min_beta_126` | 0.70 | Permissif |
| `selector_max_spread_bps` | 60 | Tolérant |
| `selector_earnings_blackout_days` | 2 | Léger (vs strict 3) |
| `selector_max_anomaly_count` | 25 | Tolérant |
| `selector_require_above_ma200` | true | ✅ |

**Verdict** : **fragile mais cohérent** — l'investissabilité réelle dépend de
la combinaison ATR + min_notional. Risque de pipeline rendu inutile en
pratique. Recommandation : télémétrie sizing (A-010), réduire min_notional
à 100 $, ou clarifier dans la doc que ce préset est un « entry-level
hibernating ».

### Tranche **5 001 → 10 000 $** (`capital_5001_10000`)

- Resserrement progressif : RS 97, ATR 0.0125-0.075, market cap 1.5e9, spread
  55, blackout 3.
- `risk_max_positions=6`, `risk_min_position_notional=200`.
- **Verdict** : **cohérent mais perfectible** — RS 97 reste extrêmement
  exigeant ; bascule progressive vers les seuils stricts.

### Tranche **10 001 → 25 000 $** (`capital_10001_25000`)

- RS 100 (strict canonique atteint), market cap 2e9, spread 50, blackout 3.
- Toujours `cash` (PDT US déclenche à 25 000 $).
- `risk_max_positions=8`, `risk_min_position_notional=300`.
- **Verdict** : **cohérent** — bonne transition vers le profil standard.

### Tranche **25 001 → 50 000 $** (`capital_25001_50000`)

- Bascule `execution_account_type=margin` ✅
- `selector_min_weekly_trend_score=0.90`, market cap 2e9, spread 45.
- `risk_max_positions=12`, `risk_per_trade_pct=0.0125`.
- **Verdict** : **cohérent** — préset équilibré.

### Tranche **50 001 → 100 000 $** (`capital_50001_100000`) — **standard**

- **Strict swing cash** quasi nominal (cf. `STRICT_SWING_CASH_FILTERS`,
  `core/filter_profiles.py:239-263`).
- `selector_min_weekly_trend_score=1.0` ⚠️ A-009 (P1) — risque univers vide.
- `risk_max_positions=15`, `risk_per_trade_pct=0.01`, sector cap 28 %.
- **Verdict** : **cohérent** — modulo A-009 à valider empiriquement.

### Tranche **100 001 $+** (`capital_100001_plus`)

- Le plus strict : RS 102, market cap 3e9, spread 35, blackout 4, beta 0.90,
  `selector_min_weekly_trend_score=1.0` (idem A-009).
- `risk_max_positions=18`, `risk_per_trade_pct=0.008`, `trailing_r_multiple=1.1`.
- **Verdict** : **cohérent mais perfectible** — idem A-009 ; RS 102 et beta
  0.90 combinés peuvent vider l'univers en marché baissier ⇒ assouplissement
  conditionnel à prévoir.

## 3. Cohérence des paramètres entre eux

| Question | Réponse |
|---|---|
| Risk per trade × max positions ≤ 100 % ? | 0.02 × 4 = 8 % ; 0.01 × 15 = 15 % ; 0.008 × 18 = 14.4 % → ✅ |
| Sector cap × max positions cohérent ? | 0.40 × 4 = 1.6 (>1, donc effectif=1) ; 0.25 × 18 = 4.5 → ✅ |
| Spread max × min_close cohérent ? | Spread 35 bps sur titres ≥ 12 $ → ~4 cents ; OK |
| Trailing 1.0R compatible avec ATR 1.5–6 % ? | ✅ |
| Blackout earnings ≥ 2 jours partout ? | ✅ |
| `execution_swing_only=true` partout ? | ✅ → cohérent avec exclusion PDT |
| `risk_enable_kelly=false` partout ? | ✅ — politique prudente |

## 4. Cohérence preset ↔ contraintes d'exécution réelles

| Tranche | Account type | Liquidité Alpaca | Verdict |
|---|---|---|---|
| 0–5k | cash | OK (settle T+2) | ✅ |
| 5–10k | cash | OK | ✅ |
| 10–25k | cash | OK | ✅ |
| 25–50k | margin | Buying power × 2 | ✅ |
| 50–100k | margin | idem | ✅ |
| 100k+ | margin | idem | ✅ |

## 5. Cohérence preset ↔ qualité données upstream

- Avec `bars_provider=eodhd`, **volume consolidé** disponible → seuils
  `screener_liquidity_threshold_usd` réalistes (5–15 M$).
- Si bascule vers Alpaca IEX (rétrocompat), **volume sous-évalué x30-50**
  (cf. `doc/dataIntegrityEngine.md:9-10`) → seuils deviennent prohibitifs.
- **⚠️ Aucun garde-fou n'empêche un préset de capital de tourner avec un
  provider incohérent.** Ajouter un check au lancement (lié à A-023).

## 6. Cohérence preset ↔ profil strict canonique

| Paramètre | Strict canonique | 0-5k | 100k+ | Cohérence |
|---|---|---|---|---|
| `min_close` | 10 | 5 | 12 | ✅ progressif |
| `min_avg_dollar_volume_20d` | 30M | 10M | 40M | ✅ |
| `max_volatility_ratio` | 0.9 | 1.0 | 0.85 | ✅ |
| `min_relative_strength_index` | 100 | 95 | 102 | ✅ |
| `min_high_52w_proximity` | 0.75 | 0.65 | 0.78 | ✅ |
| `min_weekly_trend_score` | 1.0 | 0.75 | 1.0 | ⚠️ A-009 |
| `min_market_cap` | 2e9 | 1e9 | 3e9 | ✅ |
| `min_beta_126` | 0.8 | 0.7 | 0.9 | ✅ |
| `max_spread_bps` | 40 | 60 | 35 | ✅ |
| `earnings_blackout_days` | 3 | 2 | 4 | ✅ |
| `require_above_ma200` | true | true | true | ✅ |

## 7. Verdicts synthétiques par tranche

| Tranche | Verdict | Action recommandée |
|---|---|---|
| 0–5 000 $ | **fragile mais cohérent** | A-010, A-011 ; clarifier doc « investissabilité limitée » |
| 5 001–10 000 $ | **cohérent mais perfectible** | A-011 ; éventuellement RS 95 plutôt que 97 |
| 10 001–25 000 $ | **cohérent** | A-011 |
| 25 001–50 000 $ | **cohérent** | RAS critique |
| 50 001–100 000 $ | **cohérent** | A-009 (weekly_trend 1.0) |
| 100 001 $+ | **cohérent mais perfectible** | A-009 + assouplissement conditionnel marché |

Aucune tranche n'est jugée **dangereuse en production**, mais les tranches
basses méritent un audit empirique sur la **proportion réelle de jours sans
ordre généré**.


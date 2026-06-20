# 04 — Revue des paramétrages et presets de capital

## Synthèse

Les presets de `config/capital_presets.yaml` sont détaillés et globalement orientés swing trade prudent. Ils couvrent les tranches demandées, mais la prudence réelle varie fortement : les petits comptes sont nécessairement concentrés ; les gros comptes deviennent plus stricts sur spread/liquidité/corrélation. Les valeurs sont exploitables si l’opérateur accepte que les tranches < 10k soient fragiles et que les frais/slippage réels peuvent manger une grande partie de l’alpha.

## Paramètres globaux critiques

| Paramètre | Fichier | Évaluation |
|---|---|---|
| `market_data.bars_provider: eodhd` | `config.yaml:181-183` | Correct et cohérent avec le code IHM/imports. |
| `market_data.fallback_on_failure: true` | `config.yaml:183` | **Incohérent** : non consommé par le code Python identifié. |
| `market_regimes.enabled: true` | `config.yaml:54-55` | Puissant mais doit être explicitement visible avant exécution. |
| `risk_management.trailing_stop.enabled: false` | `config.yaml:162-170` | Prudence correcte ; trailing dynamique non imposé sans validation. |
| `conviction quant/sentiment/macro` | `config.yaml:201-205` | Cohérent avec un signal fusionné ; doit être calibré par backtest/ablation. |

## Analyse par tranche de capital

### 0 → 2 500 $

Preset le plus proche : `capital_0_2000` (`min_equity=0`, `max_equity=2000`) et début `capital_2001_5000` pour 2k–2.5k.

- Risk : `risk_per_trade_pct=1.5%`, 3 lignes, `max_position_weight=35%`, DD 7%.
- Selector : market cap min 500M, spread 80/100 bps, min close 10.
- Execution : cash, swing_only true.
- Verdict : **fragile**.
- Justification : concentration assumée, ticket 500 USD très lourd pour 2k, spreads permissifs. Cohérent pour apprendre en très petit cash, pas pour rendement institutionnel.
- Tests à ajouter : `tests/test_capital_presets_micro_account_executability.py` : equity 1500/2000/2500, vérifier que tailles proposées respectent min notional, concentration, cash constraints et frais/slippage simulés.

### 2 501 → 5 000 $

Preset : `capital_2001_5000`.

- Risk : 2% par trade, 4 positions, 20% max/ligne, min notional 150.
- Selector : ADV 10M, spread 60/80 bps, market cap 1B.
- Verdict : **cohérent mais perfectible**.
- Justification : meilleure diversification que micro, mais 2% par trade reste agressif ; spread IEX 80 bps doit être traité comme borne extrême, pas cible.
- Tests : simulation cash T+1, ordre minimum 155 USD, 4 positions, rejet si spread > seuil sans quote size suffisante.

### 5 001 → 10 000 $

Preset : `capital_5001_10000`.

- Risk : 1.75%, 6 positions, 18% max/ligne, DD 10%.
- Selector : ADV 15M, market cap 1.5B, spread 55/75.
- Verdict : **cohérent mais perfectible**.
- Justification : diversification raisonnable ; encore sensible aux frais, aux gaps et au slippage.
- Tests : univers non vide avec filtres stricts ; stress 6 lignes corrélées ; cash settlement.

### 10 001 → 25 000 $

Preset : `capital_10001_25000`.

- Risk : 1.5%, 8 positions, 15% max/ligne, DD 12%.
- Selector : ADV 20M, market cap 2B, spread 50/70.
- Verdict : **cohérent**.
- Justification : bon compromis swing cash ; le compte cash impose un settlement discipliné.
- Tests : equity 24k cash, settlement contraint les réinvestissements.

### 25 001 → 50 000 $

Preset : `capital_25001_50000`.

- Risk : 1.25%, 12 positions, 12% max/ligne, margin.
- Selector : ADV 25M, spread 45/65.
- Verdict : **cohérent**.
- Justification : passage margin logique au-dessus 25k ; diversification acceptable.
- Tests : equity 25,001 margin, buying power et contraintes de compte cohérents.

### 50 001 → 100 000 $

Preset : `capital_50001_100000`.

- Risk : 1%, 15 positions, 10% max/ligne, correlation threshold 0.80.
- Selector : ADV 30M, spread 40/60.
- Verdict : **cohérent et exploitable**.
- Justification : c’est le preset swing standard le plus équilibré.
- Tests : parité risk→execution sur 15 positions, secteur 28%, corrélation 0.80.

### 100 001 $+

Preset : `capital_100001_plus`.

- Risk : 0.8%, 18 positions, 8% max/ligne, max sector 25%, corrélation 0.78.
- Selector : ADV 40M, spread 35/55, market cap 3B, beta min 0.90.
- Verdict : **cohérent mais perfectible**.
- Justification : très prudent côté diversification et liquidité ; peut devenir trop restrictif en régime défensif et rater leaders low beta.
- Tests : univers non vide par régime, beta/sector constraints, capacity/slippage sur ordres plus importants.

## Cohérence générale risk / selector / screener / execution

- Les presets montent progressivement en diversification et discipline : cohérent.
- Les petits comptes relâchent les spreads et concentrent : réaliste mais fragile.
- `execution_swing_only=true` partout : cohérent avec style swing.
- Kelly désactivé partout : prudent.
- Les poids ML élevés (`prediction_weight=0.55/0.60`) doivent être conditionnés à un drift gate et à une preuve out-of-sample.
- Les seuils `selector_max_spread_bps_iex` doivent être interprétés comme garde-fou sur source IEX, pas comme équivalent NBBO.

## Tests transverses recommandés

| Test | Type | Fichier probable | Oracle |
|---|---|---|---|
| `test_all_capital_presets_cover_equity_without_gap` | config | `tests/test_capital_presets_ranges.py` | Toute equity demandée mappe à un preset unique. |
| `test_presets_are_monotonic_for_risk_and_liquidity` | config | `tests/test_capital_preset_monotonicity.py` | Plus le capital augmente, moins spread permis et plus ADV requis. |
| `test_micro_account_orders_are_executable_after_min_notional` | integration risk/execution | `tests/test_small_account_executability.py` | Pas d’ordre rejeté par min notional broker. |
| `test_pdt_auto_only_margin_under_25k` | unit execution | `tests/test_execution_config_pdt.py` | Cash = off ; margin <25k = auto applicable. |
| `test_selector_spread_iex_requires_quote_size` | unit selector | `tests/test_alpha_scanner_spread_filters.py` | Relax IEX seulement si quote size suffisante. |


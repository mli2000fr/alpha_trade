# 07 — Évaluation "Swing Trade Fitness"

## 1. Pertinence métier vs swing US

| Critère swing US | Couverture Alpha Trade | Note |
|---|---|---|
| Univers liquide (≥ 10M$/jour) | `selector_liquidity_threshold` 5–40 M$ selon tranche | ✅ |
| Force relative (RS rank IBD-like) | `screener_min_relative_strength_index` ≥ 90–102 | ✅ |
| Tendance moyen terme (MA200) | `selector_require_above_ma200: true` partout | ✅ |
| Proximité 52W high | `selector_min_high_52w_proximity` 0.55–0.78 | ✅ |
| Range historique / VCP | `selector_min_historical_range_score`, `factors.py` | ✅ |
| Volatilité ATR contenue | `selector_min/max_atr_pct_20` | ✅ |
| Stop ATR | `risk_management/position_sizer.py` | ✅ |
| Trailing stop | `execution_engine/protection_*`, `trailing_stop` config | ✅ |
| Earnings blackout | `selector_earnings_blackout_days`, `sync_earnings_calendar.py` | ✅ |
| Sector neutrality | `alpha_scanner` neutralisation sectorielle | ✅ |
| Corrélation portefeuille | `correlation_filter.py` | ✅ |
| Circuit breaker DD/daily loss | `risk_management/circuit_breaker.py` | ✅ |
| Regime overlay (VIX, sentiment) | `risk_management/regime_apply.py`, `market_regimes.*` | ✅ |
| Swing-only (interdiction day-trade) | `execution_swing_only: true` partout, compte cash/swing cohérent | ✅ |
| News sentiment | `event_sentiment/` FinBERT std + contextuel | ✅ (poids modeste 15 %) |
| ML conviction | `modelFactory/` multi-baselines + `ml_gate` | ✅ |

## 2. Réalisme exécution

| Risque | État |
|---|---|
| Spreads IEX biaisés | ⚠️ A-004 — limite réelle |
| Frais réels Alpaca (PFOF, SEC, TAF) | À confirmer côté `backtesting/fidelity.py` |
| Slippage sizing micro-compte | TCA présent (`execution_engine/tca.py`) mais pas exposé en KPI agrégé IHM |
| Wash sale | `tax/` + `tests/test_wash_sale.py` présent ✅ |
| Ordres partiels | Réconciliation OK ; observation post-fill propre |
| Réconciliation J+1 statement | 🟡 Job + vue IHM déjà présents ; parsing PDF natif encore optionnel |
| Doctrine failover broker | ✅ Runbook + panneau IHM opérateur présents |

## 3. Adéquation par tranche capital

| Tranche | Investissable ? | Réaliste ? | Recommandation |
|---|---|---|---|
| 0 → 2 000 € | Oui mais **éducatif** | ⚠️ Concentration assumée | Mode discovery |
| 2 001 → 5 000 $ | Oui | ⚠️ Frais relatifs forts | Discipline forte |
| 5 001 → 10 000 $ | Oui | ✅ Standard | OK |
| 10 001 → 25 000 $ | Oui | ✅ Pivot pleinement investissable | OK |
| 25 001 → 50 000 $ | Oui | ✅ Standard pro | OK |
| 50 001 → 100 000 $ | Oui | ✅ Preset nominal | OK |
| 100 001 $ + | Oui | ✅ | OK ; sous-tranches futures |

## 4. Faux sentiment de robustesse — points d'attention

1. **Sentiment + ML** : empilent de la complexité ; à challenger trimestriellement par Sharpe attribution (sentiment+ML doivent battre baseline quant net de frais).
2. **Backtest** : parité testée mais pas E2E avec sentiment+ML+macro (A-009).
3. **Quote IEX** : peut faire croire qu'une opportunité passe le filtre spread alors qu'en consolidé elle ne passerait pas — ou inversement.
4. **Fallback silencieux** OHLCV (A-013) : risque de croire que le pipeline a tourné en mode EODHD alors qu'on est repassé Alpaca IEX.
5. **Ordre `event_sentiment`** : le garde-fou runtime existe désormais, mais la télémétrie quote-bias et le runbook incident sentiment provider restent à compléter.

## 5. Verdict swing-trade

> **Adapté swing US à partir de 5–10 k$, pleinement adapté ≥ 10 k$, preset
> nominal calibré sur 50–100 k$.** En dessous de 5 k$, l'application reste
> utilisable mais l'opérateur doit accepter la concentration assumée.
> Au-dessus de 100 k$, l'application est cohérente mais gagne à exposer des
> sous-tranches granulaires si l'usage évolue.

**Score d'adéquation swing US réel : 7.5 / 10.**

Le code est aligné avec la pratique swing (filtres Minervini/VCP, force
relative, MA200, ATR, earnings blackout). Les écarts par rapport à un
desk pro sont surtout sur la **qualité quote/microstructure** et
l'**observabilité TCA agrégée**, pas sur la doctrine swing elle-même.


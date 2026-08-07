# 📊 Features du Global Ranking Model (LightGBM LambdaRank)

> **Batch** : 2026-07-28 | **Feature set** : expert + cross-sectional + sector_neutral
> **160 features** | **H3 IC** : 0.0152 | **H5 IC** : 0.0087
>
> Triées par importance H3 décroissante. L'importance est une moyenne sur les 8 splits walk-forward.

---

## Légende des suffixes

| Suffixe | Signification |
|---------|--------------|
| `_xs_rank` | Rang percentile cross-sectionnel intra-date [0,1] (1 = meilleur de l'univers) |
| `_zscore` | Z-score rolling (moyenne/écart-type mobiles) |
| `_sector_neutral` | Valeur − médiane du secteur → isole l'alpha spécifique au titre |
| `_x_bull` | Interaction avec le régime bull market (×1 si bull, ×0 sinon) |
| `_x_risk_off` | Interaction avec le régime risk-off (×1 si risk-off, ×0 sinon) |
| `_rank` | Rang percentile cross-sectionnel (version courte) |

---

## Tableau des features

| # | Feature | Imp. H3 | Catégorie | Description |
|:-:|---|--:|------|------------|
| 1 | `ema20_minus_sma20` | 70.2 | Tendance | Différence EMA(20) − SMA(20). Positif = momentum court terme haussier, l'EMA réagit plus vite que la SMA. |
| 2 | `momentum_20_minus_momentum_60` | 66.7 | Momentum | Momentum 20j − momentum 60j. Accélération/décélération du momentum. Positif = tendance s'accélère. |
| 3 | `momentum_252_vs_market` | 64.6 | Facteur | Rendement 252j du titre − rendement 252j du SPY. Sur-performance annuelle vs marché. |
| 4 | `momentum_250` | 63.7 | Momentum | Rendement cumulé sur ~1 an (250 séances). Tendance long terme. |
| 5 | `atr_14_norm_xs_rank` | 63.1 | Volatilité | ATR(14) / Close, rang cross-sectionnel. Volatilité normalisée par le prix. |
| 6 | `rolling_volatility_60_zscore` | 62.0 | Volatilité | Z-score de la volatilité 60j. Volatilité actuelle vs normale historique du titre. |
| 7 | `relative_strength_60_div_market_volatility` | 55.9 | Momentum/Risque | Force relative 60j divisée par la volatilité du marché. Ratio rendement/risque. |
| 8 | `sma250_distance_zscore` | 54.8 | Tendance | Z-score de la distance au SMA(250). Éloignement vs normale historique. |
| 9 | `sma50_minus_sma200` | 52.4 | Tendance | SMA(50) − SMA(200). Croix dorée/de la mort. Positif = tendance haussière. |
| 10 | `rolling_volatility_60_xs_rank` | 50.6 | Volatilité | Volatilité 60j, rang cross-sectionnel. Plus volatile que ses pairs ? |
| 11 | `rolling_volatility_20_zscore` | 49.8 | Volatilité | Z-score de la volatilité 20j. Volatilité court terme vs normale. |
| 12 | `momentum_250_zscore` | 48.2 | Momentum | Z-score du momentum 250j. Momentum long terme vs sa propre histoire. |
| 13 | `momentum_250_xs_rank` | 47.0 | Momentum | Momentum 250j, rang cross-sectionnel. Meilleur momentum long terme de l'univers ? |
| 14 | `relative_strength_60` | 42.9 | Momentum | Force relative sur 60j = rendement titre / rendement SPY. |
| 15 | `sma50_distance_x_bull` | 42.6 | Tendance × Régime | Distance au SMA(50) × bull market. Signal haussier amplifié en marché haussier. |
| 16 | `rolling_volatility_60` | 40.4 | Volatilité | Écart-type des rendements sur 60j. Volatilité historique. |
| 17 | `vol_ratio_20_60_xs_rank` | 38.2 | Volatilité | Ratio vol(20j) / vol(60j), rang cross-sectionnel. Expansion/contraction de volatilité. |
| 18 | `atr_14_norm` | 36.3 | Volatilité | ATR(14) / Close. Range vrai normalisé par le prix. |
| 19 | `rolling_volatility_10_xs_rank` | 36.1 | Volatilité | Volatilité 10j, rang cross-sectionnel. |
| 20 | `momentum_120_xs_rank` | 35.1 | Momentum | Momentum 120j (6 mois), rang cross-sectionnel. |
| 21 | `relative_strength_20_times_market_trend` | 34.0 | Momentum × Régime | Force relative 20j × force de la tendance marché. |
| 22 | `rolling_volatility_10_zscore` | 33.0 | Volatilité | Z-score de la volatilité 10j. |
| 23 | `momentum_120` | 32.8 | Momentum | Rendement cumulé sur 120j (~6 mois). |
| 24 | `sma20_minus_sma50` | 32.8 | Tendance | SMA(20) − SMA(50). Tendance court vs moyen terme. |
| 25 | `volume_ratio_5_div_volume_ratio_20` | 31.5 | Volume | Ratio volume 5j / volume 20j. Explosion récente du volume ? |
| 26 | `rsi_slope_xs_rank` | 29.5 | RSI | Pente du RSI(14), rang cross-sectionnel. Le RSI accélère ou décélère ? |
| 27 | `vol_ratio_20_60` | 29.4 | Volatilité | Ratio vol(20j) / vol(60j). Expansion de volatilité court terme. |
| 28 | `sma200_distance_zscore` | 29.1 | Tendance | Z-score distance au SMA(200). |
| 29 | `ema50_distance_xs_rank` | 28.8 | Tendance | Distance au EMA(50), rang cross-sectionnel. |
| 30 | `sma200_distance` | 28.4 | Tendance | (Close − SMA(200)) / SMA(200). Distance à la tendance long terme. |
| 31 | `sma50_distance` | 28.3 | Tendance | (Close − SMA(50)) / SMA(50). Distance à la tendance moyen terme. |
| 32 | `momentum_60_zscore` | 28.2 | Momentum | Z-score du momentum 60j. |
| 33 | `meanrev_signal` | 27.7 | Mean Reversion | Signal de retour à la moyenne. Écart du prix vs sa moyenne mobile. |
| 34 | `rsi_14_div_volatility_20` | 27.4 | RSI/Volatilité | RSI(14) / vol(20j). RSI ajusté au risque. |
| 35 | `sma10_distance_xs_rank` | 27.0 | Tendance | Distance au SMA(10), rang cross-sectionnel. |
| 36 | `sma200_distance_xs_rank` | 26.8 | Tendance | Distance au SMA(200), rang cross-sectionnel. |
| 37 | `momentum_120_zscore` | 26.6 | Momentum | Z-score du momentum 120j. |
| 38 | `sma50_distance_xs_rank` | 26.0 | Tendance | Distance au SMA(50), rang cross-sectionnel. |
| 39 | `vol_expansion` | 25.6 | Volatilité | Expansion de volatilité : vol(5j) − vol(20j). |
| 40 | `rolling_volatility_5_zscore` | 25.6 | Volatilité | Z-score de la volatilité 5j. |
| 41 | `rolling_volatility_20_x_bull` | 25.2 | Volatilité × Régime | Volatilité 20j × bull market. |
| 42 | `momentum_60` | 25.2 | Momentum | Rendement cumulé sur 60j (~3 mois). |
| 43 | `overnight_gap` | 23.7 | Prix | Gap overnight : (Open − Close_prev) / Close_prev. |
| 44 | `momentum_5_minus_momentum_20` | 23.4 | Momentum | Momentum 5j − momentum 20j. Renversement court terme. |
| 45 | `momentum_60_sector_neutral` | 23.3 | Sector Neutral | Momentum 60j − médiane du secteur. Alpha momentum vs pairs sectoriels. |
| 46 | `relative_strength_20_x_risk_off` | 23.3 | Momentum × Régime | Force relative 20j × risk-off. |
| 47 | `volatility_20_rank` | 23.0 | Volatilité | Rang cross-sectionnel de la volatilité 20j. |
| 48 | `sma20_distance_x_bull` | 22.5 | Tendance × Régime | Distance au SMA(20) × bull market. |
| 49 | `sma100_distance_xs_rank` | 22.5 | Tendance | Distance au SMA(100), rang cross-sectionnel. |
| 50 | `sma50_distance_sector_neutral` | 22.1 | Sector Neutral | Distance au SMA(50) − médiane du secteur. |
| 51 | `rolling_volatility_20` | 21.6 | Volatilité | Écart-type des rendements sur 20j. |
| 52 | `sma20_distance_x_risk_off` | 21.5 | Tendance × Régime | Distance au SMA(20) × risk-off. |
| 53 | `sma10_distance_zscore` | 21.4 | Tendance | Z-score distance au SMA(10). |
| 54 | `sma10_distance` | 21.2 | Tendance | (Close − SMA(10)) / SMA(10). Distance à la tendance très court terme. |
| 55 | `rsi_slope` | 20.8 | RSI | Pente du RSI(14) sur 5j. Direction du momentum RSI. |
| 56 | `sma250_distance` | 20.5 | Tendance | (Close − SMA(250)) / SMA(250). Distance à la tendance annuelle. |
| 57 | `rsi_21_zscore` | 20.4 | RSI | Z-score du RSI(21). |
| 58 | `rolling_volatility_10` | 20.1 | Volatilité | Écart-type des rendements sur 10j. |
| 59 | `dist_to_sma_5d` | 19.7 | Tendance | Distance au SMA sur 5j. Écart récent. |
| 60 | `rsi_14_sector_neutral` | 19.5 | Sector Neutral | RSI(14) − médiane du secteur. RSI relatif aux pairs. |
| 61 | `momentum_10` | 19.3 | Momentum | Rendement cumulé sur 10j. |
| 62 | `decay_5_10_xs_rank` | 19.3 | Dynamique | Taux de décroissance momentum 5→10j, rang cross-sectionnel. |
| 63 | `momentum_3` | 19.1 | Momentum | Rendement cumulé sur 3j. Très court terme. |
| 64 | `sma50_distance_zscore` | 19.0 | Tendance | Z-score distance au SMA(50). |
| 65 | `momentum_5_zscore` | 18.7 | Momentum | Z-score du momentum 5j. |
| 66 | `vol_ratio_20_60_x_bull` | 18.6 | Volatilité × Régime | Ratio vol(20/60) × bull market. |
| 67 | `momentum_10_xs_rank` | 18.6 | Momentum | Momentum 10j, rang cross-sectionnel. |
| 68 | `sma250_distance_xs_rank` | 18.6 | Tendance | Distance au SMA(250), rang cross-sectionnel. |
| 69 | `momentum_60_div_vol_60` | 17.9 | Momentum/Risque | Momentum 60j / vol 60j. Ratio de Sharpe simplifié. |
| 70 | `momentum_20_sector_neutral` | 17.8 | Sector Neutral | Momentum 20j − médiane du secteur. Alpha momentum court vs pairs. |
| 71 | `rolling_volatility_5` | 17.6 | Volatilité | Écart-type des rendements sur 5j. Volatilité immédiate. |
| 72 | `momentum_5_xs_rank` | 17.5 | Momentum | Momentum 5j, rang cross-sectionnel. |
| 73 | `momentum_60_x_bull` | 17.4 | Momentum × Régime | Momentum 60j × bull market. |
| 74 | `rolling_mean_return_5_xs_rank` | 17.2 | Rendement | Rendement moyen 5j, rang cross-sectionnel. |
| 75 | `relative_strength_60_x_risk_off` | 17.1 | Momentum × Régime | Force relative 60j × risk-off. |
| 76 | `sma100_distance_zscore` | 17.0 | Tendance | Z-score distance au SMA(100). |
| 77 | `rsi_5_zscore` | 16.9 | RSI | Z-score du RSI(5). |
| 78 | `rsi_14_x_bull` | 16.7 | RSI × Régime | RSI(14) × bull market. |
| 79 | `rsi_5_xs_rank` | 16.6 | RSI | RSI(5), rang cross-sectionnel. |
| 80 | `sma100_distance` | 16.5 | Tendance | (Close − SMA(100)) / SMA(100). |
| 81 | `sma20_distance_sector_neutral` | 16.0 | Sector Neutral | Distance au SMA(20) − médiane du secteur. |
| 82 | `rsi_14_xs_rank` | 15.9 | RSI | RSI(14), rang cross-sectionnel. |
| 83 | `rsi_14_x_risk_off` | 15.8 | RSI × Régime | RSI(14) × risk-off. |
| 84 | `rolling_volatility_20_xs_rank` | 15.7 | Volatilité | Volatilité 20j, rang cross-sectionnel. |
| 85 | `vol_expansion_xs_rank` | 15.6 | Volatilité | Expansion de volatilité, rang cross-sectionnel. |
| 86 | `momentum_5` | 14.9 | Momentum | Rendement cumulé sur 5j (1 semaine). |
| 87 | `dist_to_sma_5d_xs_rank` | 14.6 | Tendance | Distance au SMA(5j), rang cross-sectionnel. |
| 88 | `range_position_20_rank` | 14.6 | Prix | Position du prix dans le range 20j (0=bas, 1=haut). |
| 89 | `sma20_distance` | 14.6 | Tendance | (Close − SMA(20)) / SMA(20). |
| 90 | `rsi_3_xs_rank` | 14.6 | RSI | RSI(3), rang cross-sectionnel. Signal très court terme. |
| 91 | `momentum_60_x_risk_off` | 14.5 | Momentum × Régime | Momentum 60j × risk-off. |
| 92 | `intraday_range_xs_rank` | 14.5 | Prix | Range intraday (High−Low)/Close, rang cross-sectionnel. |
| 93 | `sma20_distance_xs_rank` | 14.4 | Tendance | Distance au SMA(20), rang cross-sectionnel. |
| 94 | `intraday_range_div_atr_14` | 14.3 | Prix/Volatilité | Range intraday / ATR(14). Range du jour vs range normal. |
| 95 | `rsi_21_xs_rank` | 14.2 | RSI | RSI(21), rang cross-sectionnel. |
| 96 | `rolling_volatility_5_xs_rank` | 14.2 | Volatilité | Volatilité 5j, rang cross-sectionnel. |
| 97 | `momentum_20_x_risk_off` | 13.9 | Momentum × Régime | Momentum 20j × risk-off. |
| 98 | `decay_5_10` | 13.9 | Dynamique | Taux de décroissance du momentum entre 5j et 10j. |
| 99 | `rsi_5` | 13.6 | RSI | RSI(5) — indicateur de sur-achat/sur-vente très réactif. |
| 100 | `ema20_distance` | 13.6 | Tendance | (Close − EMA(20)) / EMA(20). Distance à la tendance exponentielle. |
| 101 | `relative_strength_20` | 13.5 | Momentum | Force relative 20j = rendement titre / rendement SPY. |
| 102 | `sma20_distance_zscore` | 13.4 | Tendance | Z-score distance au SMA(20). |
| 103 | `rolling_mean_return_5` | 13.3 | Rendement | Rendement moyen quotidien sur 5j. |
| 104 | `vol_ratio_20_60_x_risk_off` | 13.3 | Volatilité × Régime | Ratio vol(20/60) × risk-off. |
| 105 | `rsi_3` | 13.2 | RSI | RSI(3) — indicateur de sur-achat/sur-vente ultra-réactif. |
| 106 | `rsi_14_zscore` | 12.8 | RSI | Z-score du RSI(14). |
| 107 | `momentum_20_zscore` | 12.5 | Momentum | Z-score du momentum 20j. |
| 108 | `rsi_21` | 12.4 | RSI | RSI(21) — RSI sur 1 mois de trading. |
| 109 | `momentum_20_x_bull` | 12.1 | Momentum × Régime | Momentum 20j × bull market. |
| 110 | `ret_60_rank` | 12.1 | Rendement | Rang cross-sectionnel du rendement 60j. |
| 111 | `momentum_60_xs_rank` | 12.0 | Momentum | Momentum 60j, rang cross-sectionnel. |
| 112 | `ema20_distance_xs_rank` | 12.0 | Tendance | Distance au EMA(20), rang cross-sectionnel. |
| 113 | `rolling_mean_return_20_xs_rank` | 12.0 | Rendement | Rendement moyen 20j, rang cross-sectionnel. |
| 114 | `rolling_volatility_20_x_risk_off` | 11.8 | Volatilité × Régime | Volatilité 20j × risk-off. |
| 115 | `range_position_20_xs_rank` | 11.7 | Prix | Position dans le range 20j, rang cross-sectionnel. |
| 116 | `gap_fade` | 11.6 | Prix | Signal de comblement de gap. Gap overnight suivi d'un retour. |
| 117 | `momentum_20_div_vol_20` | 11.6 | Momentum/Risque | Momentum 20j / vol 20j. Ratio rendement/risque court terme. |
| 118 | `meanrev_signal_xs_rank` | 11.6 | Mean Reversion | Signal mean reversion, rang cross-sectionnel. |
| 119 | `momentum_10_zscore` | 11.6 | Momentum | Z-score du momentum 10j. |
| 120 | `ema50_distance` | 11.1 | Tendance | (Close − EMA(50)) / EMA(50). |
| 121 | `relative_strength_20_x_bull` | 10.7 | Momentum × Régime | Force relative 20j × bull market. |
| 122 | `intraday_range_zscore` | 10.6 | Prix | Z-score du range intraday. |
| 123 | `rsi_14_times_volume_ratio_20` | 10.5 | RSI/Volume | RSI(14) × ratio volume 20j. RSI pondéré par le volume. |
| 124 | `volume_ratio_20_zscore` | 10.2 | Volume | Z-score du ratio de volume 20j. |
| 125 | `momentum_3_xs_rank` | 10.1 | Momentum | Momentum 3j, rang cross-sectionnel. |
| 126 | `range_position_20_times_vol_ratio_20_60` | 9.8 | Prix/Volatilité | Position range × ratio de volatilité. Interaction prix/volatilité. |
| 127 | `close_to_vwap` | 9.7 | Prix | (Close − VWAP) / VWAP. Distance au prix moyen pondéré. |
| 128 | `ret_20_rank` | 9.7 | Rendement | Rang cross-sectionnel du rendement 20j. |
| 129 | `log_return_div_intraday_range` | 9.6 | Prix | Log-rendement / range intraday. Rendement ajusté au range. |
| 130 | `gap_fade_xs_rank` | 8.9 | Prix | Signal gap fade, rang cross-sectionnel. |
| 131 | `sma50_distance_x_risk_off` | 8.9 | Tendance × Régime | Distance au SMA(50) × risk-off. |
| 132 | `overnight_gap_xs_rank` | 8.7 | Prix | Gap overnight, rang cross-sectionnel. |
| 133 | `volume_ratio_20` | 8.6 | Volume | Volume 20j / Volume 60j. Expansion de volume. |
| 134 | `relative_strength_60_x_bull` | 8.5 | Momentum × Régime | Force relative 60j × bull market. |
| 135 | `volume_zscore_5d` | 8.5 | Volume | Z-score du volume sur 5j. Volume anormal récent ? |
| 136 | `close_to_vwap_xs_rank` | 8.5 | Prix | Distance au VWAP, rang cross-sectionnel. |
| 137 | `accel_3_5` | 8.0 | Dynamique | Accélération : momentum(3j) − momentum(5j). |
| 138 | `accel_3_5_xs_rank` | 7.9 | Dynamique | Accélération 3→5j, rang cross-sectionnel. |
| 139 | `daily_return_xs_rank` | 7.8 | Rendement | Rendement quotidien, rang cross-sectionnel. |
| 140 | `volume_ratio_20_sector_neutral` | 7.3 | Sector Neutral | Ratio volume 20j − médiane du secteur. |
| 141 | `volume_zscore_5d_xs_rank` | 7.1 | Volume | Z-score volume 5j, rang cross-sectionnel. |
| 142 | `volume_ratio_20_rank_xs` | 6.9 | Volume | Rang cross-sectionnel du volume ratio 20j. |
| 143 | `rsi_14` | 6.5 | RSI | RSI(14) classique — sur-achat (>70) / sur-vente (<30). |
| 144 | `intraday_range` | 6.4 | Prix | (High − Low) / Close. Range intraday normalisé. |
| 145 | `relative_strength_60_sector_neutral` | 6.1 | Sector Neutral | Force relative 60j − médiane du secteur. |
| 146 | `momentum_20` | 5.5 | Momentum | Rendement cumulé sur 20j (~1 mois). |
| 147 | `daily_return` | 5.3 | Rendement | Rendement du jour : (Close − Close_prev) / Close_prev. |
| 148 | `range_position_20` | 5.1 | Prix | (Close − Low_20j) / (High_20j − Low_20j). Position dans le range. |
| 149 | `momentum_20_xs_rank` | 5.0 | Momentum | Momentum 20j, rang cross-sectionnel. |
| 150 | `rolling_mean_return_20` | 4.7 | Rendement | Rendement moyen quotidien sur 20j. |
| 151 | `volume_ratio_20_xs_rank` | 4.7 | Volume | Volume ratio 20j, rang cross-sectionnel. |
| 152 | `daily_return_times_volume_ratio_20` | 4.3 | Rendement/Volume | Rendement jour × ratio volume. Signal prix+volume combiné. |
| 153 | `relative_strength_60_xs_rank` | 3.0 | Momentum | Force relative 60j, rang cross-sectionnel. |
| 154 | `relative_strength_20_sector_neutral` | 2.5 | Sector Neutral | Force relative 20j − médiane du secteur. |
| 155 | `selector_short_score` | 2.4 | Screener | Score baissier du screener (trend+RSI+SMA). Signal short. |
| 156 | `log_return` | 2.0 | Rendement | Log-rendement quotidien : ln(Close / Close_prev). |
| 157 | `log_return_xs_rank` | 1.9 | Rendement | Log-rendement, rang cross-sectionnel. |
| 158 | `relative_strength_60_rank` | 1.9 | Momentum | Rang cross-sectionnel force relative 60j (version courte). |
| 159 | `relative_strength_20_xs_rank` | 1.3 | Momentum | Force relative 20j, rang cross-sectionnel. |
| 160 | `relative_strength_20_rank` | 0.7 | Momentum | Rang cross-sectionnel force relative 20j (version courte). |

---

## Distribution par catégorie

| Catégorie | Nombre | Importance cumulée H3 |
|-----------|:-----:|--:|
| Tendance (SMA/EMA distance, croix) | 28 | ~550 |
| Momentum (rendements, force relative) | 34 | ~620 |
| Volatilité (rolling, ATR, zscore) | 20 | ~500 |
| RSI | 15 | ~200 |
| Volume | 12 | ~80 |
| Prix (gap, range, VWAP) | 12 | ~110 |
| Sector Neutral | 8 | ~115 |
| Dynamique (accélération, decay) | 4 | ~50 |
| Mean Reversion | 4 | ~55 |
| Rendement (daily, log, mean) | 8 | ~50 |
| Facteur (vs market) | 1 | ~65 |
| Screener | 1 | ~2 |

---

## Features blacklistées (exclues du modèle)

| Feature | Raison |
|---------|--------|
| `vix_close`, `vxn_close`, `vix3m_close`, `move_close` | Macro — identique ∀ symboles |
| `SPY_SMA_200_slope`, `VIX_zscore` | Régime macro — identique ∀ symboles |
| `market_return_20`, `market_volatility_20`, `market_trend_strength_50` | Marché — identique ∀ symboles |
| `regime_bull_market`, `regime_risk_off` | Régime binaire — identique ∀ symboles |
| `dollar_volume_20_rank` | Trop dominant, écrase l'alpha |
| `rolling_volatility_120*` (×3) | Béquille H10, empêche apprentissage momentum |
| `rolling_volatility_20_sector_neutral` | Dominance H5 excessive (imp 48.5) |
| `rolling_volatility_60_sector_neutral` | Dominance H5 excessive (imp 58.7) |
| `beta_252`, `alpha_252`, `r_squared_252` | CAPM — importance 0.0 |
| `sector_ret_20/60`, `sector_vol_20`, `sector_relative_strength_20` | Redondant avec cross-sectional + sector_neutral |
| `sector_dollar_volume_20`, `sector_symbol_count` | Redondant |
| `stock_vs_sector_ret_20/60` | Redondant |
| `is_filled` | Métadonnées |

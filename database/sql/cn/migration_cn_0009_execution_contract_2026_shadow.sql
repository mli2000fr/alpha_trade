-- Sprint 18-C : contrat CN_A 2026 pour recherche shadow uniquement.
-- Exécuter exclusivement sur alpha_trade_cn, après migration_cn_0008.
-- Ne crée aucun accès broker, ne change pas markets.live_enabled.
-- Règles bornées à la révision du 2026-07-06, aucun backfill du S1 2026.

INSERT INTO market_execution_rules
    (market_code,exchange_mic,board_code,valid_from,valid_to,currency,
     settlement_cycle_days,buy_lot_size,sell_lot_size,tick_size,
     daily_price_limit_pct,short_selling_allowed,same_day_sell_allowed,metadata_json)
VALUES
    ('CN_A','XSHG','SH_MAIN','2026-07-06','2026-12-31','CNY',1,100,1,0.01,NULL,FALSE,FALSE,
     JSON_OBJECT('minimum_buy_shares',100,'minimum_sell_shares',100,'research_only',TRUE,
       'rule_version','cn_a_2026_07_shadow_v1','source_type','OFFICIAL_RULES_RESEARCH_EXECUTION',
       'source_ref','https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml',
       'limits','instrument_session_only','not_broker_verified',TRUE)),
    ('CN_A','XSHE','SZ_MAIN','2026-07-06','2026-12-31','CNY',1,100,1,0.01,NULL,FALSE,FALSE,
     JSON_OBJECT('minimum_buy_shares',100,'minimum_sell_shares',100,'research_only',TRUE,
       'rule_version','cn_a_2026_07_shadow_v1','source_type','OFFICIAL_RULES_RESEARCH_EXECUTION',
       'source_ref','https://investor.szse.cn/lawrules/rule/trade/t20260424_620190.html',
       'limits','instrument_session_only','not_broker_verified',TRUE)),
    ('CN_A','XSHE','CHINEXT','2026-07-06','2026-12-31','CNY',1,100,1,0.01,NULL,FALSE,FALSE,
     JSON_OBJECT('minimum_buy_shares',100,'minimum_sell_shares',100,'research_only',TRUE,
       'rule_version','cn_a_2026_07_shadow_v1','source_type','OFFICIAL_RULES_RESEARCH_EXECUTION',
       'source_ref','https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf',
       'limits','instrument_session_only','not_broker_verified',TRUE)),
    ('CN_A','XSHG','STAR','2026-07-06','2026-12-31','CNY',1,1,1,0.01,NULL,FALSE,FALSE,
     JSON_OBJECT('minimum_buy_shares',200,'minimum_sell_shares',200,'research_only',TRUE,
       'rule_version','cn_a_2026_07_shadow_v1','source_type','OFFICIAL_RULES_RESEARCH_EXECUTION',
       'source_ref','https://english.sse.com.cn/start/trading/mechanism/',
       'limits','instrument_session_only','not_broker_verified',TRUE))
ON DUPLICATE KEY UPDATE rule_id = rule_id;

-- Commission/minimum/slippage : scénarios de recherche, PAS frais du courtier.
-- 10 bps et 5 CNY prolongent l'hypothèse économique 11-B, mais dans un
-- nouveau profil borné et contrôlé. 0.1 bps de transfert et 5 bps de taxe
-- vendeur s'appuient sur les barèmes publics. Pas de frais de place ajoutés
-- séparément car ils peuvent déjà être inclus dans la commission du courtier.
INSERT INTO cn_execution_cost_profiles
    (market_code,profile_key,valid_from,valid_to,currency,source_type,
     commission_bps_buy,commission_bps_sell,commission_min_cny,
     transfer_fee_bps_buy,transfer_fee_bps_sell,stamp_duty_bps_sell,
     slippage_bps_buy,slippage_bps_sell,source_ref,metadata_json)
VALUES
    ('CN_A','cn_a_research','2026-07-06','2026-12-31','CNY','RESEARCH_PROXY',
     10,10,5,0.1,0.1,5,2,2,
     'Sprint 18-C proxy 2026: commission 10bps/min 5 CNY + slippage 2bps par cote; taxes publiques explicites',
     JSON_OBJECT('version','cn_a_research_2026_shadow_v1',
       'not_verified_broker',TRUE,'commission_assumption','Sprint 11-B 10bps/min5',
       'slippage_assumption_bps_per_side',2,
       'public_fees_ref','https://one.sse.com.cn/onething/gptz/',
       'szse_fees_ref','https://investor.szse.cn/marketServices/deal/payFees/index.html',
       'exchange_handling_in_commission_not_added_twice',TRUE))
ON DUPLICATE KEY UPDATE profile_id = profile_id;

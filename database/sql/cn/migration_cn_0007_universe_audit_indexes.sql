-- Sprint 8 : recherche rapide des rares anomalies historiques avant jointure aux snapshots.
CREATE INDEX ix_cn_daily_status_date ON stock_bars_daily(trading_status, `date`);
CREATE INDEX ix_cn_limits_policy_date ON cn_daily_price_limits(policy_code, session_date);

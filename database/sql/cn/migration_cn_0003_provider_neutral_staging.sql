-- Sprint 6 CN : le staging devient multi-fournisseurs.
-- À exécuter exclusivement sur alpha_trade_cn si Alembic ne peut pas être utilisé.
RENAME TABLE tushare_raw_payloads TO cn_raw_payloads;
RENAME TABLE tushare_staging_rows TO cn_staging_rows;

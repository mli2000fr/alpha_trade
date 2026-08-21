# -*- coding: utf-8 -*-
"""Vérification ponctuelle de la table stock_earnings_calendar après backfill SEC EDGAR."""
from sqlalchemy import create_engine, text

ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)


def q(sql: str):
    with ENGINE.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql))]


print("== volume ==")
print(q(
    "SELECT COUNT(*) AS lignes, COUNT(DISTINCT symbol) AS symboles, "
    "MIN(earnings_date) AS min_date, MAX(earnings_date) AS max_date "
    "FROM stock_earnings_calendar"
))
print("== nulls ==")
print(q(
    "SELECT SUM(eps_actual IS NULL) AS eps_act_null, "
    "SUM(revenue_actual IS NULL) AS rev_act_null, "
    "SUM(eps_estimate IS NULL) AS eps_est_null "
    "FROM stock_earnings_calendar"
))
print("== par annee de depot ==")
print(q(
    "SELECT YEAR(earnings_date) AS annee, COUNT(*) AS n "
    "FROM stock_earnings_calendar GROUP BY YEAR(earnings_date) ORDER BY 1"
))
print("== par annee fiscale ==")
print(q(
    "SELECT LEFT(fiscal_period, 4) AS fy, COUNT(*) AS n "
    "FROM stock_earnings_calendar GROUP BY LEFT(fiscal_period, 4) ORDER BY 1"
))
print("== symboles hors univers 400 ? ==")
print(q(
    "SELECT COUNT(*) FROM stock_earnings_calendar e "
    "LEFT JOIN stock_metadata m ON m.symbol = e.symbol WHERE m.symbol IS NULL"
))
print("== echantillon ==")
print(q(
    "SELECT symbol, earnings_date, eps_estimate, eps_actual, revenue_estimate, "
    "revenue_actual, fiscal_period FROM stock_earnings_calendar "
    "ORDER BY symbol, earnings_date LIMIT 8"
))
print("== top symbols par nombre de lignes ==")
print(q(
    "SELECT symbol, COUNT(*) AS n FROM stock_earnings_calendar "
    "GROUP BY symbol ORDER BY n DESC LIMIT 5"
))
print("== lignes avec fiscal_period FY (10-K) ==")
print(q(
    "SELECT COUNT(*) FROM stock_earnings_calendar WHERE fiscal_period LIKE '%FY'"
))

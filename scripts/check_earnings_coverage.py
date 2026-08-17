# -*- coding: utf-8 -*-
"""Couverture du backfill SEC sur l'univers 400 uniquement + vérifs valeurs."""
import re

from sqlalchemy import create_engine, text

ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)


def q(sql: str):
    with ENGINE.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql))]


raw = open("config/ticket_mid_cap_400.txt", encoding="utf-8").read()
UNIVERSE = [s.strip().upper() for s in re.split(r"[,\s]+", raw) if s.strip()]

print("== univers 400 : lignes SEC (fiscal_period 20xx) par symbole ==")
rows = dict(q(
    "SELECT symbol, COUNT(*) FROM stock_earnings_calendar "
    "WHERE fiscal_period LIKE '20%' GROUP BY symbol"
))
covered = {s: rows.get(s, 0) for s in UNIVERSE}
zero = [s for s, n in covered.items() if n == 0]
low = {s: n for s, n in covered.items() if 0 < n < 15}
print("symboles couverts:", sum(1 for n in covered.values() if n > 0), "/", len(UNIVERSE))
print("sans AUCUNE ligne SEC:", len(zero), zero)
counts = sorted(covered.values())
print(f"lignes/symbole (univers) : min={counts[0]} p10={counts[39]} med={counts[199]} p90={counts[359]} max={counts[-1]}")
print("symb. 1-14 lignes:", len(low), dict(list(low.items())[:25]))

print("\n== verif correction YTD (AA 2025Q3) ==")
print(q(
    "SELECT symbol, earnings_date, eps_estimate, eps_actual, revenue_estimate, revenue_actual, fiscal_period "
    "FROM stock_earnings_calendar WHERE symbol='AA' AND fiscal_period='2025Q3'"
))
print("== verif AAPL 2016 ==")
print(q(
    "SELECT earnings_date, eps_actual, revenue_actual, fiscal_period "
    "FROM stock_earnings_calendar WHERE symbol='AAPL' AND fiscal_period IN ('2016Q1','2016Q2','2016Q3','2016FY') ORDER BY 1"
))
print("== exemple symbole FPI (20-F, pas de 10-Q) ==")
for sym in ["LKNCY", "BZ", "YUMC"]:
    print(sym, q(
        "SELECT fiscal_period, earnings_date FROM stock_earnings_calendar "
        f"WHERE symbol='{sym}' AND fiscal_period LIKE '20%' ORDER BY 1 LIMIT 6"
    ))

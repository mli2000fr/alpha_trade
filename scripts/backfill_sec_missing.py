# -*- coding: utf-8 -*-
"""Backfill ciblé SEC : re-fetch des symboles univers absents ou < 15 lignes, upsert direct.

Usage : .venv\Scripts\python.exe scripts\backfill_sec_missing.py
"""
import re
from datetime import date

from sqlalchemy import create_engine, text

from dataIntegrityEngine.sync_earnings_calendar import _fetch_sec_earnings
from database.selector_reference import upsert_earnings_calendar

ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
FROM = date(2015, 1, 1)
TO = date(2026, 8, 14)

raw = open("config/ticket_mid_cap_400.txt", encoding="utf-8").read()
UNIVERSE = [s.strip().upper() for s in re.split(r"[,\s]+", raw) if s.strip()]

with ENGINE.connect() as conn:
    db_rows = {
        str(r[0]): int(r[1])
        for r in conn.execute(text(
            "SELECT symbol, COUNT(*) FROM stock_earnings_calendar WHERE fiscal_period LIKE '20%' GROUP BY symbol"
        ))
    }

targets = [s for s in UNIVERSE if db_rows.get(s, 0) < 15]
print(f"symboles a retraiter: {len(targets)}")
print(", ".join(targets))

total_rows = 0
ok, ko = [], []
for sym in targets:
    try:
        rows = _fetch_sec_earnings(sym, from_date=FROM, to_date=TO)
        if rows:
            n = upsert_earnings_calendar(rows)
            total_rows += n
            print(f"  {sym}: {len(rows)} extraites, upsert {n}")
            ok.append(sym)
        else:
            print(f"  {sym}: 0 ligne extraite")
            ko.append(sym)
    except Exception as exc:  # noqa: BLE001
        print(f"  {sym}: ERREUR {type(exc).__name__}: {exc}")
        ko.append(sym)

print(f"\nRESUME: {len(ok)} ok / {len(ko)} sans donnee ou erreur / {total_rows} lignes upsertées")
print("KO:", ", ".join(ko))

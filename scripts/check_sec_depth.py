# -*- coding: utf-8 -*-
"""Preuve : companyfacts contient l'historique complet (2010+) et le provider SEC extrait bien 2019-2025."""
from datetime import date

from service.sec.clientEdgar import ticker_to_cik, fetch_company_facts
from dataIntegrityEngine.sync_earnings_calendar import (
    _EPS_TAGS,
    _fetch_sec_earnings,
    _pick_quarterly_facts,
)

print("== 1. Profondeur historique brute du companyfacts (AAPL, EPS Diluted) ==")
d = fetch_company_facts(ticker_to_cik("AAPL"))
m = _pick_quarterly_facts((d.get("facts") or {}).get("us-gaap") or {}, _EPS_TAGS)
keys = sorted(m)
print("plus ancien (fy,fp):", keys[0], "| plus recent:", keys[-1], "| nb trimestres:", len(keys))

print("\n== 2. Extraction 2019-2025 via _fetch_sec_earnings ==")
for sym in ["AAPL", "SMCI", "CLF"]:
    try:
        rows = _fetch_sec_earnings(sym, from_date=date(2019, 1, 1), to_date=date(2025, 12, 31))
        yrs = sorted({r["earnings_date"][:4] for r in rows})
        print(f"{sym}: {len(rows)} lignes, annees={yrs}")
    except Exception as exc:  # noqa: BLE001
        print(f"{sym}: ERREUR {type(exc).__name__}: {exc}")

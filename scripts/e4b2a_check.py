"""E4-B2A — vérif couverture du cache FINRA vs dataset O1."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
CACHE = Path("artifacts/finra_short_volume/short_sale_volume_400.parquet")
TICKET = Path("config/ticket_recherche.txt")


def main() -> None:
    ds = pd.read_parquet(DATA, columns=["date", "symbol"])
    print("O1 dates min/max:", ds["date"].min(), "->", ds["date"].max())
    ds22 = ds[ds["date"] >= "2022-01-01"]
    print("O1 nb dates uniques >=2022:", ds22["date"].nunique())

    sv = pd.read_parquet(CACHE)
    sv["symbol"] = sv["symbol"].astype(str)
    print("FINRA sym:", sv["symbol"].nunique(), "| dates:", sv["date"].min(), "->", sv["date"].max())

    ticket = {s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()}
    missing = sorted(ticket - set(sv["symbol"].unique()))
    print("symboles 400 absents du cache FINRA:", missing)

    # couverture par année (dates FINRA vs dates O1)
    o1_dates = set(pd.to_datetime(ds22["date"]).dt.normalize())
    sv_dates = set(pd.to_datetime(sv["date"]).dt.normalize())
    manquantes = sorted(d for d in o1_dates if d not in sv_dates)
    print(f"dates O1 absentes du cache FINRA : {len(manquantes)}")
    if manquantes:
        print("  premiere:", manquantes[:5], "| derniere:", manquantes[-5:])
    # par année
    sv["year"] = pd.to_datetime(sv["date"]).dt.year
    print(sv.groupby("year").size())


if __name__ == "__main__":
    main()

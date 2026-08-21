"""Génère la liste des fichiers FINRA manquants (66 dates 2026) avec URLs + script d'ingestion."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
CACHE = Path("artifacts/finra_short_volume/short_sale_volume_400.parquet")
OUT_TXT = Path("artifacts/finra_short_volume/missing_2026_list.txt")
DL_DIR = Path("artifacts/finra_short_volume/manual_dl")


def main() -> None:
    ds = pd.read_parquet(DATA, columns=["date"])
    o1_dates = set(pd.to_datetime(ds["date"]).dt.normalize().dt.date)
    sv = pd.read_parquet(CACHE, columns=["date"])
    sv_dates = set(pd.to_datetime(sv["date"]).dt.normalize().dt.date)
    missing = sorted(d for d in o1_dates if d.year >= 2022 and d not in sv_dates)
    print(f"fichiers manquants : {len(missing)}")

    DL_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for d in missing:
        ymd = d.strftime("%Y%m%d")
        url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{ymd}.txt"
        lines.append(f"{ymd} {url}")
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"liste ecrite : {OUT_TXT} ({len(lines)} urls)")
    print("exemples:")
    for ln in lines[:5]:
        print("  ", ln)
    print("  ...")
    for ln in lines[-3:]:
        print("  ", ln)


if __name__ == "__main__":
    main()

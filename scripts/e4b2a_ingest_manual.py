"""Ingère les données FINRA téléchargées manuellement dans le parquet cache.

Sources acceptées :
  1. un fichier concaténé : c:/Users/PC ming/Downloads/2.txt (66 dates, format API float)
  2. des fichiers CNMSshvol*.txt dans artifacts/finra_short_volume/manual_dl/

Format (les deux) : Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
Volumes = int (CDN) ou float (API) — acceptés.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

TICKET = Path("config/ticket_recherche.txt")
DL_DIR = Path("artifacts/finra_short_volume/manual_dl")
MANUAL_FILE = Path("c:/Users/PC ming/Downloads/2.txt")
OUT = Path("artifacts/finra_short_volume/short_sale_volume_400.parquet")
_COLS = ["date", "symbol", "short_volume", "short_exempt_volume", "total_volume"]


def parse_text(text: str, ticket: set[str]) -> list[dict]:
    rows = []
    for ln in text.splitlines():
        parts = ln.split("|")
        if len(parts) < 5:
            continue
        date_part = parts[0].strip()
        if len(date_part) != 8 or not date_part.isdigit():
            continue  # pas une ligne data (header ou autre)
        sym = parts[1].strip().upper()
        if sym not in ticket:
            continue
        try:
            rows.append({"date": date_part, "symbol": sym,
                         "short_volume": float(parts[2]),
                         "short_exempt_volume": float(parts[3]),
                         "total_volume": float(parts[4])})
        except ValueError:
            continue
    return rows


def main() -> None:
    ticket = {s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()}
    print(f"univers 400 : {len(ticket)} symboles")
    sources: list[tuple[str, str]] = []  # (nom, texte)

    if MANUAL_FILE.exists():
        sources.append((MANUAL_FILE.name, MANUAL_FILE.read_text(encoding="utf-8", errors="replace")))
    for f in sorted(DL_DIR.glob("CNMSshvol*.txt")):
        sources.append((f.name, f.read_text(encoding="utf-8", errors="replace")))

    if not sources:
        print("aucune source — mets le fichier dans Downloads ou manual_dl")
        return

    new_rows = []
    for name, text in sources:
        rows = parse_text(text, ticket)
        print(f"  {name} : {len(rows):,} lignes ticket")
        new_rows.extend(rows)
    if not new_rows:
        print("aucune ligne extraite")
        return
    def _norm_dates(s: pd.Series) -> pd.Series:
        """Normalise une série de dates en YYYY-MM-DD (formats mixtes YYYYMMDD / YYYY-MM-DD)."""
        out = s.astype(str)
        yyyymmdd = out.str.match(r"^\d{8}$")
        iso = out.str.match(r"^\d{4}-\d{2}-\d{2}$")
        out = out.where(iso, out.where(yyyymmdd, out))
        out[iso] = pd.to_datetime(out[iso]).dt.strftime("%Y-%m-%d")
        out[yyyymmdd] = pd.to_datetime(out[yyyymmdd], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        return out

    new = pd.DataFrame(new_rows, columns=_COLS)
    new["date"] = _norm_dates(new["date"])
    old = pd.read_parquet(OUT)
    old["date"] = _norm_dates(old["date"])
    df = pd.concat([old, new], ignore_index=True)
    df = df.drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"]).reset_index(drop=True)
    df.to_parquet(OUT, index=False)
    print(f"cache : {len(df):,} lignes | {df['date'].min()} -> {df['date'].max()} | sym {df['symbol'].nunique():,}")
    # couverture restante vs O1
    ds = pd.read_parquet("artifacts/models/oracle/e2_feature_dataset.parquet", columns=["date"])
    o1 = set(pd.to_datetime(ds["date"]).dt.normalize().dt.strftime("%Y-%m-%d"))
    have = set(df["date"])
    missing = sorted(d for d in o1 if d >= "2022-01-01" and d not in have)
    print(f"dates O1 encore manquantes : {len(missing)} -> {missing[:8]}")


if __name__ == "__main__":
    main()

"""E4-B2A — downloader FINRA Daily Short Sale Volume (v4, dates de trading O1).

Stratégie :
  - Les dates cibles = dates de trading réelles du dataset O1 (univers 400),
    déjà débarrassées des fériés US. Source de vérité = parquet existant.
  - 404 = fichier absent inattendu (on logge). 403 persistant = rate-limit -> stop propre.
  - Reprise : re-télécharge seulement les dates de trading O1 absentes du parquet.
  - Pause longue entre lots pour éviter le rate-limit FINRA (~200 req / fenêtre).
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

TICKET = Path("config/ticket_recherche.txt")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
CACHE_DIR = Path("artifacts/finra_short_volume")
OUT = CACHE_DIR / "short_sale_volume_400.parquet"

URL_TMPL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{ymd}.txt"
HEADERS = {"User-Agent": "research-backtest/1.0 (contact: local)"}
SLEEP = 2.0
BATCH_PAUSE = 60.0   # pause entre lots de 100 requêtes
BATCH_SIZE = 100

_COLS = ["date", "symbol", "short_volume", "short_exempt_volume", "total_volume"]


def load_ticket_syms() -> set[str]:
    return {s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()}


def target_dates() -> list:
    """Dates de trading réelles du dataset O1 (>= 2022), triées."""
    ds = pd.read_parquet(DATA, columns=["date"])
    dates = pd.to_datetime(ds["date"]).dt.normalize().drop_duplicates().sort_values()
    return [d.date() for d in dates if d.year >= 2022]


def existing_dates() -> set:
    if not OUT.exists():
        return set()
    df = pd.read_parquet(OUT, columns=["date"])
    return set(pd.to_datetime(df["date"]).dt.normalize().dt.date)


def fetch_day(ymd: str, ticket: set[str], session: requests.Session):
    """Retourne (rows, 'ok') ; (None,'holiday') si 404 ; (None,'ratelimit') si 403 persistant."""
    url = URL_TMPL.format(ymd=ymd)
    for attempt in range(4):
        r = session.get(url, timeout=30)
        if r.status_code == 200:
            text = r.content.decode("utf-8", errors="replace")
            lines = text.splitlines()
            if not lines or not lines[0].startswith("Date"):
                return None, "ok"
            rows = []
            for ln in lines[1:]:
                parts = ln.split("|")
                if len(parts) < 5:
                    continue
                sym = parts[1].strip().upper()
                if sym not in ticket:
                    continue
                try:
                    rows.append({"date": parts[0].strip(), "symbol": sym,
                                 "short_volume": int(parts[2]),
                                 "short_exempt_volume": int(parts[3]),
                                 "total_volume": int(parts[4])})
                except ValueError:
                    continue
            return rows, "ok"
        if r.status_code == 404:
            return None, "holiday"
        # 403/5xx : backoff puis retry
        time.sleep(4.0 * (attempt + 1))
    return None, "ratelimit"


def main() -> None:
    ticket = load_ticket_syms()
    targets = target_dates()
    have = existing_dates()
    missing = [d for d in targets if d not in have]
    print(f"dates de trading O1 (>=2022) : {len(targets):,} | deja en parquet : {len(have):,} | restants : {len(missing):,}")

    session = requests.Session()
    session.headers.update(HEADERS)
    new_rows: list[dict] = []
    holidays = 0
    for i, d in enumerate(missing):
        ymd = d.strftime("%Y%m%d")
        rows, status = fetch_day(ymd, ticket, session)
        if status == "ratelimit":
            print(f"  rate-limit a {ymd} — pause longue puis abandon (reprise possible)")
            break
        if status == "holiday":
            holidays += 1
            print(f"  !! {ymd} 404 inattendu (férié ?) — skip")
        elif rows:
            new_rows.extend(rows)
        if (i + 1) % BATCH_SIZE == 0:
            print(f"  lot {i+1}/{len(missing)} : {ymd} | nouveaux {len(new_rows):,} | 404 {holidays}")
            time.sleep(BATCH_PAUSE)
        else:
            time.sleep(SLEEP)

    # consolider
    frames = []
    if OUT.exists():
        frames.append(pd.read_parquet(OUT))
    if new_rows:
        frames.append(pd.DataFrame(new_rows, columns=_COLS))
    if frames:
        df = pd.concat(frames, ignore_index=True).drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"]).reset_index(drop=True)
    else:
        df = pd.DataFrame(columns=_COLS)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"cache : {len(df):,} lignes | {df['date'].min()} -> {df['date'].max()} | sym {df['symbol'].nunique():,}")
    print(f"nouveaux ajoutes : {len(new_rows):,} | 404 : {holidays}")


if __name__ == "__main__":
    main()

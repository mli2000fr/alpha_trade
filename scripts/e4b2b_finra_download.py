"""E4-B2B — downloader FINRA Consolidated Short Interest (API OAuth2, univers 400).

Contrat API corrigé (documentation actuelle) :
  - OAuth2 client_credentials -> Bearer token (FINRA Identity Platform).
  - POST /data/group/OTCMarket/name/consolidatedShortInterest
  - payload : {"compareFilters":[{"fieldName":"settlementDate",
              "fieldValue":"YYYY-MM-DD","compareType":"EQUAL"}], "limit":5000, "offset":...}
  - Pagination par Record-Total / offset (Record-Max-Limit = 5000).

PIT : publication_date = settlement_date + 7 jours de trading du calendrier O1
(FINRA publie le 7e jour ouvré après la settlement date ; feature disponible
uniquement à partir de publication_date). settlement_date = date de MESURE.

Credentials : variables d'environnement FINRA_API_USER / FINRA_API_SERCET.
Aucun secret en dur, aucun secret affiché.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

TICKET = Path("config/ticket_recherche.txt")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
CACHE_DIR = Path("artifacts/finra_short_volume")
OUT = CACHE_DIR / "short_interest_400.parquet"
STATE = CACHE_DIR / "short_interest_state.json"

TOKEN_URL = "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token?grant_type=client_credentials"
DATA_URL = "https://api.finra.org/data/group/OTCMarket/name/consolidatedShortInterest"
PARTS_URL = "https://api.finra.org/partitions/group/OTCMarket/name/consolidatedShortInterest"

# fenêtre : pool Oracle O1 (dates >= 2022), borne haute = max date du pool
WIN_START = "2022-01-01"
WIN_END = "2026-05-29"

UA = "research-backtest/1.0 (contact: local)"
SLEEP = 0.8

_COLS = [
    "settlement_date", "publication_date", "symbol",
    "current_short_position", "previous_short_position",
    "average_daily_volume", "days_to_cover",
    "change_previous_number", "change_percent",
    "revision_flag", "stock_split_flag", "market_class_code",
]


def get_token() -> str:
    cid = os.environ.get("FINRA_API_USER", "")
    csec = os.environ.get("FINRA_API_SERCET", "") or os.environ.get("FINRA_API_SECRET", "")
    if not cid or not csec:
        raise RuntimeError("credentials manquantes: FINRA_API_USER / FINRA_API_SERCET")
    auth = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    r = requests.post(TOKEN_URL, headers={"Authorization": f"Basic {auth}"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"token HTTP {r.status_code}: {r.text[:200]}")
    tok = r.json().get("access_token")
    if not tok:
        raise RuntimeError("pas de access_token dans la reponse")
    return tok


def load_ticket() -> set[str]:
    return {s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()}


def settlement_dates(token: str) -> list[str]:
    r = requests.get(PARTS_URL, headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": UA}, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"partitions HTTP {r.status_code}: {r.text[:200]}")
    d = r.json()
    parts = [p["partitions"][0] for p in d["availablePartitions"]]
    out = [x for x in parts if WIN_START <= x <= WIN_END]
    # tri chronologique croissant pour le PIT / publication
    return sorted(out)


def o1_trading_dates() -> list:
    ds = pd.read_parquet(DATA, columns=["date"])
    dates = sorted(pd.to_datetime(ds["date"]).dt.normalize().drop_duplicates())
    return [d for d in dates if d.year >= 2022]


def publication_date(settlement, o1_dates: list, n_bus: int = 7) -> object:
    """7e jour de trading O1 >= settlement (FINRA: publication au 7e jour ouvré)."""
    s = pd.Timestamp(settlement)
    fwd = [d for d in o1_dates if d >= s]
    if len(fwd) <= n_bus:
        return pd.NaT
    return fwd[n_bus]


def fetch_all(token: str, settlement: str, session: requests.Session, hdr: dict) -> list[dict]:
    rows: list[dict] = []
    off = 0
    while True:
        payload = {
            "compareFilters": [{"fieldName": "settlementDate", "fieldValue": settlement, "compareType": "EQUAL"}],
            "limit": 5000, "offset": off,
        }
        for attempt in range(4):
            r = session.post(DATA_URL, headers=hdr, data=json.dumps(payload), timeout=60)
            if r.status_code == 200:
                break
            time.sleep(3.0 * (attempt + 1))
        else:
            raise RuntimeError(f"data HTTP {r.status_code} pour {settlement}: {r.text[:200]}")
        d = r.json()
        # controle: toutes les lignes doivent avoir la settlement demandee
        bad = [x for x in d if x.get("settlementDate") != settlement]
        if bad:
            raise RuntimeError(f"filtre non respecte pour {settlement}: {len(bad)} lignes hors date")
        rows.extend(d)
        total = int(r.headers.get("Record-Total", 0))
        off += len(d)
        if off >= total or not d:
            break
        time.sleep(SLEEP)
    return rows


def main() -> None:
    ticket = load_ticket()
    print(f"ticket: {len(ticket)} symboles")
    tok = get_token()
    dates = settlement_dates(tok)
    print(f"settlement dates dans fenetre: {len(dates)} | {dates[0]} -> {dates[-1]}")

    o1_dates = o1_trading_dates()
    print(f"jours de trading O1: {len(o1_dates)}")

    have = set()
    frames = []
    if OUT.exists():
        old = pd.read_parquet(OUT)
        frames.append(old)
        have = set(old["settlement_date"].astype(str).str[:10])
    missing = [d for d in dates if d not in have]
    print(f"deja en parquet: {len(have)} | restants: {len(missing)}")

    session = requests.Session()
    hdr = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
           "Accept": "application/json", "User-Agent": UA}
    new_rows: list[dict] = []
    for i, sd in enumerate(missing):
        try:
            raw = fetch_all(tok, sd, session, hdr)
        except RuntimeError as e:
            print(f"  !! {sd}: {e}")
            break
        # filtre 400 symboles
        keep = [x for x in raw if x.get("symbolCode", "").upper() in ticket]
        pub = publication_date(sd, o1_dates)
        for x in keep:
            new_rows.append({
                "settlement_date": sd,
                "publication_date": pub.date().isoformat() if pub is not pd.NaT else None,
                "symbol": x["symbolCode"].upper(),
                "current_short_position": x.get("currentShortPositionQuantity"),
                "previous_short_position": x.get("previousShortPositionQuantity"),
                "average_daily_volume": x.get("averageDailyVolumeQuantity"),
                "days_to_cover": x.get("daysToCoverQuantity"),
                "change_previous_number": x.get("changePreviousNumber"),
                "change_percent": x.get("changePercent"),
                "revision_flag": x.get("revisionFlag"),
                "stock_split_flag": x.get("stockSplitFlag"),
                "market_class_code": x.get("marketClassCode"),
            })
        if (i + 1) % 10 == 0 or i == len(missing) - 1:
            print(f"  {i+1}/{len(missing)}: {sd} | raw={len(raw)} keep={len(keep)} cumul={len(new_rows):,}")
        time.sleep(SLEEP)

    if new_rows:
        frames.append(pd.DataFrame(new_rows, columns=_COLS))
    if frames:
        df = pd.concat(frames, ignore_index=True).drop_duplicates(["settlement_date", "symbol"]).sort_values(["settlement_date", "symbol"]).reset_index(drop=True)
    else:
        df = pd.DataFrame(columns=_COLS)
    df.to_parquet(OUT, index=False)
    print(f"\nsaved: {OUT} | {len(df):,} lignes | {df['symbol'].nunique()} symboles")
    if len(df):
        print(f"  fenetre settlement: {df['settlement_date'].min()} -> {df['settlement_date'].max()}")
        pub = pd.to_datetime(df["publication_date"], errors="coerce")
        print(f"  fenetre publication: {pub.min()} -> {pub.max()} | non-null {pub.notna().sum():,}/{len(df):,}")


if __name__ == "__main__":
    main()

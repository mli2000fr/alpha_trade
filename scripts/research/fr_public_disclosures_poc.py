"""Read-only French disclosure event study; research artefacts only.

Uses the public DILA INFO-FINANCIERE metadata API and anonymous Yahoo chart
prices. This is a feasibility test, not a production data or trading feed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd


SYMBOLS = {
    "AF.PA": "FR0000031122", "FR.PA": "FR0013176526",
    "UBI.PA": "FR0000054470", "RXL.PA": "FR0010451203",
    "NEX.PA": "FR0000044448", "EDEN.PA": "FR0010908533",
    "TEP.PA": "FR0000051807", "ALO.PA": "FR0010220475",
    "RNO.PA": "FR0000131906", "WLN.PA": "FR0011981968",
    "ETL.PA": "FR0010221234", "ELIS.PA": "FR0012435121",
    "SOI.PA": "FR0013227113", "ELIOR.PA": "FR0011950732",
    "GNFT.PA": "FR0004163111", "DBV.PA": "FR0010417345",
    "RCO.PA": "FR0000130395", "S30.PA": "FR0013379484",
}

BASE = "https://www.info-financiere.gouv.fr/api/explore/v2.0/catalog/datasets/flux-amf-new-prod/exports/json"
HEADERS = {"User-Agent": "AlphaTrade-Research/1.0 (public-data-readonly)"}
POSITIVE = re.compile(
    r"(relev\w*|rehauss\w*|augment\w*) .{0,35}(objectif|prevision|perspective)|"
    r"(objectif|prevision|perspective).{0,35}(hausse|relev\w*|rehauss\w*)|"
    r"(resultat|benefice|chiffre d.affaires).{0,35}(en hausse|progresse|croissance)"
)
NEGATIVE = re.compile(
    r"(abaisse\w*|redui\w*|rev\w* a la baisse).{0,35}(objectif|prevision|perspective)|"
    r"(objectif|prevision|perspective).{0,35}(baisse|abaisse\w*|redui\w*)|"
    r"(profit warning|avertissement sur resultat|perte nette)|"
    r"(resultat|benefice|chiffre d.affaires).{0,35}(en baisse|recul|chute)"
)
FINANCIAL = re.compile(r"(resultat|chiffre d.affaires|prevision|objectif|perspective|guidance)")


def fetch_json(url: str, *, attempts: int = 3) -> object:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def normalize(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(ch for ch in raw if not unicodedata.combining(ch))


def safe_publication_date(record: dict) -> pd.Timestamp | None:
    fields = ("uin_dat_amf", "uin_dat_mar", "informationdeposee_inf_dat_emt")
    times = [pd.to_datetime(record.get(key), utc=True, errors="coerce") for key in fields]
    valid = [value for value in times if not pd.isna(value)]
    if not valid:
        return None
    # Latest official timestamp is conservative when feed ordering is unclear.
    return max(valid).tz_convert("Europe/Paris").normalize().tz_localize(None)


def load_disclosures() -> pd.DataFrame:
    rows = []
    for symbol, isin in SYMBOLS.items():
        where = (
            f"identificationsociete_iso_cd_isi = '{isin}' "
            "AND uin_dat_amf >= '2018-01-01' AND uin_dat_amf < '2026-01-01'"
        )
        url = BASE + "?" + urllib.parse.urlencode({"where": where})
        payload = fetch_json(url)
        if not isinstance(payload, list):
            raise ValueError(f"DILA export not a list for {symbol}")
        for item in payload:
            if not isinstance(item, dict):
                continue
            date = safe_publication_date(item)
            if date is None:
                continue
            title = str(item.get("informationdeposee_inf_tit_inf") or "")
            title_norm = normalize(title)
            pos, neg = bool(POSITIVE.search(title_norm)), bool(NEGATIVE.search(title_norm))
            rows.append({
                "symbol": symbol, "isin": isin, "published_date": date,
                "title": title,
                "subtype": str(item.get("sous_type_d_information") or ""),
                "url": str(item.get("url_de_recuperation") or ""),
                "financial_title": bool(FINANCIAL.search(title_norm)),
                "positive_title": pos and not neg,
                "negative_title": neg and not pos,
            })
        print(f"DILA {symbol}: {len(payload)} records", flush=True)
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No DILA disclosures")
    return frame.drop_duplicates(["symbol", "published_date", "title"])


def load_prices() -> pd.DataFrame:
    start = int(pd.Timestamp("2018-01-01", tz="UTC").timestamp())
    end = int(pd.Timestamp("2026-02-01", tz="UTC").timestamp())
    rows = []
    for symbol in SYMBOLS:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
            f"?period1={start}&period2={end}&interval=1d"
        )
        data = fetch_json(url)
        result = data["chart"]["result"][0]
        if result["meta"].get("currency") != "EUR":
            raise ValueError(f"Unexpected currency for {symbol}: {result['meta'].get('currency')}")
        times = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
        if len(adj) != len(times):
            raise ValueError(f"Missing adjusted closes for {symbol}")
        for index, stamp in enumerate(times):
            op, close, adjusted = quote["open"][index], quote["close"][index], adj[index]
            if not op or not close or not adjusted:
                continue
            date = pd.Timestamp(stamp, unit="s", tz="UTC").tz_convert("Europe/Paris").date()
            rows.append({
                "symbol": symbol, "date": pd.Timestamp(date),
                "adjusted_open": float(op) * float(adjusted) / float(close),
                "adjusted_close": float(adjusted),
            })
        print(f"PRICE {symbol}: {len(times)} bars", flush=True)
    frame = pd.DataFrame(rows).drop_duplicates(["symbol", "date"])
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def label_prices(prices: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    parts = []
    for _, group in prices.groupby("symbol", sort=False):
        group = group.copy().reset_index(drop=True)
        group["bar_index"] = np.arange(len(group))
        for horizon in horizons:
            # Entry is the first session strictly after the disclosure date.
            group[f"return_h{horizon}"] = (
                group["adjusted_close"].shift(-(horizon - 1)) / group["adjusted_open"] - 1
            )
            group.loc[group[f"return_h{horizon}"].abs() > 0.8, f"return_h{horizon}"] = np.nan
        parts.append(group)
    frame = pd.concat(parts, ignore_index=True)
    for horizon in horizons:
        col = f"return_h{horizon}"
        frame[f"panel_mean_h{horizon}"] = frame.groupby("date")[col].transform("mean")
        frame[f"panel_n_h{horizon}"] = frame.groupby("date")[col].transform("count")
        rank_asc = frame.groupby("date")[col].rank(method="first", ascending=True)
        rank_desc = frame.groupby("date")[col].rank(method="first", ascending=False)
        tail_n = np.ceil(frame[f"panel_n_h{horizon}"] * 0.1)
        frame[f"bottom_h{horizon}"] = rank_asc <= tail_n
        frame[f"top_h{horizon}"] = rank_desc <= tail_n
    return frame


def join_events(disclosures: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    events = disclosures.groupby(["symbol", "published_date"], as_index=False).agg(
        disclosure_count=("title", "size"),
        financial_title=("financial_title", "max"),
        positive_title=("positive_title", "max"),
        negative_title=("negative_title", "max"),
    )
    # Same-day contradictory titles do not get a directional label.
    both = events["positive_title"] & events["negative_title"]
    events.loc[both, ["positive_title", "negative_title"]] = False
    parts = []
    for symbol, group in events.groupby("symbol"):
        history = prices[prices.symbol == symbol].sort_values("date")
        if history.empty:
            continue
        left = group.sort_values("published_date")
        joined = pd.merge_asof(
            left, history, left_on="published_date", right_on="date",
            direction="forward", allow_exact_matches=False,
            suffixes=("", "_price"),
        )
        parts.append(joined)
    return pd.concat(parts, ignore_index=True).dropna(subset=["date"])


def thin(frame: pd.DataFrame, horizon: int = 20) -> pd.DataFrame:
    keep = []
    for _, group in frame.sort_values(["symbol", "bar_index"]).groupby("symbol"):
        last = -math.inf
        for row in group.itertuples():
            if row.bar_index >= last + horizon:
                keep.append(row.Index)
                last = row.bar_index
    return frame.loc[keep]


def summarize(events: pd.DataFrame, horizons: tuple[int, ...]) -> list[dict]:
    out = []
    masks = {
        "any_disclosure": pd.Series(True, index=events.index),
        "financial_title": events.financial_title,
        "positive_title": events.positive_title,
        "negative_title": events.negative_title,
    }
    for period, bounds in {"development": (2018, 2023), "holdout": (2024, 2025)}.items():
        for signal, mask in masks.items():
            pool = events[mask & events.date.dt.year.between(*bounds)]
            for horizon in horizons:
                col = f"return_h{horizon}"
                sample = pool[pool[col].notna() & (pool[f"panel_n_h{horizon}"] >= 12)]
                sample = thin(sample, horizon)
                if sample.empty:
                    continue
                out.append({
                    "period": period, "signal": signal, "horizon": horizon,
                    "n": int(len(sample)), "symbols": int(sample.symbol.nunique()),
                    "mean_excess_pct": round(100 * float((sample[col] - sample[f"panel_mean_h{horizon}"]).mean()), 3),
                    "bottom_tail_pct": round(100 * float(sample[f"bottom_h{horizon}"].mean()), 2),
                    "top_tail_pct": round(100 * float(sample[f"top_h{horizon}"].mean()), 2),
                    "avg_panel_tail_pct": round(100 * float((np.ceil(sample[f"panel_n_h{horizon}"] * 0.1) / sample[f"panel_n_h{horizon}"]).mean()), 2),
                })
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.output_dir is None:
        stamp = pd.Timestamp.now(tz="UTC").strftime("poc-%Y%m%d-%H%M%S")
        args.output_dir = Path("artifacts/research/fr_public_disclosures") / stamp
    args.output_dir.mkdir(parents=True, exist_ok=True)
    disclosures = load_disclosures()
    prices = label_prices(load_prices(), (5, 20))
    events = join_events(disclosures, prices)
    summary = summarize(events, (5, 20))
    disclosures.to_parquet(args.output_dir / "disclosure_metadata.parquet", index=False)
    prices.to_parquet(args.output_dir / "price_labels.parquet", index=False)
    events.to_parquet(args.output_dir / "event_labels.parquet", index=False)
    report = {
        "scope": "18 hand-mapped French stocks, public DILA metadata and anonymous Yahoo prices",
        "pit_rule": "latest official transmission timestamp as conservative proxy; entry first Paris session strictly after its local date",
        "caveats": [
            "Yahoo is unofficial; no licence or corporate-action validation for production",
            "18 short-interest-heavy stocks are not a representative French tradable universe",
            "D1/D10 approximated as cross-sectional tails within 18-stock panel",
            "title lexicon is not manually validated against document body",
            "official transmission timestamp is not proof of actual public web availability",
            "identical DILA API queries returned inconsistent historical counts during this run; immutable source snapshot required",
            "overlapping events across different symbols remain; no trading costs",
        ],
        "disclosure_rows": int(len(disclosures)),
        "event_days": int(len(events)),
        "title_samples": {
            key: disclosures.loc[disclosures[key], "title"].drop_duplicates().head(12).tolist()
            for key in ("positive_title", "negative_title")
        },
        "summary": summary,
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {args.output_dir / 'report.json'}")
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()

"""Audit read-only des clôtures corrigées Euronext du 19 octobre 2020."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd

from service.fr.universe_liquidity_6b import _load_symbol_bars
from service.fr.yahoo_price_reference_pilot import normalize_chart

DAY = "2020-10-19"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_closes(path: Path) -> dict:
    """Lit uniquement la première feuille officielle actions, sans modifier le XLSX."""
    with zipfile.ZipFile(path) as archive:
        sheets = ET.fromstring(archive.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS)
        if not sheets or sheets[0].get("name") != "Equities_closing_prices_1910202":
            raise ValueError("Feuille officielle actions inattendue")
        strings = ["".join(item.itertext()) for item in
                   ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        rows = []
        for row in ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall(".//s:row", NS):
            values = {}
            for cell in row.findall("s:c", NS):
                value = cell.find("s:v", NS)
                text = value.text if value is not None else None
                if cell.get("t") == "s" and text is not None:
                    text = strings[int(text)]
                values[cell.get("r").rstrip("0123456789")] = text
            rows.append(values)
    expected = ["ISINCode", "MIC", "CURRENCY", "Symbol Index", "Last Adjusted Closing Price"]
    if [rows[0].get(c) for c in "ABCDE"] != expected:
        raise ValueError("En-têtes officiels inattendus")
    result = {}
    for row in rows[1:]:
        key = (row["A"], row["B"], row["C"])
        if key in result:
            raise ValueError(f"Clôture officielle dupliquée : {key}")
        result[key] = float(row["E"])
    return result


def verdict(official: float | None, eodhd: float, yahoo: float, tolerance: float = .0001) -> str:
    if official is None:
        return "OFFICIAL_MISSING"
    e, y = abs(official - eodhd) <= tolerance, abs(official - yahoo) <= tolerance
    return "BOTH_MATCH" if e and y else "EODHD_ONLY" if e else "YAHOO_ONLY" if y else "NEITHER_MATCH"


def run(workbook: Path, output: Path) -> dict:
    diagnostics = Path("artifacts/fr/research/fold3_repair/fr-fold3-repair-4ccc07603d2f/row_diagnostics.parquet")
    frame = pd.read_parquet(diagnostics)
    symbols = set()
    for row in frame.itertuples():
        for field in (row.feature_window_blockers, row.label_path_blockers):
            for blocker in field:
                if blocker["date"] == DAY and "INDEPENDENT_PRICE_CORROBORATION_MISSING" in blocker["reasons"]:
                    symbols.add(row.provider_symbol)
    if not symbols:
        raise ValueError("Aucun symbole litigieux : vérifier les diagnostics sources")
    identities_path = Path("artifacts/fr/sprint6c_reference/identities.jsonl.gz")
    with gzip.open(identities_path, "rt", encoding="utf-8") as stream:
        identities = {r["provider_symbol"]: r for r in map(json.loads, stream)}
    official = read_closes(workbook)
    results = []
    for symbol in sorted(symbols):
        identity = identities[symbol]
        mics = [ref["mic"] for ref in identity["market_reference"] if any(
            interval["from"] <= DAY and (interval["to"] is None or interval["to"] >= DAY)
            for interval in ref["observed_asof_intervals"])]
        isin = identity["isin"]
        mic = mics[0] if len(mics) == 1 else None
        key = hashlib.sha256(symbol.encode()).hexdigest()[:16]
        caches = list(Path("artifacts/fr/yahoo_daily_reference/cache").glob(f"{key}_2018-01-01_2026-10-01.json"))
        if len(caches) != 1:
            raise ValueError(f"Cache Yahoo absent/ambigu : {symbol}")
        cache = caches[0]
        yahoo, _ = normalize_chart(json.loads(cache.read_text(encoding="utf-8"))["payload"])
        bars = _load_symbol_bars(Path("artifacts/fr/eodhd/backfill_2016"), symbol)
        e, y = bars[DAY], yahoo[DAY]
        metadata_path = Path("artifacts/fr/eodhd/backfill_2016/symbols") / f"{key}.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        payload_path = Path("artifacts/fr/eodhd/backfill_2016") / metadata["payloads"]["eod"]["file"]
        close = official.get((isin, mic, "EUR"))
        results.append({"symbol": symbol, "isin": isin, "mic": mic, "date": DAY,
                        "official_close": close, "eodhd_close": e["close"], "yahoo_close": y["close"],
                        "verdict": verdict(close, e["close"], y["close"]) if mic else "MIC_AMBIGUOUS_OR_MISSING",
                        "other_price_differences": [f for f in ("open", "high", "low") if abs(e[f]-y[f]) > .0001],
                        "volume_difference": e["volume"] != y["volume"],
                        "eodhd_payload_sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
                        "yahoo_cache_sha256": hashlib.sha256(cache.read_bytes()).hexdigest()})
    report = {"date": DAY, "official_url": "https://live.euronext.com/media/516/download",
              "notice_url": "https://www.euronext.com/en/news/more-info-about-19-october-2020-market-status",
              "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
              "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "diagnostics_sha256": hashlib.sha256(diagnostics.read_bytes()).hexdigest(),
              "identities_sha256": hashlib.sha256(identities_path.read_bytes()).hexdigest(),
              "requested": len(symbols), "counts": dict(Counter(r["verdict"] for r in results)),
              "non_close_price_disagreements": sum(bool(r["other_price_differences"]) for r in results),
              "volume_disagreements": sum(r["volume_difference"] for r in results),
              "canonical_go": False, "results": results,
              "limitations": ["Official correction proves closing prices only, not OHLCV or tradability",
                              "No frozen data, model, database or admission mask modified",
                              "Other dates and missing ESMA evidence remain unresolved"]}
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(workbook, output / "official_closes_20201019.xlsx")
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.workbook, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, ensure_ascii=False))

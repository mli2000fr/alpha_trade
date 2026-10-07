"""Charge l'archive France dans un staging non tradable, reprenable par symbole.

Ne crée ni instrument_id, ni listing XPAR, ni barre canonique. La disponibilité
historique est l'heure d'observation du backfill, jamais reconstruite.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import create_engine, text

from common.market_calendar import get_market_calendar
from database.router import build_database_url
from service.fr.import_eodhd_archive import archive_rows

CLASSIFIER_VERSION = "fr_eod_v2"


def _decimal(value):
    try:
        parsed = Decimal(str(value))
        return parsed if parsed.is_finite() and parsed > 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def classify_bar(row: dict, sessions: set[date]) -> tuple[date, str, dict]:
    day = date.fromisoformat(str(row["date"]))
    opened, high, low, closed = (_decimal(row.get(key)) for key in
                                 ("open", "high", "low", "close"))
    volume = row.get("volume")
    try:
        volume = int(volume) if volume is not None and str(volume).strip() == str(int(volume)) else None
    except (TypeError, ValueError):
        volume = None
    if volume is not None and volume < 0:
        volume = None
    adjusted = _decimal(row.get("adjusted_close"))
    if opened == high == low == closed == Decimal("999999.9999") and volume == 0:
        quality = "PLACEHOLDER"
    elif day not in sessions:
        quality = "NON_SESSION"
    elif None in (opened, high, low, closed):
        quality = "BAD_PRICE"
    elif low > min(opened, closed) or high < max(opened, closed):
        quality = "BAD_OHLC"
    elif volume is None:
        quality = "BAD_VOLUME"
    elif volume == 0:
        quality = "ZERO_VOLUME"
    else:
        quality = "VALID"
    return day, quality, {"open": opened, "high": high, "low": low,
                          "close": closed, "adjusted": adjusted, "volume": volume}


def _read_payload(root: Path, item: dict) -> list[dict]:
    path = (root / item["file"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("payload hors archive ou absent")
    with gzip.open(path, "rb") as stream:
        payload = stream.read()
    if hashlib.sha256(payload).hexdigest() != item["sha256"]:
        raise ValueError(f"hash incorrect pour {path.name}")
    return json.loads(payload)


def load(root: Path, *, max_symbols: int | None = None) -> dict:
    root = root.resolve()
    summary, _ = archive_rows(root)
    manifest = json.loads((root / "universe.json").read_text(encoding="utf-8"))
    records = [{**row, "provider_status": status} for status in ("active", "delisted")
               for row in manifest[status]
               if row.get("Type") == "Common Stock" and row.get("Currency") == "EUR" and row.get("Code")]
    records.sort(key=lambda row: (row["provider_status"], row["Code"]))
    if max_symbols is not None:
        records = records[:max_symbols]
    start, end = (date.fromisoformat(item) for item in summary["window"])
    sessions = set(get_market_calendar("FR_EQ").session_dates(start, end))
    engine = create_engine(build_database_url("fr_primary", "FR_EQ"), pool_pre_ping=True)
    stats = Counter()
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar() != "alpha_trade_fr":
                raise RuntimeError("staging FR refuse une autre base")
            raw_map = {(row["request_key"], row["dataset"]): row["raw_payload_id"]
                       for row in conn.execute(text("""
                           SELECT request_key,dataset,raw_payload_id FROM fr_raw_payloads
                           WHERE provider='EODHD'
                       """)).mappings()}
        bar_sql = text("""
            INSERT INTO fr_provider_bars_staging
            (provider,provider_symbol,session_date,raw_payload_id,open_price,
             high_price,low_price,close_price,provider_adjusted_close,
             provider_volume_split_adjusted,quality_code,observed_at,available_at)
            VALUES ('EODHD',:symbol,:day,:raw,:open,:high,:low,:close,:adjusted,
                    :volume,:quality,:observed,:observed)
            ON DUPLICATE KEY UPDATE quality_code=VALUES(quality_code)
        """)
        action_sql = text("""
            INSERT INTO fr_provider_actions_staging
            (provider,provider_symbol,action_type,event_date,event_ordinal,
             raw_payload_id,event_json,observed_at,available_at)
            VALUES ('EODHD',:symbol,:kind,:day,:ordinal,:raw,:payload,:observed,:observed)
            ON DUPLICATE KEY UPDATE event_json=VALUES(event_json)
        """)
        universe_sql = text("""
            INSERT INTO fr_provider_universe_staging
            (provider,provider_symbol,provider_exchange,provider_status,
             provider_type,currency,reported_isin,reported_name,verified_mic,
             observed_at)
            VALUES ('EODHD',:symbol,'PA',:status,'Common Stock','EUR',:isin,:name,NULL,:observed)
            ON DUPLICATE KEY UPDATE reported_name=VALUES(reported_name),
             reported_isin=VALUES(reported_isin),provider_status=VALUES(provider_status)
        """)
        progress_sql = text("""
            INSERT INTO fr_staging_progress
            (provider,provider_symbol,raw_payload_id,dataset,classifier_version,row_count,valid_count,
             status,completed_at)
            VALUES ('EODHD',:symbol,:raw,:dataset,:classifier,:rows,:valid,'COMPLETED',:now)
            ON DUPLICATE KEY UPDATE row_count=VALUES(row_count),
             valid_count=VALUES(valid_count),classifier_version=VALUES(classifier_version),
             status='COMPLETED',completed_at=VALUES(completed_at)
        """)
        for index, record in enumerate(records, 1):
            symbol = f"{record['Code']}.PA"
            key = hashlib.sha256(symbol.encode()).hexdigest()[:16]
            meta = json.loads((root / "symbols" / f"{key}.json").read_text(encoding="utf-8"))
            observed = datetime.fromisoformat(meta["collected_at"]).astimezone(UTC).replace(tzinfo=None)
            with engine.begin() as conn:
                conn.execute(universe_sql, {"symbol": symbol, "status": record["provider_status"],
                                            "isin": record.get("Isin") or None,
                                            "name": record.get("Name"), "observed": observed})
                for kind in ("eod", "splits", "div"):
                    request_key = f"{symbol}:{summary['window'][0]}:{summary['window'][1]}"
                    raw_id = raw_map[(request_key, kind)]
                    present = conn.execute(text("""
                        SELECT classifier_version FROM fr_staging_progress
                        WHERE provider='EODHD' AND provider_symbol=:symbol
                        AND raw_payload_id=:raw AND dataset=:kind AND status='COMPLETED'
                    """), {"symbol": symbol, "raw": raw_id, "kind": kind}).scalar()
                    if present == CLASSIFIER_VERSION:
                        stats["skipped_payloads"] += 1
                        continue
                    rows = _read_payload(root, meta["payloads"][kind])
                    now = datetime.now(UTC).replace(tzinfo=None)
                    if kind == "eod":
                        prepared = []
                        seen_dates = set()
                        valid = 0
                        for row in rows:
                            day, quality, fields = classify_bar(row, sessions)
                            if day in seen_dates:
                                raise ValueError(f"date EOD dupliquée {symbol}/{day}")
                            seen_dates.add(day)
                            valid += quality == "VALID"
                            stats[quality] += 1
                            prepared.append({"symbol": symbol, "day": day, "raw": raw_id,
                                             "quality": quality, "observed": observed, **fields})
                        for offset in range(0, len(prepared), 500):
                            conn.execute(bar_sql, prepared[offset:offset + 500])
                    else:
                        prepared = []
                        ordinals = Counter()
                        for row in rows:
                            day = date.fromisoformat(str(row["date"]))
                            ordinals[day] += 1
                            prepared.append({"symbol": symbol, "kind": kind, "day": day,
                                             "ordinal": ordinals[day], "raw": raw_id,
                                             "payload": json.dumps(row, ensure_ascii=False),
                                             "observed": observed})
                        if prepared:
                            conn.execute(action_sql, prepared)
                        valid = len(rows)
                    conn.execute(progress_sql, {"symbol": symbol, "raw": raw_id, "dataset": kind,
                                                "classifier": CLASSIFIER_VERSION,
                                                "rows": len(rows), "valid": valid, "now": now})
                    stats["loaded_payloads"] += 1
                    stats[f"{kind}_rows"] += len(rows)
            if index % 25 == 0 or index == len(records):
                print(f"FR staging {index}/{len(records)} loaded={stats['loaded_payloads']} "
                      f"skipped={stats['skipped_payloads']} valid={stats['VALID']}", flush=True)
        return dict(stats)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/eodhd/backfill_2016"))
    parser.add_argument("--max-symbols", type=int)
    args = parser.parse_args()
    print(json.dumps(load(args.root, max_symbols=args.max_symbols), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

"""Archive brute, reprenable, des actions Paris EODHD (sans canonicalisation).

Commande : python -m service.fr.eodhd_backfill --start 2016-01-01 --end 2026-10-01
Ne journalise jamais le token ni l'URL signée. Aucun accès à la base ni batch.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from service.fr.http import verified_system_session

BASE = "https://eodhd.com/api"
_LIMIT_LOCK = threading.Lock()
_NEXT_AT = 0.0
_STOP = threading.Event()


def _fetch(endpoint: str, token: str, params: dict[str, str], *, pace: float) -> list[dict]:
    global _NEXT_AT
    for attempt in range(4):
        if _STOP.is_set():
            raise RuntimeError("collecte arrêtée après erreur d'autorisation")
        with _LIMIT_LOCK:
            delay = max(0.0, _NEXT_AT - time.monotonic())
            if delay:
                time.sleep(delay)
            _NEXT_AT = time.monotonic() + pace
        try:
            session = verified_system_session()
            try:
                response = session.get(f"{BASE}/{endpoint}",
                                       params={**params, "api_token": token, "fmt": "json"},
                                       timeout=45)
            finally:
                session.close()
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"échec réseau {type(exc).__name__}") from None
            time.sleep(2 ** attempt)
            continue
        if response.status_code in (401, 403):
            _STOP.set()
            raise RuntimeError(f"accès EODHD refusé HTTP {response.status_code}")
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
            time.sleep(min(30, 2 ** (attempt + 1)))
            continue
        if not response.ok:
            raise RuntimeError(f"HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError:
            raise RuntimeError("réponse EODHD non JSON") from None
        if not isinstance(data, list):
            raise RuntimeError("réponse EODHD non liste")
        return data
    raise RuntimeError("tentatives EODHD épuisées")


def _atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _archive(root: Path, symbol: str, kind: str, rows: list[dict]) -> dict:
    key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
    folder = root / kind
    folder.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    destination = folder / f"{key}.json.gz"
    temporary = folder / f"{key}.{os.getpid()}.tmp"
    with gzip.open(temporary, "wb") as stream:
        stream.write(payload)
    temporary.replace(destination)
    return {"rows": len(rows), "sha256": hashlib.sha256(payload).hexdigest(),
            "file": str(destination.relative_to(root))}


def _archive_matches(root: Path, item: dict) -> bool:
    try:
        with gzip.open(root / item["file"], "rb") as stream:
            digest = hashlib.sha256(stream.read()).hexdigest()
        return digest == item["sha256"]
    except (OSError, EOFError, KeyError):
        return False


def _collect_symbol(root: Path, record: dict, token: str, start: str, end: str,
                    pace: float) -> dict:
    symbol = f"{record['Code']}.PA"
    key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
    metadata_path = root / "symbols" / f"{key}.json"
    if metadata_path.exists():
        prior = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (prior.get("status") == "COMPLETED" and prior.get("window") == [start, end]
                and set(prior.get("payloads", {})) == {"eod", "splits", "div"}
                and all(_archive_matches(root, item) for item in prior["payloads"].values())):
            return {"symbol": symbol, "status": "SKIPPED", "eod_rows": prior["payloads"]["eod"]["rows"]}
    payloads = {}
    for kind in ("eod", "splits", "div"):
        rows = _fetch(f"{kind}/{quote(symbol, safe='.')}", token,
                      {"from": start, "to": end}, pace=pace)
        if kind == "eod":
            for row in rows:
                day = str(row.get("date", ""))
                if not (start <= day <= end):
                    raise RuntimeError("barre hors fenêtre demandée")
        payloads[kind] = _archive(root, symbol, kind, rows)
    metadata = {"symbol": symbol, "record": record, "window": [start, end],
                "status": "COMPLETED", "collected_at": datetime.now(UTC).isoformat(),
                "payloads": payloads}
    _atomic_json(metadata_path, metadata)
    return {"symbol": symbol, "status": "COMPLETED", "eod_rows": payloads["eod"]["rows"]}


def run(*, root: Path, start: str, end: str, workers: int, pace: float,
        max_symbols: int | None = None) -> dict:
    token = os.environ.get("EODHD_API_TOKEN")
    if not token:
        raise RuntimeError("EODHD_API_TOKEN absent")
    if date.fromisoformat(end) < date.fromisoformat(start):
        raise ValueError("fenêtre inversée")
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "universe.json"
    if manifest_path.exists():
        universe = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        active = _fetch("exchange-symbol-list/PA", token, {}, pace=pace)
        delisted = _fetch("exchange-symbol-list/PA", token, {"delisted": "1"}, pace=pace)
        universe = {"collected_at": datetime.now(UTC).isoformat(),
                    "provider": "EODHD", "exchange_code": "PA",
                    "active": active, "delisted": delisted}
        _atomic_json(manifest_path, universe)
    records = []
    for status in ("active", "delisted"):
        for row in universe[status]:
            if row.get("Type") == "Common Stock" and row.get("Currency") == "EUR" and row.get("Code"):
                records.append({**row, "provider_status": status})
    records.sort(key=lambda row: (row["provider_status"], row["Code"]))
    if max_symbols is not None:
        records = records[:max_symbols]
    codes = [row["Code"] for row in records]
    if len(codes) != len(set(codes)):
        raise RuntimeError("codes fournisseur réutilisés dans le manifeste")
    counts = Counter()
    errors = []
    summary_path = root / "summary.json"
    def report() -> dict:
        payload = {"window": [start, end], "selected": len(records),
                   "by_provider_status": dict(Counter(row["provider_status"] for row in records)),
                   "missing_isin": sum(not row.get("Isin") for row in records),
                   "completed": counts["COMPLETED"], "skipped": counts["SKIPPED"],
                   "failed": counts["FAILED"], "eod_rows": counts["eod_rows"],
                   "errors": errors[-50:], "updated_at": datetime.now(UTC).isoformat()}
        _atomic_json(summary_path, payload)
        return payload
    report()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_collect_symbol, root, row, token, start, end, pace): row["Code"]
                   for row in records}
        for future in as_completed(futures):
            code = futures[future]
            try:
                item = future.result()
            except Exception as exc:
                counts["FAILED"] += 1
                errors.append({"code": code, "error": str(exc)[:160]})
            else:
                counts[item["status"]] += 1
                counts["eod_rows"] += item["eod_rows"]
            done = counts["COMPLETED"] + counts["SKIPPED"] + counts["FAILED"]
            if done % 25 == 0 or done == len(records):
                snapshot = report()
                print(f"FR EODHD {done}/{len(records)} completed={snapshot['completed']} "
                      f"skipped={snapshot['skipped']} failed={snapshot['failed']} "
                      f"bars={snapshot['eod_rows']}", flush=True)
    return report()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/fr/eodhd/backfill_2016"))
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default=(date.today() - timedelta(days=1)).isoformat())
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--requests-per-second", type=float, default=5)
    parser.add_argument("--max-symbols", type=int)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.requests_per_second <= 20:
        parser.error("workers 1..8 et requests-per-second 0..20 requis")
    result = run(root=args.output_root, start=args.start, end=args.end,
                 workers=args.workers, pace=1 / args.requests_per_second,
                 max_symbols=args.max_symbols)
    print(f"Archive FR terminée : {args.output_root} ; {result['completed']} reçus, "
          f"{result['failed']} erreurs, {result['eod_rows']} barres", flush=True)
    if result["failed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

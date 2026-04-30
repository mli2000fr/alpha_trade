"""Phase 1 EODHD — smoke test de cadrage.

Objectifs (cf. ``prompt/iex/plan_eodhd.md`` Phase 1) :
1. Valider que le token ``EODHD_API_TOKEN`` est utilisable.
2. Mesurer le délai de publication du bulk J-1 (``/eod-bulk-last-day/US``).
3. Confirmer le mapping symbole projet -> symbole EODHD sur 20 cas (large caps,
   classes B, ETFs, GOOG/GOOGL, ADRs).
4. Récupérer ``/splits/NVDA.US`` pour valider la reconstruction split-only future.

Ce script **ne touche pas la base** et ne crée pas le module ``service/eodhd/``
(c'est la Phase 2). Il sert uniquement de validation empirique avant de
développer le socle.

Usage::

    $env:EODHD_API_TOKEN = "votre_token"
    python scripts/eodhd_phase1_smoke.py

    # ou plage de dates pour mesurer la régularité de publication du bulk
    python scripts/eodhd_phase1_smoke.py --bulk-days 3

Sortie : log console + JSON dans ``artifacts/eodhd_cache/phase1_smoke_<TS>.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import urllib.request
import urllib.error


EODHD_BASE_URL = "https://eodhd.com/api"

# 20 symboles couvrant les principaux pièges de mapping.
# Format projet -> attendu côté EODHD.
SYMBOL_MAPPING_BATTERY: list[tuple[str, str, str]] = [
    # Large caps simples
    ("AAPL",  "AAPL.US",   "Apple"),
    ("MSFT",  "MSFT.US",   "Microsoft"),
    ("NVDA",  "NVDA.US",   "Nvidia"),
    ("AMZN",  "AMZN.US",   "Amazon"),
    ("META",  "META.US",   "Meta"),
    ("TSLA",  "TSLA.US",   "Tesla"),
    # Classes A/B (point -> tiret côté EODHD)
    ("BRK.B", "BRK-B.US",  "Berkshire Hathaway B"),
    ("BRK.A", "BRK-A.US",  "Berkshire Hathaway A"),
    ("BF.B",  "BF-B.US",   "Brown-Forman B"),
    # Multi-classes (notation point différente)
    ("GOOG",  "GOOG.US",   "Alphabet C"),
    ("GOOGL", "GOOGL.US",  "Alphabet A"),
    # ETFs
    ("SPY",   "SPY.US",    "SPDR S&P 500 ETF"),
    ("QQQ",   "QQQ.US",    "Invesco QQQ"),
    ("IWM",   "IWM.US",    "iShares Russell 2000"),
    ("VTI",   "VTI.US",    "Vanguard Total Stock Market"),
    # ADRs / cross-listings (symboles courts / longs)
    ("BABA",  "BABA.US",   "Alibaba ADR"),
    ("TSM",   "TSM.US",    "Taiwan Semi ADR"),
    ("NVO",   "NVO.US",    "Novo Nordisk ADR"),
    # Mid caps moins liquides (test edge)
    ("AAOI",  "AAOI.US",   "Applied Optoelectronics"),
    # ETF leveraged (peut différer)
    ("TQQQ",  "TQQQ.US",   "ProShares UltraPro QQQ"),
]


# --------------------------------------------------------------------------- #
# HTTP helpers (sans dépendance ``requests`` : la Phase 1 reste minimaliste).  #
# --------------------------------------------------------------------------- #
def _build_url(endpoint: str, params: dict[str, Any]) -> str:
    qs = urlencode(params)
    return f"{EODHD_BASE_URL}{endpoint}?{qs}"


def _http_get_json(url: str, timeout: int = 30) -> tuple[Any, float, int]:
    """Retourne (payload_json, latency_seconds, http_status)."""
    started = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "alpha_trade/eodhd-phase1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            elapsed = time.monotonic() - started
            return json.loads(body), elapsed, status
    except urllib.error.HTTPError as exc:
        elapsed = time.monotonic() - started
        return {"_error": str(exc), "_body": exc.read().decode("utf-8", "replace")}, elapsed, exc.code
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - started
        return {"_error": str(exc)}, elapsed, -1


# --------------------------------------------------------------------------- #
# Tests Phase 1                                                                #
# --------------------------------------------------------------------------- #
def _previous_business_day(d: datetime) -> datetime:
    """Retourne le dernier jour ouvré (lun-ven, sans tenir compte des fériés US)."""
    delta = 1
    while True:
        candidate = d - timedelta(days=delta)
        if candidate.weekday() < 5:  # 0=lun .. 4=ven
            return candidate
        delta += 1


def test_bulk_for_date(token: str, target_date: str) -> dict[str, Any]:
    """Appel `/eod-bulk-last-day/US?date=...` — coût 100 calls sur le quota."""
    url = _build_url(
        f"/eod-bulk-last-day/US",
        {"api_token": token, "date": target_date, "fmt": "json"},
    )
    payload, latency, status = _http_get_json(url, timeout=60)
    result = {
        "target_date": target_date,
        "http_status": status,
        "latency_s": round(latency, 3),
        "payload_size": len(payload) if isinstance(payload, list) else None,
        "first_3_codes": [row.get("code") for row in payload[:3]] if isinstance(payload, list) else None,
        "error": payload.get("_error") if isinstance(payload, dict) else None,
    }
    return result


def test_eod_history(token: str, eodhd_symbol: str, days: int = 30) -> dict[str, Any]:
    """Appel `/eod/<sym>` — coût 1 call."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    url = _build_url(
        f"/eod/{eodhd_symbol}",
        {"api_token": token, "from": start.isoformat(), "to": end.isoformat(), "fmt": "json", "period": "d"},
    )
    payload, latency, status = _http_get_json(url, timeout=30)
    return {
        "symbol": eodhd_symbol,
        "http_status": status,
        "latency_s": round(latency, 3),
        "rows": len(payload) if isinstance(payload, list) else None,
        "first_row": payload[0] if isinstance(payload, list) and payload else None,
        "error": payload.get("_error") if isinstance(payload, dict) else None,
    }


def test_splits(token: str, eodhd_symbol: str) -> dict[str, Any]:
    """Appel `/splits/<sym>` — coût 1 call."""
    url = _build_url(f"/splits/{eodhd_symbol}", {"api_token": token, "fmt": "json"})
    payload, latency, status = _http_get_json(url, timeout=30)
    return {
        "symbol": eodhd_symbol,
        "http_status": status,
        "latency_s": round(latency, 3),
        "rows": len(payload) if isinstance(payload, list) else None,
        "splits": payload if isinstance(payload, list) else None,
        "error": payload.get("_error") if isinstance(payload, dict) else None,
    }


def test_symbol_mapping(token: str) -> list[dict[str, Any]]:
    """Tente un `/eod/<EODHD_SYM>` minimal sur les 20 symboles de la batterie."""
    results: list[dict[str, Any]] = []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=10)
    for project_sym, eodhd_sym, label in SYMBOL_MAPPING_BATTERY:
        url = _build_url(
            f"/eod/{eodhd_sym}",
            {"api_token": token, "from": start.isoformat(), "to": end.isoformat(), "fmt": "json"},
        )
        payload, latency, status = _http_get_json(url, timeout=20)
        ok = isinstance(payload, list) and len(payload) > 0
        results.append({
            "project_symbol": project_sym,
            "eodhd_symbol": eodhd_sym,
            "label": label,
            "ok": ok,
            "rows": len(payload) if isinstance(payload, list) else 0,
            "http_status": status,
            "latency_s": round(latency, 3),
        })
        # Petite politesse : EODHD All-In-One tolère >> 50 req/s mais on évite le burst.
        time.sleep(0.05)
    return results


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1 EODHD smoke test")
    parser.add_argument("--bulk-days", type=int, default=1,
                        help="Nombre de jours ouvrés à tester pour /eod-bulk-last-day (1 par défaut).")
    parser.add_argument("--skip-mapping", action="store_true",
                        help="Saute la batterie de mapping symboles (économise 20 calls).")
    args = parser.parse_args(argv)

    token = os.environ.get("EODHD_API_TOKEN", "").strip()
    if not token:
        print("[ERREUR] EODHD_API_TOKEN absent dans l'environnement.")
        print("        Souscrivez https://eodhd.com/cp/dashboard puis :")
        print('        $env:EODHD_API_TOKEN = "votre_token"')
        return 2

    print(f"[INFO] Token EODHD detecte (longueur={len(token)}).")
    print(f"[INFO] Repertoire cache : artifacts/eodhd_cache/")

    summary: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bulk_tests": [],
        "eod_history_test": None,
        "splits_test": None,
        "mapping_tests": [],
    }

    # 1. Bulk J-1, J-2, ... selon --bulk-days
    today = datetime.now(timezone.utc)
    target = today
    for i in range(args.bulk_days):
        target = _previous_business_day(target)
        target_str = target.strftime("%Y-%m-%d")
        print(f"[BULK] /eod-bulk-last-day/US?date={target_str} ...")
        res = test_bulk_for_date(token, target_str)
        summary["bulk_tests"].append(res)
        if res["payload_size"]:
            print(f"       OK status={res['http_status']} symbols={res['payload_size']} latency={res['latency_s']}s")
        else:
            print(f"       KO status={res['http_status']} error={res['error']}")

    # 2. Historique long sur NVDA (test split obligatoire)
    print("[EOD]  /eod/NVDA.US (30 jours) ...")
    summary["eod_history_test"] = test_eod_history(token, "NVDA.US", days=30)
    eod_res = summary["eod_history_test"]
    print(f"       status={eod_res['http_status']} rows={eod_res['rows']} latency={eod_res['latency_s']}s")

    # 3. Splits NVDA (test golden 10:1 du 2024-06-10)
    print("[SPLT] /splits/NVDA.US ...")
    summary["splits_test"] = test_splits(token, "NVDA.US")
    splt_res = summary["splits_test"]
    print(f"       status={splt_res['http_status']} rows={splt_res['rows']} latency={splt_res['latency_s']}s")
    if splt_res.get("splits"):
        print(f"       payload : {json.dumps(splt_res['splits'], ensure_ascii=False)}")

    # 4. Batterie de mapping symboles
    if not args.skip_mapping:
        print(f"[MAPS] {len(SYMBOL_MAPPING_BATTERY)} symboles ...")
        summary["mapping_tests"] = test_symbol_mapping(token)
        ok_count = sum(1 for r in summary["mapping_tests"] if r["ok"])
        print(f"       OK={ok_count}/{len(summary['mapping_tests'])}")
        for r in summary["mapping_tests"]:
            mark = "OK " if r["ok"] else "KO "
            print(f"       {mark} {r['project_symbol']:6s} -> {r['eodhd_symbol']:10s} "
                  f"rows={r['rows']:>3} status={r['http_status']:>3}  ({r['label']})")

    summary["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Sauvegarde
    out_dir = Path("artifacts/eodhd_cache")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"phase1_smoke_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"[DONE] Resume sauvegarde dans {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


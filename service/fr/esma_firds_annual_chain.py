"""Enchaîne les rejeux FIRDS annuels et leurs réconciliations officielles.

La chaîne est strictement séquentielle. Une année incomplète ou une divergence
avec le dernier Full officiel disponible arrête le traitement. Aucune table
canonique n'est modifiée.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json
from service.fr.esma_firds_download import INDEX_URL, _get_json, _tls_context

LOGGER = logging.getLogger(__name__)
FULL_PATTERN = re.compile(r"^FULINS_E_(\d{8})_\d+of\d+\.zip$")


def validate_history(path: Path, expected_end: date) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"rapport annuel absent : {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("end") != expected_end.isoformat():
        raise ValueError(f"borne annuelle inattendue : {path}")
    if report.get("complete") is not True:
        raise ValueError(f"rapport annuel incomplet : {path}")
    if report.get("files_processed") != report.get("files_indexed"):
        raise ValueError(f"fichiers non entièrement rejoués : {path}")
    if report.get("missing_files"):
        raise ValueError(f"archives manquantes dans le rejeu : {path}")
    return report


def _select_latest_full_date(file_names: list[str], end: date) -> date:
    dates = set()
    for name in file_names:
        match = FULL_PATTERN.fullmatch(name)
        if not match:
            continue
        day = date.fromisoformat(
            f"{match[1][:4]}-{match[1][4:6]}-{match[1][6:]}")
        if day <= end:
            dates.add(day)
    if not dates:
        raise ValueError(f"aucun Full FULINS_E disponible avant {end}")
    return max(dates)


def latest_full_date(end: date, *, lookback_days: int = 45) -> date:
    lower = end - timedelta(days=lookback_days)
    params = urllib.parse.urlencode({
        "q": "file_type:FULINS",
        "fq": (f"publication_date:[{lower}T00:00:00Z TO "
               f"{end}T23:59:59Z]"),
        "wt": "json", "rows": 1000, "sort": "id asc",
    })
    last_error = None
    for attempt in range(3):
        try:
            payload = _get_json(f"{INDEX_URL}?{params}", _tls_context())
            names = [row.get("file_name", "")
                     for row in payload["response"]["docs"]]
            return _select_latest_full_date(names, end)
        except Exception as exc:  # pragma: no cover - réseau réel
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"index ESMA inaccessible : {last_error}")


def _run(command: list[str], log_dir: Path, label: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{label}.stdout.log"
    stderr_path = log_dir / f"{label}.stderr.log"
    with stdout_path.open("a", encoding="utf-8") as stdout, \
            stderr_path.open("a", encoding="utf-8") as stderr:
        marker = datetime.now(timezone.utc).isoformat()
        stdout.write(f"\n[{marker}] START {' '.join(command)}\n")
        stdout.flush()
        result = subprocess.run(command, stdout=stdout, stderr=stderr,
                                cwd=Path.cwd(), check=False)
        stdout.write(f"[{datetime.now(timezone.utc).isoformat()}] END exit={result.returncode}\n")
        stdout.flush()
    if result.returncode:
        raise RuntimeError(f"commande {label} en échec, exit={result.returncode}")


def _wait_for_report(path: Path, expected_end: date, timeout_hours: float) -> dict:
    deadline = time.monotonic() + timeout_hours * 3600
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"attente du rapport expirée : {path}")
        time.sleep(30)
    return validate_history(path, expected_end)


def run_chain(*, start_year: int, end_date: date, replay_root: Path,
              output_root: Path, log_root: Path, state_path: Path,
              wait_for_first: bool, wait_timeout_hours: float) -> dict:
    if end_date.year < start_year:
        raise ValueError("end_date antérieure au start_year")
    state = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "start_year": start_year, "end_date": end_date.isoformat(),
        "status": "RUNNING", "years": {}, "canonical_go": False,
    }
    _atomic_json(state_path, state)
    try:
        for year in range(start_year, end_date.year + 1):
            year_end = min(date(year, 12, 31), end_date)
            history_path = output_root / f"history_{year}_observed_v2.json"
            previous_path = output_root / f"history_{year - 1}_observed_v2.json"
            row = {"end": year_end.isoformat(), "status": "RUNNING"}
            state["years"][str(year)] = row
            _atomic_json(state_path, state)

            if history_path.is_file():
                history = validate_history(history_path, year_end)
                row["replay"] = "REUSED"
            elif year == start_year and wait_for_first:
                history = _wait_for_report(history_path, year_end,
                                           wait_timeout_hours)
                row["replay"] = "WAITED_FOR_EXISTING"
            else:
                validate_history(previous_path, date(year - 1, 12, 31))
                _run([
                    sys.executable, "-u", "-m", "service.fr.esma_firds_history",
                    "--root", str(replay_root),
                    "--resume-from", str(previous_path),
                    "--end-date", year_end.isoformat(),
                    "--output", str(history_path),
                ], log_root / str(year), "replay")
                history = validate_history(history_path, year_end)
                row["replay"] = "COMPLETED"

            row.update({
                "files": history["files_processed"],
                "versions": history["counts"]["version_records"],
                "anomalies": len(history["anomalies"]),
            })
            full_day = latest_full_date(year_end)
            full_root = replay_root.parent / f"full_reconciliation_{year}"
            _run([
                sys.executable, "-u", "-m", "service.fr.esma_firds_download",
                "--full-date", full_day.isoformat(),
                "--end-date", full_day.isoformat(),
                "--root", str(full_root), "--workers", "3",
            ], log_root / str(year), "full_download")
            reconciliation_path = output_root / f"full_reconciliation_{year}_observed_v2.json"
            _run([
                sys.executable, "-u", "-m", "service.fr.esma_firds_full_reconcile",
                "--history", str(history_path),
                "--full-root", str(full_root / str(full_day.year)),
                "--full-date", full_day.isoformat(),
                "--output", str(reconciliation_path),
            ], log_root / str(year), "full_reconcile")
            reconciliation = json.loads(
                reconciliation_path.read_text(encoding="utf-8"))
            if reconciliation.get("candidate_pairs_reconciled") is not True:
                raise ValueError(f"réconciliation Full divergente pour {year}")
            row.update({
                "full_date": full_day.isoformat(),
                "active_pairs": reconciliation["replayed_active_records"],
                "status": "COMPLETED",
            })
            _atomic_json(state_path, state)
        state["status"] = "COMPLETED"
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        state["status"] = "FAILED"
        state["error"] = f"{type(exc).__name__}: {exc}"
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(state_path, state)
        raise
    _atomic_json(state_path, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--replay-root", type=Path,
                        default=Path("artifacts/fr/esma_firds/replay_2018"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/fr/esma_firds/replay_2018"))
    parser.add_argument("--log-root", type=Path,
                        default=Path("log/batch/fr-esma-annual-chain"))
    parser.add_argument("--state", type=Path,
                        default=Path("artifacts/fr/esma_firds/replay_2018/annual_chain_state.json"))
    parser.add_argument("--wait-for-first", action="store_true")
    parser.add_argument("--wait-timeout-hours", type=float, default=6)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    result = run_chain(
        start_year=args.start_year, end_date=args.end_date,
        replay_root=args.replay_root, output_root=args.output_root,
        log_root=args.log_root, state_path=args.state,
        wait_for_first=args.wait_for_first,
        wait_timeout_hours=args.wait_timeout_hours,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

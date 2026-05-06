"""Sprint S24.2 — Agrège la fenêtre 30 j de runs sandbox nightly.

Lit tous les ``artifacts/sandbox_runs/<date>/health.json`` puis écrit
``artifacts/sandbox_runs/_rollup.json`` :

```json
{
  "generated_at": "...",
  "window_days": 30,
  "n_days_observed": 27,
  "streak_green": 12,
  "streak_red": 0,
  "n_success": 26,
  "n_failure": 1,
  "n_cancelled": 0,
  "last_failure": "2026-04-12",
  "calendar": [
    {"date": "2026-05-06", "status": "success"},
    {"date": "2026-05-05", "status": "success"},
    ...
  ]
}
```
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)

DEFAULT_SANDBOX_DIR = Path("artifacts/sandbox_runs/")
DEFAULT_WINDOW = 30


def compute_rollup(
    sandbox_dir: Path,
    *,
    window: int = DEFAULT_WINDOW,
    today: date | None = None,
) -> dict:
    today = today or datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=window - 1)
    calendar: list[dict] = []
    n_success = n_failure = n_cancelled = 0
    last_failure: str | None = None
    streak_green = 0
    streak_red = 0
    in_green = True

    # Walk dates from today → cutoff
    current = today
    while current >= cutoff:
        d_str = current.isoformat()
        health_path = sandbox_dir / d_str / "health.json"
        status: str
        if health_path.exists():
            try:
                payload = json.loads(health_path.read_text(encoding="utf-8"))
                status = str(payload.get("status", "unknown")).lower()
            except Exception:
                status = "unknown"
        else:
            status = "missing"
        calendar.append({"date": d_str, "status": status})

        if status == "success":
            n_success += 1
            if in_green:
                streak_green += 1
        elif status == "failure":
            n_failure += 1
            if last_failure is None:
                last_failure = d_str
            in_green = False
            streak_red += 1
        elif status == "cancelled":
            n_cancelled += 1
            in_green = False
        # "missing" / "unknown" cassent la streak verte mais pas la rouge.
        if status not in ("success",):
            in_green = False

        current -= timedelta(days=1)

    n_observed = sum(
        1 for c in calendar if c["status"] in ("success", "failure", "cancelled")
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window,
        "n_days_observed": n_observed,
        "streak_green": streak_green,
        "streak_red": streak_red,
        "n_success": n_success,
        "n_failure": n_failure,
        "n_cancelled": n_cancelled,
        "last_failure": last_failure,
        "calendar": calendar,
    }


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Rollup sandbox nightly 30 j.")
    p.add_argument("--sandbox-dir", type=Path, default=DEFAULT_SANDBOX_DIR)
    p.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    p.add_argument("--out", type=Path, default=None,
                   help="Chemin du rollup (défaut: <sandbox-dir>/_rollup.json).")
    args = p.parse_args(argv)

    rollup = compute_rollup(args.sandbox_dir, window=args.window)
    target = args.out or args.sandbox_dir / "_rollup.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rollup, indent=2), encoding="utf-8")
    LOGGER.info(
        "rollup écrit : %s — streak_green=%d n_failure=%d",
        target, rollup["streak_green"], rollup["n_failure"],
    )
    print(str(target))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


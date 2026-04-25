from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from common.utils import configure_root_logging
from database.assets import insert_assets_to_db
from service.alpaca.clientAlpaca import fetch_alpaca_assets

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: Dict[str, Any]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def import_alpaca_assets() -> Dict[str, Any]:
    started_at = _utc_now_naive()
    summary: Dict[str, Any] = {
        "run_id": _build_run_id("import-assets"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "duration_seconds": 0.0,
        "assets_fetched": 0,
        "rows_upserted": 0,
    }
    assets = list(fetch_alpaca_assets())
    summary["assets_fetched"] = len(assets)
    summary["rows_upserted"] = int(insert_assets_to_db(assets) or 0)
    finished_at = _utc_now_naive()
    summary["finished_at"] = finished_at.isoformat(timespec="seconds")
    summary["duration_seconds"] = round((finished_at - started_at).total_seconds(), 2)
    LOGGER.info(
        "Resume import assets Alpaca | run_id=%s assets_fetched=%s rows_upserted=%s duration_s=%s",
        summary["run_id"],
        summary["assets_fetched"],
        summary["rows_upserted"],
        summary["duration_seconds"],
    )
    return summary


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/import_alpaca_assets.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    summary = import_alpaca_assets()
    _emit_run_summary(summary)


if __name__ == "__main__":
    main()




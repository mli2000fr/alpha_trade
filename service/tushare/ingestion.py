from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from service.tushare.adapters import adapt_staging_row
from service.tushare.client import TushareClient
from service.tushare.models import ENDPOINT_SPECS
from service.tushare.storage import persist_page, utcnow_naive

DEFAULT_STATE_ROOT = Path("artifacts/cn/tushare/state")


@dataclass(slots=True)
class IngestionCounters:
    requested: int = 0
    received: int = 0
    persisted: int = 0
    empty: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def merge(self, other: IngestionCounters) -> None:
        for field_name in ("requested", "received", "persisted", "empty", "failed"):
            setattr(self, field_name, getattr(self, field_name) + getattr(other, field_name))
        self.warnings.extend(other.warnings)
        self.details.update(other.details)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _date_text(value: date | None) -> str | None:
    return value.strftime("%Y%m%d") if value else None


def _parameter_variants(endpoint: str) -> list[dict[str, Any]]:
    if endpoint == "stock_basic":
        return [{"list_status": status} for status in ("L", "D", "P")]
    if endpoint == "trade_cal":
        return [{"exchange": exchange} for exchange in ("SSE", "SZSE", "BSE")]
    if endpoint == "index_daily":
        return [{"ts_code": symbol} for symbol in ("000001.SH", "399001.SZ", "000300.SH", "399006.SZ", "899050.BJ")]
    return [{}]


class ResumeState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.payload: dict[str, Any] = {}
        if path.exists():
            self.payload = json.loads(path.read_text(encoding="utf-8"))

    def completed(self, endpoint: str, variant: str) -> bool:
        return self.payload.get(endpoint, {}).get(variant, {}).get("status") == "COMPLETED"

    def offset(self, endpoint: str, variant: str) -> int:
        return int(self.payload.get(endpoint, {}).get(variant, {}).get("offset", 0))

    def update(self, endpoint: str, variant: str, *, offset: int, status: str) -> None:
        self.payload.setdefault(endpoint, {})[variant] = {"offset": offset, "status": status}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)


class TushareIngestionService:
    def __init__(
        self,
        *,
        client: TushareClient,
        engine: Engine,
        run_id: str,
        page_limit: int = 5000,
        max_pages: int = 100_000,
        state_root: Path = DEFAULT_STATE_ROOT,
        state_key: str | None = None,
    ) -> None:
        self.client = client
        self.engine = engine
        self.run_id = run_id
        self.page_limit = max(1, int(page_limit))
        self.max_pages = max(1, int(max_pages))
        self.state = ResumeState(state_root / f"{state_key or run_id}.json")

    def collect_endpoint(
        self,
        endpoint: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        dry_run: bool = False,
        resume: bool = True,
    ) -> IngestionCounters:
        if endpoint not in ENDPOINT_SPECS:
            raise KeyError(f"Endpoint Tushare non autorisé : {endpoint}")
        spec = ENDPOINT_SPECS[endpoint]
        total = IngestionCounters(details={"endpoint": endpoint})
        for variant_no, variant_params in enumerate(_parameter_variants(endpoint)):
            scope = {
                "variant": variant_params,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            }
            variant = f"v{variant_no}:{json.dumps(scope, sort_keys=True)}"
            if resume and self.state.completed(endpoint, variant):
                total.details.setdefault("resumed_completed", []).append(variant)
                continue
            offset = self.state.offset(endpoint, variant) if resume else 0
            for _page_no in range(self.max_pages):
                params = dict(variant_params)
                if spec.date_parameter_mode == "range":
                    if start_date:
                        params["start_date"] = _date_text(start_date)
                    if end_date:
                        params["end_date"] = _date_text(end_date)
                params.update({"limit": self.page_limit, "offset": offset})
                total.requested += 1
                page = self.client.query(spec.api_name, params=params, fields=spec.fields)
                rows = list(page.rows)
                total.received += len(rows)
                if not rows:
                    total.empty += 1
                    self.state.update(endpoint, variant, offset=offset, status="COMPLETED")
                    break
                observed_at = utcnow_naive()
                available_at = observed_at
                adapted = [
                    adapt_staging_row(
                        endpoint,
                        row,
                        run_id=self.run_id,
                        raw_id=None,
                        observed_at=observed_at,
                        available_at=available_at,
                    )
                    for row in rows
                ]
                if not dry_run:
                    _, persisted = persist_page(
                        self.engine,
                        page=page,
                        page_key=f"{variant_no}:{offset}",
                        run_id=self.run_id,
                        observed_at=observed_at,
                        available_at=available_at,
                        adapted_rows=adapted,
                    )
                    total.persisted += persisted
                offset += len(rows)
                self.state.update(endpoint, variant, offset=offset, status="RUNNING")
                if len(rows) < self.page_limit:
                    self.state.update(endpoint, variant, offset=offset, status="COMPLETED")
                    break
            else:
                raise RuntimeError(f"Pagination Tushare non bornée : endpoint={endpoint} variant={variant}")
        total.details["quota_calls"] = self.client.quota.calls
        return total


__all__ = ["IngestionCounters", "ResumeState", "TushareIngestionService"]

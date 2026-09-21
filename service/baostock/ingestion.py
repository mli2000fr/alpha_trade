from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from service.baostock.adapters import adapt_staging_row
from service.baostock.client import BaoStockClient
from service.baostock.models import BaoStockPage
from service.tushare.ingestion import IngestionCounters
from service.tushare.storage import persist_page, utcnow_naive

DEFAULT_STATE_ROOT = Path("artifacts/cn/baostock/state")
DEFAULT_INDICES = ("sh.000001", "sz.399001", "sh.000300", "sz.399006")


class BaoStockResumeState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.payload: dict[str, Any] = {}
        if path.exists():
            self.payload = json.loads(path.read_text(encoding="utf-8"))

    def completed(self, key: str) -> bool:
        return self.payload.get(key, {}).get("status") == "COMPLETED"

    def mark_completed(self, key: str) -> None:
        self.payload[key] = {"status": "COMPLETED"}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


class BaoStockIngestionService:
    def __init__(
        self,
        *,
        client: BaoStockClient,
        engine: Engine,
        run_id: str,
        state_root: Path = DEFAULT_STATE_ROOT,
        state_key: str | None = None,
        max_symbols: int | None = None,
    ) -> None:
        self.client = client
        self.engine = engine
        self.run_id = run_id
        self.state = BaoStockResumeState(state_root / f"{state_key or run_id}.json")
        self.max_symbols = max_symbols
        self._master: BaoStockPage | None = None

    def _stock_master(self) -> BaoStockPage:
        if self._master is None:
            self._master = self.client.stock_basic()
        return self._master

    def equity_symbols(self, *, include_inactive: bool) -> list[str]:
        rows = self._stock_master().rows
        symbols = [
            str(row.get("code") or "").lower()
            for row in rows
            if str(row.get("type") or "") == "1"
            and (include_inactive or str(row.get("status") or "") == "1")
            and str(row.get("code") or "").lower().startswith(("sh.", "sz."))
        ]
        symbols = sorted(set(filter(None, symbols)))
        return symbols[: self.max_symbols] if self.max_symbols else symbols

    def _persist(self, page: BaoStockPage, page_key: str, *, dry_run: bool) -> tuple[int, int]:
        observed_at = utcnow_naive()
        adapted = [
            adapt_staging_row(
                page.endpoint,
                row,
                run_id=self.run_id,
                raw_id=None,
                observed_at=observed_at,
                available_at=observed_at,
            )
            for row in page.rows
        ]
        if dry_run:
            return 0, 0
        return persist_page(
            self.engine,
            page=page,
            page_key=page_key,
            run_id=self.run_id,
            observed_at=observed_at,
            available_at=observed_at,
            adapted_rows=adapted,
            provider="baostock",
        )

    def collect_endpoint(
        self,
        endpoint: str,
        *,
        start_date: date | None,
        end_date: date | None,
        dry_run: bool = False,
        resume: bool = True,
        include_inactive: bool = False,
    ) -> IngestionCounters:
        start = (start_date or date(1990, 1, 1)).isoformat()
        end = (end_date or date.today()).isoformat()
        total = IngestionCounters(details={"endpoint": endpoint, "provider": "baostock"})
        if endpoint == "stock_basic":
            pages = [("all", self._stock_master())]
        elif endpoint == "trade_cal":
            pages = [(f"{start}:{end}", self.client.trade_calendar(start, end))]
        elif endpoint == "index_daily":
            pages = [(symbol, self.client.daily(symbol, start, end, index=True)) for symbol in DEFAULT_INDICES]
        elif endpoint in {"daily", "adj_factor"}:
            symbols = self.equity_symbols(include_inactive=include_inactive)
            total.details["symbols"] = len(symbols)
            pages = (
                (
                    symbol,
                    self.client.daily(symbol, start, end)
                    if endpoint == "daily"
                    else self.client.adjustment_factors(symbol, start, end),
                )
                for symbol in symbols
            )
        else:
            raise KeyError(f"Endpoint BaoStock non autorisé : {endpoint}")

        for page_key, page in pages:
            state_key = f"{endpoint}|{page_key}|{start}|{end}"
            if resume and self.state.completed(state_key):
                total.details.setdefault("resumed", 0)
                total.details["resumed"] += 1
                continue
            total.requested += 1
            total.received += len(page.rows)
            if not page.rows:
                total.empty += 1
            _raw, persisted = self._persist(page, page_key, dry_run=dry_run)
            total.persisted += persisted
            if not dry_run:
                self.state.mark_completed(state_key)
        total.details["provider_calls"] = self.client.calls
        return total


__all__ = ["BaoStockIngestionService", "BaoStockResumeState"]

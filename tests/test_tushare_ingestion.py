from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from service.tushare.ingestion import ResumeState, TushareIngestionService
from service.tushare.models import TusharePage


class FakeQuota:
    calls = 0


class FakeClient:
    def __init__(self, pages: list[tuple[dict[str, Any], ...]]) -> None:
        self.pages = pages
        self.quota = FakeQuota()
        self.calls: list[dict[str, Any]] = []

    def query(self, endpoint: str, *, params: dict[str, Any], fields: tuple[str, ...]) -> TusharePage:
        self.calls.append(params)
        self.quota.calls += 1
        rows = self.pages.pop(0)
        return TusharePage(endpoint, fields, rows, {"params": params}, {"code": 0}, 200, 0)


def test_empty_page_completes_resume_scope(tmp_path: Path) -> None:
    client = FakeClient([()])
    service = TushareIngestionService(
        client=client,  # type: ignore[arg-type]
        engine=object(),  # type: ignore[arg-type]
        run_id="run-1",
        state_root=tmp_path,
        state_key="daily-job",
    )
    result = service.collect_endpoint(
        "daily", start_date=date(2026, 9, 1), end_date=date(2026, 9, 2), dry_run=True
    )
    assert result.requested == 1
    assert result.empty == 1
    assert (tmp_path / "daily-job.json").exists()


def test_resume_skips_same_scope_but_not_a_new_date(tmp_path: Path) -> None:
    client = FakeClient([(), ()])
    first = TushareIngestionService(
        client=client,  # type: ignore[arg-type]
        engine=object(),  # type: ignore[arg-type]
        run_id="run-1",
        state_root=tmp_path,
        state_key="daily-job",
    )
    first.collect_endpoint(
        "daily", start_date=date(2026, 9, 1), end_date=date(2026, 9, 2), dry_run=True
    )
    second = TushareIngestionService(
        client=client,  # type: ignore[arg-type]
        engine=object(),  # type: ignore[arg-type]
        run_id="run-2",
        state_root=tmp_path,
        state_key="daily-job",
    )
    skipped = second.collect_endpoint(
        "daily", start_date=date(2026, 9, 1), end_date=date(2026, 9, 2), dry_run=True
    )
    fresh = second.collect_endpoint(
        "daily", start_date=date(2026, 9, 2), end_date=date(2026, 9, 3), dry_run=True
    )
    assert skipped.requested == 0
    assert skipped.details["resumed_completed"]
    assert fresh.requested == 1
    assert len(client.calls) == 2


def test_resume_state_is_written_atomically(tmp_path: Path) -> None:
    state = ResumeState(tmp_path / "state.json")
    state.update("daily", "scope", offset=5000, status="RUNNING")
    reloaded = ResumeState(tmp_path / "state.json")
    assert reloaded.offset("daily", "scope") == 5000
    assert not (tmp_path / "state.tmp").exists()

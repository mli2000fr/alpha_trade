"""T-EOD-11 — Stooq cross-check effectivement câblé dans le pipeline EODHD
(plan_eodhd.md §5.7 + §7.1).

Vérifie que ``run_eodhd_ingestion`` :
- appelle bien ``compare_with_stooq`` quand ``enable_stooq_cross_check=True``,
- enregistre les anomalies dans ``run_summary["cross_check_stooq"]``,
- reste **non bloquant** en cas d'échec Stooq (``failed=True`` mais pas d'exception).
"""
from __future__ import annotations

from typing import Any

import pytest

from dataIntegrityEngine import import_eodhd_bar
from service.eodhd import accounts as eodhd_accounts
from service.eodhd import quota as eodhd_quota


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.committed = 0
        self.rolled_back = 0

    def execute(self, stmt) -> Any:  # pragma: no cover - non utilisé en dry-run
        self.executed.append(stmt)
        class _R:
            rowcount = 0
        return _R()

    def commit(self) -> None: self.committed += 1
    def rollback(self) -> None: self.rolled_back += 1
    def close(self) -> None: ...


@pytest.fixture
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("EODHD_API_TOKEN", "TEST")
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()
    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path)
    monkeypatch.setattr(eodhd_quota, "_DEFAULT_TRACKER", tracker, raising=False)
    monkeypatch.setattr(
        import_eodhd_bar,
        "_get_active_tradable_symbols",
        lambda session: ["AAPL", "NVDA"],
    )
    monkeypatch.setattr(
        import_eodhd_bar, "fetch_eod_bulk",
        lambda **kwargs: [
            {"code": "AAPL", "date": "2026-04-28", "open": 192.0, "high": 193.0,
             "low": 191.0, "close": 192.5, "adjusted_close": 192.5, "volume": 50_000_000},
            {"code": "NVDA", "date": "2026-04-28", "open": 165.0, "high": 167.0,
             "low": 164.0, "close": 165.5, "adjusted_close": 165.5, "volume": 200_000_000},
        ],
    )
    monkeypatch.setattr(
        import_eodhd_bar, "fetch_splits", lambda symbol, **kwargs: []
    )
    yield {"tracker": tracker}
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()


def test_stooq_cross_check_called_and_anomalies_recorded(monkeypatch, _env):
    """Le pipeline doit invoquer compare_with_stooq et propager les anomalies."""
    captured: dict[str, Any] = {}

    def _fake_compare(ingested_bars, **kwargs):
        captured["ingested_bars"] = dict(ingested_bars)
        captured["kwargs"] = dict(kwargs)
        return [
            {"symbol": "AAPL", "trade_date": "2026-04-28", "kind": "volume_ratio_low",
             "ingested": {"close": 192.5, "volume": 50_000_000},
             "stooq": {"close": 192.5, "volume": 600_000_000},
             "volume_ratio": 0.083},
        ]

    monkeypatch.setattr(
        "dataIntegrityEngine.cross_check_stooq.compare_with_stooq", _fake_compare
    )

    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        enable_stooq_cross_check=True,
        config={},
        session=_FakeSession(),
        tracker=_env["tracker"],
    )

    assert "ingested_bars" in captured, "compare_with_stooq pas appelé"
    assert set(captured["ingested_bars"].keys()) == {"AAPL", "NVDA"}
    assert summary["cross_check_stooq"] == {
        "anomalies_count": 1, "failed": False, "skipped": False,
    }


def test_stooq_failure_is_non_blocking(monkeypatch, _env):
    """Si Stooq lève, le pipeline DOIT continuer et marquer failed=True."""
    def _broken_compare(*args, **kwargs):
        raise RuntimeError("Stooq down")

    monkeypatch.setattr(
        "dataIntegrityEngine.cross_check_stooq.compare_with_stooq", _broken_compare
    )

    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        enable_stooq_cross_check=True,
        config={},
        session=_FakeSession(),
        tracker=_env["tracker"],
    )

    # Pas de crash + pipeline arrive au bout
    assert summary["mode"] == "dry_run"
    assert summary["cross_check_stooq"]["failed"] is True
    assert summary["cross_check_stooq"]["anomalies_count"] == 0
    # Les barres EODHD sont quand même présentes dans le summary
    assert summary["matched_in_bulk"] == 2


def test_stooq_skipped_when_disabled_flag(monkeypatch, _env):
    """``enable_stooq_cross_check=False`` -> pas d'appel + skipped=True."""
    def _should_not_be_called(*a, **k):
        raise AssertionError("Stooq ne doit pas être appelé quand désactivé")

    monkeypatch.setattr(
        "dataIntegrityEngine.cross_check_stooq.compare_with_stooq",
        _should_not_be_called,
    )

    summary = import_eodhd_bar.run_eodhd_ingestion(
        dry_run=True,
        target_date="2026-04-28",
        enable_stooq_cross_check=False,
        config={},
        session=_FakeSession(),
        tracker=_env["tracker"],
    )

    assert summary["cross_check_stooq"]["skipped"] is True
    assert summary["cross_check_stooq"]["anomalies_count"] == 0


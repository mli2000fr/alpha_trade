from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib import error

import pytest

import core.eligibility as eligibility
import database.assets as assets
import risk_management.audit as audit
import service._finnhub_cache as finnhub_cache
import service._telemetry as telemetry
import service.eodhd.cache as eodhd_cache_module
import service.stooq.clientStooq as stooq_client
from risk_management.models import PortfolioEntry


class _FakeRiskRepository:
    def __init__(self) -> None:
        self.decisions_calls: list[tuple[list[dict[str, object]], str | None]] = []
        self.targets_calls: list[tuple[list[dict[str, object]], str | None]] = []

    def write_risk_decisions(self, records: list[dict[str, object]], account_id: str | None = None) -> int:
        self.decisions_calls.append((records, account_id))
        return len(records)

    def write_portfolio_targets(self, records: list[dict[str, object]], account_id: str | None = None) -> int:
        self.targets_calls.append((records, account_id))
        return len(records)


class _FakeResponse:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


def _portfolio_entry(symbol: str, approved_shares: int, *, decision: str = "ACCEPTED") -> PortfolioEntry:
    return PortfolioEntry(
        symbol=symbol,
        sector="TECH",
        entry_price=123.4,
        score_used=0.91,
        score_source="final_score_sentiment",
        atr_20=4.2,
        proposed_shares=max(approved_shares, 1),
        approved_shares=approved_shares,
        target_notional=approved_shares * 123.4,
        target_weight=0.15,
        decision=decision,
        decision_reason="ok",
        conviction_score=0.88,
        predicted_proba=0.77,
        historical_win_rate=0.61,
        effective_probability=0.69,
        kelly_fraction=0.12,
        sizing_method="atr",
        correlation_blocker=None,
        correlation_value=None,
        company_idio_score=0.45,
        macro_regime_score=0.32,
        company_idio_signal_norm=0.22,
        macro_regime_signal_norm=0.18,
        company_idio_component=0.14,
        macro_regime_component=0.11,
        quant_component=0.63,
        walk_forward_sentiment_weight=0.15,
        walk_forward_macro_weight=0.1,
        walk_forward_quant_weight=0.75,
        calibration_run_id="cal-1",
        calibration_source="walk_forward",
        candidate_rank=1,
        decision_rank=2,
        stop_price_initial=118.0,
        risk_per_share=5.4,
        risk_budget_dollars=540.0,
        initial_risk_dollars=540.0,
        score_snapshot_date=date(2026, 4, 28),
        price_asof_date=date(2026, 4, 28),
        atr_asof_date=date(2026, 4, 28),
        prediction_asof_date=date(2026, 4, 28),
        ml_metrics_asof_date=date(2026, 4, 28),
    )


def test_finnhub_cache_store_and_get_profile_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FINNHUB_CACHE_DIR", str(tmp_path))

    finnhub_cache.store_profile(" aapl ", {"name": "Apple", "marketCapitalization": 100.0})

    assert finnhub_cache.get_cached_profile("AAPL") == {
        "name": "Apple",
        "marketCapitalization": 100.0,
    }


def test_finnhub_cache_returns_none_for_stale_or_corrupted_payload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FINNHUB_CACHE_DIR", str(tmp_path))
    stale_path = tmp_path / "MSFT.json"
    stale_path.write_text(
        json.dumps(
            {
                "_cached_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                "profile": {"name": "Microsoft"},
            }
        ),
        encoding="utf-8",
    )
    broken_path = tmp_path / "NVDA.json"
    broken_path.write_text("{not-json", encoding="utf-8")

    assert finnhub_cache.get_cached_profile("MSFT", ttl_days=7) is None
    assert finnhub_cache.get_cached_profile("NVDA") is None


def test_finnhub_cache_invalidate_and_symbol_validation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FINNHUB_CACHE_DIR", str(tmp_path))
    finnhub_cache.store_profile("TSLA", {"name": "Tesla"})

    finnhub_cache.invalidate("TSLA")

    assert finnhub_cache.get_cached_profile("TSLA") is None
    with pytest.raises(ValueError, match="symbol invalide"):
        finnhub_cache.store_profile("***", {"name": "bad"})


def test_eodhd_disk_cache_set_get_and_expire(monkeypatch, tmp_path: Path) -> None:
    cache = eodhd_cache_module.EodhdDiskCache(root=tmp_path)
    monkeypatch.setattr(eodhd_cache_module.time, "time", lambda: 1000.0)
    cache.set("splits", "AAPL/2026", {"ok": True})

    monkeypatch.setattr(eodhd_cache_module.time, "time", lambda: 1005.0)
    assert cache.get("splits", "AAPL/2026", ttl_seconds=10) == {"ok": True}

    monkeypatch.setattr(eodhd_cache_module.time, "time", lambda: 2000.0)
    assert cache.get("splits", "AAPL/2026", ttl_seconds=10) is None


def test_eodhd_disk_cache_get_or_fetch_and_invalidate_namespace(tmp_path: Path) -> None:
    cache = eodhd_cache_module.EodhdDiskCache(root=tmp_path)
    calls: list[str] = []

    def _loader() -> dict[str, str]:
        calls.append("called")
        return {"source": "loader"}

    first = cache.get_or_fetch("dividends", "MSFT", _loader, ttl_seconds=60)
    second = cache.get_or_fetch("dividends", "MSFT", _loader, ttl_seconds=60)
    other = cache.get_or_fetch("splits", "MSFT", lambda: {"other": "ns"}, ttl_seconds=60)

    removed = cache.invalidate("dividends")

    assert first == {"source": "loader"}
    assert second == {"source": "loader"}
    assert other == {"other": "ns"}
    assert calls == ["called"]
    assert removed == 1
    assert cache.get("dividends", "MSFT", ttl_seconds=60) is None
    assert cache.get("splits", "MSFT", ttl_seconds=60) == {"other": "ns"}


def test_telemetry_bump_snapshot_and_reset() -> None:
    telemetry.reset_telemetry()

    telemetry.bump("alpaca", "requests_total")
    telemetry.bump("alpaca", "requests_total", by=2)
    telemetry.bump("alpaca", "success_total")
    telemetry.bump("", "ignored")
    telemetry.bump("alpaca", "")

    assert telemetry.get_telemetry("alpaca") == {
        "requests_total": 3,
        "success_total": 1,
    }
    assert telemetry.get_telemetry() == {
        "alpaca": {"requests_total": 3, "success_total": 1}
    }

    telemetry.reset_telemetry()
    assert telemetry.get_telemetry() == {}


def test_stooq_symbol_and_parse_csv_skip_invalid_rows() -> None:
    raw = "Date,Open,High,Low,Close,Volume\n2026-04-28,10,11,9,10.5,1000\n2026-04-29,broken,11,9,10.5,1000\n"

    assert stooq_client._stooq_symbol("AAPL") == "aapl.us"
    assert stooq_client._stooq_symbol("spy.us") == "spy.us"
    assert stooq_client._parse_csv(raw) == [
        {
            "date": date(2026, 4, 28),
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.5,
            "volume": 1000.0,
        }
    ]


def test_fetch_daily_bars_builds_request_and_parses_response(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _fake_urlopen(req, timeout: float):
        seen["url"] = req.full_url
        seen["timeout"] = timeout
        seen["headers"] = {key.lower(): value for key, value in req.header_items()}
        return _FakeResponse("Date,Open,High,Low,Close,Volume\n2026-04-28,10,11,9,10.5,1000\n")

    monkeypatch.setattr(stooq_client.request, "urlopen", _fake_urlopen)

    bars = stooq_client.fetch_daily_bars(
        "AAPL",
        start=date(2026, 4, 1),
        end=date(2026, 4, 30),
        timeout=3.5,
    )

    assert "s=aapl.us" in str(seen["url"])
    assert "d1=20260401" in str(seen["url"])
    assert "d2=20260430" in str(seen["url"])
    assert seen["timeout"] == 3.5
    assert seen["headers"]["user-agent"] == "alpha-trade-cross-check/0.1"
    assert bars[0]["close"] == 10.5


def test_fetch_daily_bars_returns_empty_list_on_network_error(monkeypatch) -> None:
    monkeypatch.setattr(
        stooq_client.request,
        "urlopen",
        lambda req, timeout: (_ for _ in ()).throw(error.URLError("down")),
    )

    assert stooq_client.fetch_daily_bars("AAPL") == []


def test_risk_audit_build_run_id_and_persist_records() -> None:
    repo = _FakeRiskRepository()
    entries = [_portfolio_entry("AAPL", 10), _portfolio_entry("MSFT", 0, decision="REJECTED")]
    run_id = audit.build_run_id()

    decision_count = audit.persist_decisions(repo, entries, run_id, date(2026, 4, 29), account_id="acct-1")
    target_count = audit.persist_portfolio_targets(repo, entries, run_id, date(2026, 4, 29), account_id="acct-1")

    assert len(run_id) == 16
    int(run_id, 16)
    assert decision_count == 2
    assert target_count == 1
    assert repo.decisions_calls[0][1] == "acct-1"
    assert repo.targets_calls[0][1] == "acct-1"
    assert repo.decisions_calls[0][0][0]["symbol"] == "AAPL"
    assert repo.decisions_calls[0][0][1]["decision"] == "REJECTED"
    assert repo.targets_calls[0][0] == [
        {
            "run_id": run_id,
            "trade_date": date(2026, 4, 29),
            "symbol": "AAPL",
            "shares": 10,
            "entry_price": 123.4,
            "atr_20": 4.2,
            "target_weight": 0.15,
            "sector": "TECH",
            "score_used": 0.91,
            "score_source": "final_score_sentiment",
            "conviction_score": 0.88,
            "sizing_method": "atr",
            "kelly_fraction": 0.12,
            "company_idio_score": 0.45,
            "macro_regime_score": 0.32,
            "company_idio_signal_norm": 0.22,
            "macro_regime_signal_norm": 0.18,
            "company_idio_component": 0.14,
            "macro_regime_component": 0.11,
            "quant_component": 0.63,
            "walk_forward_sentiment_weight": 0.15,
            "walk_forward_macro_weight": 0.1,
            "walk_forward_quant_weight": 0.75,
            "calibration_run_id": "cal-1",
            "calibration_source": "walk_forward",
            "candidate_rank": 1,
            "selector_signal_mode": None,
            "selection_explanation": None,
            "selector_earnings_blackout": None,
            "decision_rank": 2,
            "target_notional": 1234.0,
            "stop_price_initial": 118.0,
            "risk_per_share": 5.4,
            "risk_budget_dollars": 540.0,
            "initial_risk_dollars": 540.0,
            "price_asof_date": date(2026, 4, 28),
            "atr_asof_date": date(2026, 4, 28),
        }
    ]


def test_core_eligibility_reexports_database_assets_contract() -> None:
    assert eligibility.ELIGIBLE_HISTORY_STATUSES == assets.ELIGIBLE_HISTORY_STATUSES
    assert eligibility.HISTORY_STATUS_READY == assets.HISTORY_STATUS_READY
    assert eligibility.build_eligible_stock_metadata_filters is assets.build_eligible_stock_metadata_filters



"""T-EOD-6 - EodhdCorporateActionProvider (plan §5.8 Phase 6)."""
from __future__ import annotations

from datetime import date

import pytest

from corporate_actions.models import CaType
from corporate_actions import provider as ca_provider
from service.eodhd import accounts as eodhd_accounts
from service.eodhd import quota as eodhd_quota


@pytest.fixture(autouse=True)
def _eodhd_env(monkeypatch, tmp_path):
    monkeypatch.setenv("EODHD_API_TOKEN", "TEST")
    monkeypatch.delenv("CORPORATE_ACTIONS_PROVIDER", raising=False)
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()
    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path)
    monkeypatch.setattr(eodhd_quota, "_DEFAULT_TRACKER", tracker, raising=False)
    yield tracker
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()


# ---------------------------------------------------------------------------
# parse_split_ratio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ratio, expected",
    [
        ("10/1", (1, 10)),
        ("10.000000/1.000000", (1, 10)),  # format réel EODHD
        ("4/1", (1, 4)),
        ("3/2", (2, 3)),
        ("1/2", (2, 1)),  # reverse
    ],
)
def test_parse_split_ratio(ratio, expected):
    assert ca_provider.EodhdCorporateActionProvider._parse_split_ratio(ratio) == expected


@pytest.mark.parametrize("bad", ["", "abc", "10", "1/0", "0/1", "-1/2"])
def test_parse_split_ratio_invalid(bad):
    with pytest.raises(ValueError):
        ca_provider.EodhdCorporateActionProvider._parse_split_ratio(bad)


# ---------------------------------------------------------------------------
# _parse_dividend / _parse_split
# ---------------------------------------------------------------------------


def test_parse_dividend_full_payload():
    raw = {
        "date": "2026-02-15",
        "value": 0.24,
        "unadjustedValue": 0.24,
        "currency": "USD",
        "declarationDate": "2026-01-30",
        "recordDate": "2026-02-16",
        "paymentDate": "2026-02-20",
    }
    ev = ca_provider.EodhdCorporateActionProvider._parse_dividend("AAPL", raw)
    assert ev.provider == "eodhd"
    assert ev.symbol == "AAPL"
    assert ev.ca_type == CaType.CASH_DIVIDEND
    assert ev.amount_per_share == pytest.approx(0.24)
    assert ev.currency == "USD"
    assert ev.ex_date == date(2026, 2, 15)
    assert ev.record_date == date(2026, 2, 16)
    assert ev.payable_date == date(2026, 2, 20)
    assert ev.announcement_date == date(2026, 1, 30)
    assert ev.provider_event_id == "eodhd-div-AAPL-2026-02-15"


def test_parse_dividend_optional_dates_missing():
    raw = {"date": "2026-02-15", "value": 1.0}
    ev = ca_provider.EodhdCorporateActionProvider._parse_dividend("AAPL", raw)
    assert ev.record_date is None
    assert ev.payable_date is None
    assert ev.announcement_date is None
    assert ev.currency == "USD"


def test_parse_split_forward_10_for_1_real_eodhd_format():
    raw = {"date": "2024-06-10", "split": "10.000000/1.000000"}
    ev = ca_provider.EodhdCorporateActionProvider._parse_split("NVDA", raw)
    assert ev.ca_type == CaType.SPLIT
    assert (ev.split_from, ev.split_to) == (1, 10)
    assert ev.ex_date == date(2024, 6, 10)
    assert ev.provider == "eodhd"


def test_parse_split_reverse_classified():
    raw = {"date": "2025-01-15", "split": "1/2"}
    ev = ca_provider.EodhdCorporateActionProvider._parse_split("XYZ", raw)
    assert ev.ca_type == CaType.REVERSE_SPLIT
    assert (ev.split_from, ev.split_to) == (2, 1)


def test_parse_dividend_missing_date_raises():
    with pytest.raises(ValueError):
        ca_provider.EodhdCorporateActionProvider._parse_dividend("AAPL", {"value": 1.0})


def test_parse_split_missing_ratio_raises():
    with pytest.raises(ValueError):
        ca_provider.EodhdCorporateActionProvider._parse_split("AAPL", {"date": "2024-06-10"})


# ---------------------------------------------------------------------------
# fetch_events (intégration mockée)
# ---------------------------------------------------------------------------


def test_fetch_events_combines_dividends_and_splits(monkeypatch):
    div_payload = [
        {"date": "2026-02-15", "value": 0.24, "currency": "USD"},
        {"date": "2025-11-15", "value": 0.23, "currency": "USD"},
    ]
    split_payload = [
        {"date": "2024-06-10", "split": "10.000000/1.000000"},
    ]
    monkeypatch.setattr(
        "service.eodhd.clientEodhd.fetch_dividends",
        lambda symbol, **kwargs: div_payload,
    )
    monkeypatch.setattr(
        "service.eodhd.clientEodhd.fetch_splits",
        lambda symbol, **kwargs: split_payload,
    )

    p = ca_provider.EodhdCorporateActionProvider()
    events = p.fetch_events(["NVDA"], date(2020, 1, 1), date(2026, 4, 30))

    assert len(events) == 3
    kinds = [e.ca_type for e in events]
    assert kinds.count(CaType.CASH_DIVIDEND) == 2
    assert kinds.count(CaType.SPLIT) == 1
    assert all(e.symbol == "NVDA" for e in events)
    assert all(e.provider == "eodhd" for e in events)


def test_fetch_events_none_symbols_raises():
    p = ca_provider.EodhdCorporateActionProvider()
    with pytest.raises(ValueError, match="liste explicite"):
        p.fetch_events(None)


def test_fetch_events_swallows_per_symbol_error_and_continues(monkeypatch):
    """Si dividends KO, splits doivent quand même être tentés."""
    from service.eodhd.clientEodhd import EodhdBarsFetchError

    def _div_boom(symbol, **kwargs):
        raise EodhdBarsFetchError("HTTP 500 dividends")

    monkeypatch.setattr("service.eodhd.clientEodhd.fetch_dividends", _div_boom)
    monkeypatch.setattr(
        "service.eodhd.clientEodhd.fetch_splits",
        lambda symbol, **kwargs: [{"date": "2024-06-10", "split": "10/1"}],
    )

    p = ca_provider.EodhdCorporateActionProvider()
    events = p.fetch_events(["NVDA"])
    assert len(events) == 1
    assert events[0].ca_type == CaType.SPLIT


def test_fetch_events_skips_invalid_payload_entries(monkeypatch):
    monkeypatch.setattr(
        "service.eodhd.clientEodhd.fetch_dividends",
        lambda symbol, **kwargs: [
            "not-a-dict",
            {"value": 1.0},  # pas de date -> parse_dividend lèvera, ignoré
            {"date": "2026-02-15", "value": 0.24},  # OK
        ],
    )
    monkeypatch.setattr("service.eodhd.clientEodhd.fetch_splits", lambda symbol, **kwargs: [])

    events = ca_provider.EodhdCorporateActionProvider().fetch_events(["AAPL"])
    assert len(events) == 1
    assert events[0].ex_date == date(2026, 2, 15)


# ---------------------------------------------------------------------------
# build_corporate_action_provider (factory)
# ---------------------------------------------------------------------------


def test_factory_default_returns_alpaca(monkeypatch):
    """Défaut bars_provider=alpaca -> AlpacaCorporateActionProvider."""
    monkeypatch.delenv("CORPORATE_ACTIONS_PROVIDER", raising=False)
    monkeypatch.setattr(
        "service.alpaca.clientAlpaca.get_alpaca_credentials",
        lambda account_id=None: ("KEY", "SECRET"),
    )
    p = ca_provider.build_corporate_action_provider(config={"market_data": {"bars_provider": "alpaca"}})
    assert isinstance(p, ca_provider.AlpacaCorporateActionProvider)


def test_factory_returns_eodhd_when_configured(monkeypatch):
    monkeypatch.delenv("CORPORATE_ACTIONS_PROVIDER", raising=False)
    p = ca_provider.build_corporate_action_provider(config={"market_data": {"bars_provider": "eodhd"}})
    assert isinstance(p, ca_provider.EodhdCorporateActionProvider)


def test_factory_env_var_overrides_config(monkeypatch):
    monkeypatch.setenv("CORPORATE_ACTIONS_PROVIDER", "eodhd")
    p = ca_provider.build_corporate_action_provider(config={"market_data": {"bars_provider": "alpaca"}})
    assert isinstance(p, ca_provider.EodhdCorporateActionProvider)


def test_factory_missing_config_falls_back_to_alpaca(monkeypatch):
    monkeypatch.delenv("CORPORATE_ACTIONS_PROVIDER", raising=False)

    def _boom():
        raise RuntimeError("config indispo")
    import common.config_loader as cl
    monkeypatch.setattr(cl, "load_config", _boom)
    monkeypatch.setattr(
        "service.alpaca.clientAlpaca.get_alpaca_credentials",
        lambda account_id=None: ("KEY", "SECRET"),
    )
    p = ca_provider.build_corporate_action_provider(config=None)
    assert isinstance(p, ca_provider.AlpacaCorporateActionProvider)


"""Tests pour la restitution IHM du régime marché.

Couvre :

* lecture du dernier snapshot persisté ;
* bannière neutre quand aucun snapshot n'existe ;
* bannière complète avec mode défensif → ``st.error`` ;
* présence du composant dans Overview / Execution / Risk.
* sérialisation robuste de ``MarketRegimeSnapshot`` côté page dédiée.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Stubs Streamlit minimaux pour exécuter render() hors runtime Streamlit.
# ---------------------------------------------------------------------------


class _FakeColumn:
    def metric(self, *args, **kwargs): return None


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name):
        def _fn(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return None
        return _fn

    def __getattr__(self, name):
        # default: noop recording
        return self._record(name)

    def columns(self, n):
        if isinstance(n, list):
            n = len(n)
        return [_FakeColumn() for _ in range(int(n))]


@pytest.fixture()
def fake_streamlit(monkeypatch):
    fake = _FakeStreamlit()
    import ihm.components.market_regime_banner as mod
    monkeypatch.setattr(mod, "st", fake)
    return fake


# ---------------------------------------------------------------------------
# load_latest_snapshot
# ---------------------------------------------------------------------------


def test_load_latest_snapshot_returns_none_when_dir_missing(tmp_path):
    from ihm.components.market_regime_banner import load_latest_snapshot
    assert load_latest_snapshot(tmp_path / "missing") is None


def test_load_latest_snapshot_returns_most_recent(tmp_path):
    from ihm.components.market_regime_banner import load_latest_snapshot
    (tmp_path / "snapshot_20250101T000000_acc.json").write_text(
        json.dumps({"trade_date": "2025-01-01", "mode": "normal"}), encoding="utf-8"
    )
    (tmp_path / "snapshot_20250115T123000_acc.json").write_text(
        json.dumps({"trade_date": "2025-01-15", "mode": "capital_preservation"}), encoding="utf-8"
    )
    snap = load_latest_snapshot(tmp_path)
    assert snap is not None
    assert snap["mode"] == "capital_preservation"


def test_load_latest_snapshot_skips_invalid_json(tmp_path):
    from ihm.components.market_regime_banner import load_latest_snapshot
    (tmp_path / "snapshot_20250115T120000_acc.json").write_text("not-json", encoding="utf-8")
    (tmp_path / "snapshot_20250114T120000_acc.json").write_text(
        json.dumps({"trade_date": "2025-01-14", "mode": "normal"}), encoding="utf-8"
    )
    snap = load_latest_snapshot(tmp_path)
    assert snap is not None
    assert snap["trade_date"] == "2025-01-14"


# ---------------------------------------------------------------------------
# render_market_regime_banner
# ---------------------------------------------------------------------------


def test_banner_renders_neutral_caption_when_no_snapshot(fake_streamlit, monkeypatch):
    from ihm.components import market_regime_banner as mod
    monkeypatch.setattr(mod, "load_latest_snapshot", lambda directory=None: None)
    out = mod.render_market_regime_banner()
    assert out is None
    captions = [c for c in fake_streamlit.calls if c[0] == "caption"]
    assert any("aucun snapshot" in str(c[1][0]).lower() for c in captions)


def test_banner_uses_error_for_close_only(fake_streamlit):
    from ihm.components.market_regime_banner import render_market_regime_banner
    snap = {
        "trade_date": "2025-04-15",
        "mode": "close_only",
        "risk_multiplier": 0.5,
        "effective_max_positions": 4,
        "allowed_slots": 4,
        "allow_new_entries": False,
    }
    render_market_regime_banner(snapshot=snap, compact=True, show_link_hint=False)
    error_calls = [c for c in fake_streamlit.calls if c[0] == "error"]
    assert error_calls, "Mode close_only doit déclencher st.error"
    headline = str(error_calls[0][1][0])
    assert "close_only" in headline
    assert "🛑" in headline


def test_banner_full_mode_shows_macro_and_patterns(fake_streamlit):
    from ihm.components.market_regime_banner import render_market_regime_banner
    snap = {
        "trade_date": "2025-04-15",
        "mode": "capital_preservation",
        "risk_multiplier": 0.7,
        "effective_max_positions": 6,
        "allowed_slots": 8,
        "allow_new_entries": True,
        "active_patterns": ["tax_day", "opex"],
        "blocked_sectors": ["Technology"],
        "macro": {"vix": 27.5, "yield_10y_5d_pct": 0.06},
        "reasons": ["VIX>25"],
    }
    render_market_regime_banner(snapshot=snap, compact=False, show_link_hint=False)
    warnings = [c for c in fake_streamlit.calls if c[0] == "warning"]
    assert warnings, "Mode capital_preservation → st.warning"
    captions = [str(c[1][0]) for c in fake_streamlit.calls if c[0] == "caption"]
    assert any("Patterns actifs" in s for s in captions)
    assert any("Secteurs bloqués" in s for s in captions)
    assert any("VIX>25" in s for s in captions)


# ---------------------------------------------------------------------------
# Intégration pages
# ---------------------------------------------------------------------------


def test_overview_imports_banner_component():
    src = Path("ihm/pages/overview.py").read_text(encoding="utf-8")
    assert "market_regime_banner" in src


def test_execution_imports_banner_component():
    src = Path("ihm/pages/execution.py").read_text(encoding="utf-8")
    assert "market_regime_banner" in src


def test_risk_imports_banner_component():
    src = Path("ihm/pages/risk.py").read_text(encoding="utf-8")
    assert "market_regime_banner" in src


def test_market_regime_snapshot_exposes_to_dict_alias():
    from service.market.models import MarketRegimeSnapshot

    snap = MarketRegimeSnapshot(trade_date=date(2025, 4, 15), mode="capital_preservation")
    payload = snap.to_dict()

    assert payload["trade_date"] == "2025-04-15"
    assert payload["mode"] == "capital_preservation"
    assert isinstance(payload["active_patterns"], list)


def test_compute_live_snapshot_serializes_slots_dataclass(monkeypatch):
    import ihm.pages.market_regime as mod
    import service.market as market
    from service.market.models import MarketRegimeSnapshot

    monkeypatch.setattr(mod, "_load_yaml", lambda: {"market_regimes": {"enabled": True}})
    monkeypatch.setattr(market, "parse_market_regimes", lambda cfg: object())
    monkeypatch.setattr(market, "build_default_macro_provider", lambda cfg: None)
    monkeypatch.setattr(
        market,
        "build_snapshot",
        lambda *args, **kwargs: MarketRegimeSnapshot(
            trade_date=date(2025, 4, 15),
            mode="capital_preservation",
            risk_multiplier=0.7,
            active_patterns=("tax_day",),
            blocked_sectors=("Technology",),
            macro={"vix": 28.0},
        ),
    )

    result = mod._compute_live_snapshot(date(2025, 4, 15), 2000.0)

    assert result["trade_date"] == "2025-04-15"
    assert result["mode"] == "capital_preservation"
    assert result["risk_multiplier"] == pytest.approx(0.7)
    assert result["active_patterns"] == ["tax_day"]
    assert result["blocked_sectors"] == ["Technology"]
    assert result["macro"] == {"vix": 28.0}



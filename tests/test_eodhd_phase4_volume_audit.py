"""Tests unitaires des calculs go/no-go Phase 4 (sans DB)."""
from __future__ import annotations

from datetime import date

import pytest

from scripts import eodhd_phase4_volume_audit as audit


@pytest.fixture
def sample_pairs():
    """20 jours sur 3 symboles : ratio EODHD/Alpaca = 25 (cible plan)."""
    pairs = []
    for sym, close in (("AAPL", 192.0), ("NVDA", 165.0), ("META", 510.0)):
        for d in range(1, 21):
            pairs.append({
                "symbol": sym,
                "date": date(2026, 4, d),
                "vol_alpaca": 2_000_000.0,
                "vol_eodhd": 50_000_000.0,
                "close_alpaca": close,
                "close_eodhd": close,
            })
    return pairs


def test_compute_volume_ratios_skips_zero_alpaca(sample_pairs):
    sample_pairs.append({
        "symbol": "BAD", "date": date(2026, 4, 21),
        "vol_alpaca": 0, "vol_eodhd": 1000,
        "close_alpaca": 1, "close_eodhd": 1,
    })
    ratios = audit.compute_volume_ratios(sample_pairs)
    assert len(ratios) == 60
    assert all(r["ratio"] == pytest.approx(25.0) for r in ratios)


def test_aggregate_by_symbol_median_p25_p75(sample_pairs):
    ratios = audit.compute_volume_ratios(sample_pairs)
    agg = audit.aggregate_by_symbol(ratios)
    assert set(agg.keys()) == {"AAPL", "NVDA", "META"}
    for stats in agg.values():
        assert stats["median_ratio"] == pytest.approx(25.0)
        assert stats["n_days"] == 20


def test_assess_go_no_go_pass_when_ratio_in_band(sample_pairs):
    ratios = audit.compute_volume_ratios(sample_pairs)
    by_symbol = audit.aggregate_by_symbol(ratios)
    avg_a = audit.compute_avg_dollar_volume_20d(sample_pairs, "alpaca")
    avg_e = audit.compute_avg_dollar_volume_20d(sample_pairs, "eodhd")
    market_caps = {"AAPL": 3e12, "NVDA": 2e12, "META": 1.3e12}
    decision = audit.assess_go_no_go(by_symbol, market_caps, avg_a, avg_e)
    assert decision["decision"] == "GO"
    assert decision["ratio_in_band"] is True
    assert audit.RATIO_MIN_OK <= decision["median_ratio_global"] <= audit.RATIO_MAX_OK
    assert decision["no_large_cap_lost"] is True


def test_assess_go_no_go_fails_when_ratio_below_band():
    pairs = [{
        "symbol": "AAPL", "date": date(2026, 4, d),
        "vol_alpaca": 1_000_000, "vol_eodhd": 2_000_000,  # ratio = 2 < 10
        "close_alpaca": 192.0, "close_eodhd": 192.0,
    } for d in range(1, 11)]
    ratios = audit.compute_volume_ratios(pairs)
    by_symbol = audit.aggregate_by_symbol(ratios)
    decision = audit.assess_go_no_go(
        by_symbol, {"AAPL": 3e12},
        audit.compute_avg_dollar_volume_20d(pairs, "alpaca"),
        audit.compute_avg_dollar_volume_20d(pairs, "eodhd"),
    )
    assert decision["decision"] == "NO-GO"
    assert decision["ratio_in_band"] is False


def test_assess_go_no_go_fails_when_large_cap_lost_not_recovered():
    pairs = [{
        "symbol": "AAPL", "date": date(2026, 4, d),
        "vol_alpaca": 100_000, "vol_eodhd": 3_000_000,
        "close_alpaca": 100.0, "close_eodhd": 100.0,
    } for d in range(1, 21)]
    pairs += [{
        "symbol": "BIGCO", "date": date(2026, 4, d),
        "vol_alpaca": 100, "vol_eodhd": 200,
        "close_alpaca": 1000.0, "close_eodhd": 1000.0,
    } for d in range(1, 21)]

    ratios = audit.compute_volume_ratios(pairs)
    by_symbol = audit.aggregate_by_symbol(ratios)
    avg_a = audit.compute_avg_dollar_volume_20d(pairs, "alpaca")
    avg_e = audit.compute_avg_dollar_volume_20d(pairs, "eodhd")
    decision = audit.assess_go_no_go(
        by_symbol, {"AAPL": 3e12, "BIGCO": 5e10}, avg_a, avg_e
    )
    assert "BIGCO" in decision["large_caps_rejected_by_alpaca"]
    assert "BIGCO" not in decision["large_caps_recovered_by_eodhd"]
    assert decision["no_large_cap_lost"] is False
    assert decision["decision"] == "NO-GO"


def test_resolve_symbols_sp100_default_returns_known_symbols():
    syms = audit._resolve_symbols(None, "sp100")
    assert "AAPL" in syms and "NVDA" in syms and "BRK.B" in syms
    assert len(syms) >= 95


def test_resolve_symbols_explicit_uppercases():
    assert audit._resolve_symbols(["aapl", "nvda"], "sp100") == ["AAPL", "NVDA"]


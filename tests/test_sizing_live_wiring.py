"""Tests P2-1 — branchement du sizing live (common.sizing + RiskConfig + builder)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from backtesting.risk_overlay import SizingConfig as BTSizingConfig
from common.sizing import SizingConfig
from risk_management.config import RiskConfig
from risk_management.models import EnrichedSelection
from risk_management.portfolio_builder import compute_allocation_factors


def _enriched(symbol: str, sector: str, rank: int | None, conviction: float = 1.0) -> EnrichedSelection:
    return EnrichedSelection(
        symbol=symbol,
        sector=sector,
        score_used=1.0,
        score_source="test",
        predicted_proba=0.5,
        historical_win_rate=0.5,
        conviction_score=conviction,
        selection_rank=rank,
    )


def test_common_sizing_is_reused_by_backtesting_risk_overlay():
    assert BTSizingConfig is SizingConfig


def test_sizing_config_rank_weighted_shared():
    cfg = SizingConfig(mode="rank_weighted", min_weight_pct=0.0, max_weight_pct=1.0)
    df = pd.DataFrame(
        {
            "symbol": ["A", "B", "C"],
            "selection_rank": [1, 2, 3],
        }
    ).set_index("symbol")
    weights = cfg.compute_weights(df, max_positions=3)
    assert weights["A"] > weights["B"] > weights["C"]
    assert weights.sum() == pytest.approx(1.0)


def test_risk_config_build_sizing_config_atr_returns_none():
    assert RiskConfig().build_sizing_config() is None


def test_risk_config_build_sizing_config_unknown_mode_returns_none():
    assert RiskConfig(sizing_mode="banane").build_sizing_config() is None


def test_risk_config_build_sizing_config_loads_multipliers(tmp_path: Path):
    payload = {"Retail": 1.25, "Health Care": 0.5}
    json_path = tmp_path / "mult.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    cfg = RiskConfig.from_yaml_section(
        {"sizing_mode": "rank_weighted", "sector_multipliers_path": str(json_path)},
    )
    sizing = cfg.build_sizing_config()
    assert sizing is not None
    assert sizing.mode == "rank_weighted"
    assert sizing.sector_multipliers == payload


def test_risk_config_build_sizing_config_bad_path_ignores_multipliers(tmp_path: Path):
    cfg = RiskConfig.from_yaml_section(
        {
            "sizing_mode": "rank_weighted",
            "sector_multipliers_path": str(tmp_path / "absent.json"),
        },
    )
    sizing = cfg.build_sizing_config()
    assert sizing is not None
    assert sizing.mode == "rank_weighted"
    assert sizing.sector_multipliers is None


def test_compute_allocation_factors_empty():
    assert compute_allocation_factors([], SizingConfig(), max_positions=10) == {}


def test_compute_allocation_factors_rank_and_sector():
    sizing = SizingConfig(
        mode="rank_weighted",
        min_weight_pct=0.0,
        max_weight_pct=1.0,
        sector_multipliers={"Health Care": 0.5, "Retail": 2.0},
    )
    retained = [
        _enriched("A", "Retail", 1),
        _enriched("B", "Health Care", 2),
        _enriched("C", "Other", 3),
    ]
    factors = compute_allocation_factors(retained, sizing, max_positions=3)
    # Base (3+1-rang) : A=3/6, B=2/6, C=1/6 ; facteurs 2.0/0.5/1.0
    # → A=1.0, B=1/6, C=1/6 ; somme = 4/3 → normalisé
    assert factors["A"] == pytest.approx(0.75)
    assert factors["B"] == pytest.approx(0.125)
    assert factors["C"] == pytest.approx(0.125)


def test_compute_allocation_factors_conviction_mode():
    sizing = SizingConfig(mode="conviction_weighted", min_weight_pct=0.0, max_weight_pct=1.0)
    retained = [
        _enriched("A", "X", 1, conviction=3.0),
        _enriched("B", "X", 2, conviction=1.0),
    ]
    factors = compute_allocation_factors(retained, sizing, max_positions=5)
    assert factors["A"] == pytest.approx(0.75)
    assert factors["B"] == pytest.approx(0.25)


def test_compute_allocation_factors_missing_ranks_fallback_equal():
    sizing = SizingConfig(mode="rank_weighted", min_weight_pct=0.0, max_weight_pct=1.0)
    retained = [
        _enriched("A", "X", None),
        _enriched("B", "X", None),
    ]
    factors = compute_allocation_factors(retained, sizing, max_positions=10)
    assert factors["A"] == pytest.approx(0.1)
    assert factors["B"] == pytest.approx(0.1)

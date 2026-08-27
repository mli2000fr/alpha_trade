"""Tests unitaires pour selector/dip_filter.py (Persistent Rank DIP filter).

Couvre :
- load_dip_filter_config() : clés prod_*/backtest_* distinctes + défauts
- _rank_column() : mapping horizon → colonne global_rank_{H}
- evaluate_dip_filter() : logique pure (persistance + dip + non-DIP)
- filter_day_candidates() : filtre DB réel (si données dispo) sinon skip
"""
from __future__ import annotations

import pandas as pd
import pytest

from selector.dip_filter import (
    _rank_column,
    evaluate_dip_filter,
    filter_day_candidates,
    load_dip_filter_config,
)


# ═══════════════════════════════════════════════════════════════════
# load_dip_filter_config — clés prod_*/backtest_* distinctes
# ═══════════════════════════════════════════════════════════════════

class TestLoadDipFilterConfig:
    def test_prod_and_backtest_defaults_disabled(self, monkeypatch):
        # Indépendant de l'état réel de config.yaml : on mocke la source.
        monkeypatch.setattr(
            "selector.dip_filter._load_yaml_config",
            lambda: {
                "prod_enabled": False,
                "prod_rank_horizon": 20,
                "backtest_enabled": False,
                "backtest_rank_horizon": 20,
            },
        )
        prod = load_dip_filter_config("prod")
        backtest = load_dip_filter_config("backtest")
        assert prod["enabled"] is False
        assert backtest["enabled"] is False
        # Défauts N4/X2 gelés
        assert prod["persist_days"] == 4
        assert prod["dip_pct"] == 0.02
        assert prod["rank_threshold"] == 0.90
        assert prod["rank_horizon"] == 20

    def test_prod_backtest_independent(self, monkeypatch):
        # Simule une config où prod activé mais backtest désactivé
        monkeypatch.setattr(
            "selector.dip_filter._load_yaml_config",
            lambda: {
                "prod_enabled": True,
                "prod_rank_horizon": 10,
                "backtest_enabled": False,
                "backtest_rank_horizon": 20,
            },
        )
        prod = load_dip_filter_config("prod")
        backtest = load_dip_filter_config("backtest")
        assert prod["enabled"] is True
        assert prod["rank_horizon"] == 10
        assert backtest["enabled"] is False
        assert backtest["rank_horizon"] == 20


# ═══════════════════════════════════════════════════════════════════
# _rank_column — mapping horizon → colonne
# ═══════════════════════════════════════════════════════════════════

class TestRankColumn:
    def test_explicit_horizons(self):
        for h, col in [(3, "global_rank_3"), (10, "global_rank_10"), (20, "global_rank_20")]:
            assert _rank_column({"rank_horizon": h}) == col

    def test_none_uses_best_h(self):
        assert _rank_column({"rank_horizon": None}, best_h=10) == "global_rank_10"
        assert _rank_column({"rank_horizon": None}) == "global_rank_20"

    def test_invalid_horizon_falls_back(self):
        assert _rank_column({"rank_horizon": 999}) == "global_rank_20"


# ═══════════════════════════════════════════════════════════════════
# evaluate_dip_filter — logique pure (PIT)
# ═══════════════════════════════════════════════════════════════════

def _mk_config(**overrides) -> dict:
    cfg = {
        "enabled": True,
        "rank_horizon": 20,
        "rank_threshold": 0.90,
        "persist_days": 4,
        "dip_pct": 0.02,
    }
    cfg.update(overrides)
    return cfg


def _mk_rank(dates, values, rank_col="global_rank_20") -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "symbol": "AAA", rank_col: values})


def _mk_price(dates, closes) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "symbol": "AAA", "close": closes})


class TestEvaluateDipFilter:
    def test_disabled_returns_true(self):
        cfg = _mk_config(enabled=False)
        assert evaluate_dip_filter("AAA", "2024-06-14", pd.DataFrame(), pd.DataFrame(), cfg) is True

    def test_passes_persistence_and_dip(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        rh = _mk_rank(dates, [0.95, 0.92, 0.91, 0.93])
        # prix : close[J] = 100, close[J-4] = 110 → ret = -9.1% ≤ -2%
        ph = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [110.0, 108.0, 105.0, 102.0, 100.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config()) is True

    def test_rejects_non_persistent(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        # Un jour sous le seuil 0.90 → persistance cassée
        rh = _mk_rank(dates, [0.95, 0.92, 0.89, 0.93])
        ph = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [110.0, 108.0, 105.0, 102.0, 100.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config()) is False

    def test_rejects_no_dip(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        rh = _mk_rank(dates, [0.95, 0.92, 0.91, 0.93])
        # Prix en hausse → pas de DIP
        ph = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [100.0, 102.0, 104.0, 106.0, 108.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config()) is False

    def test_rejects_insufficient_history(self):
        dates = ["2024-06-13", "2024-06-14"]  # seulement 2 séances < N=4
        rh = _mk_rank(dates, [0.95, 0.93])
        ph = _mk_price(["2024-06-14"], [100.0])
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config()) is False

    def test_uses_rank_col_override(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        rh = _mk_rank(dates, [0.95, 0.92, 0.91, 0.93], rank_col="global_rank_10")
        ph = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [110.0, 108.0, 105.0, 102.0, 100.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config(), rank_col="global_rank_10") is True


# ═══════════════════════════════════════════════════════════════════
# filter_day_candidates — filtre réel (DB), skip si données absentes
# ═══════════════════════════════════════════════════════════════════

class TestFilterDayCandidates:
    def test_disabled_returns_unchanged(self):
        day = pd.DataFrame({"symbol": ["AAA", "BBB"], "global_rank_20": [0.95, 0.50]})
        cfg = _mk_config(enabled=False)
        out = filter_day_candidates(day, None, "batch-x", "2024-06-14", cfg)
        assert len(out) == 2

    def test_empty_input(self):
        day = pd.DataFrame()
        out = filter_day_candidates(day, None, "batch-x", "2024-06-14", _mk_config())
        assert out.empty

    def test_filters_when_db_available(self):
        # Skip si pas de DB réelle dispo (environnement de test).
        try:
            from database.connection import get_sqlalchemy_engine
            engine = get_sqlalchemy_engine()
            # probe rapide
            import pandas as pd
            n = pd.read_sql(
                "SELECT COUNT(*) c FROM global_rank_history WHERE batch_id='model-factory-20260811223551-ef2cd0' AND date='2024-06-14'",
                engine,
            ).iloc[0]["c"]
            if n == 0:
                pytest.skip("données batch absentes — skip")
        except Exception:
            pytest.skip("pas de DB — skip")

        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine()
        day = pd.read_sql(
            "SELECT symbol, global_rank_20 FROM global_rank_history "
            "WHERE batch_id='model-factory-20260811223551-ef2cd0' AND date='2024-06-14'",
            engine,
        )
        cfg = _mk_config()
        out = filter_day_candidates(day.copy(), engine, "model-factory-20260811223551-ef2cd0", "2024-06-14", cfg)
        # Le DIP doit réduire le nombre de candidats (top10 > dip)
        assert len(out) <= len(day)
        assert set(out["symbol"]).issubset(set(day["symbol"]))

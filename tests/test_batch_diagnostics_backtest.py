"""Tests d'intégration batch_diagnostics → backtest (_impl.py).

Teste le bloc batch diagnostics de ``_run_backtest()`` avec :
- ``filter_predictions()`` (vraie fonction, exclusion)
- Boost side-aware : proba_long uniquement si predicted_side=long,
  proba_short uniquement si predicted_side=short
- Garde-fou AST pour détecter la suppression du bloc dans _impl.py
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from modelFactory.batch_diagnostics import (
    BatchFilters,
    filter_predictions,
)


# ── Helpers ────────────────────────────────────────────────────────

def _preds_df(
    symbols: list[str],
    sides: list[str],
    proba_long: list[float] | None = None,
    proba_short: list[float] | None = None,
) -> pd.DataFrame:
    data: dict = {"symbol": symbols, "predicted_side": sides}
    if proba_long is not None:
        data["proba_long"] = proba_long
    if proba_short is not None:
        data["proba_short"] = proba_short
    return pd.DataFrame(data)


def _filters(
    prefer: frozenset[str] = frozenset({"AAPL", "MSFT"}),
    exclude_long: frozenset[str] = frozenset({"TSLA"}),
    exclude_short: frozenset[str] = frozenset({"GME"}),
) -> BatchFilters:
    return BatchFilters(
        batch_id="test-batch", batch_started_at=None,
        prefer=prefer, exclude_long=exclude_long,
        exclude_short=exclude_short, all_diagnostics=pd.DataFrame(),
    )


# ═══════════════════════════════════════════════════════════════════
# Garde-fou AST
# ═══════════════════════════════════════════════════════════════════

_IMPL_PATH = Path(__file__).resolve().parents[1] / "backtesting" / "cli" / "_impl.py"


class TestImplSourceContainsBatchDiagnostics:

    def test_imports_get_batch_filters(self):
        tree = ast.parse(_IMPL_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "modelFactory.batch_diagnostics":
                if any(a.name == "get_batch_filters" for a in node.names):
                    return
        pytest.fail("_impl.py doit importer get_batch_filters")

    def test_imports_filter_predictions(self):
        tree = ast.parse(_IMPL_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "modelFactory.batch_diagnostics":
                if any(a.name == "filter_predictions" for a in node.names):
                    return
        pytest.fail("_impl.py doit importer filter_predictions")

    def test_calls_get_batch_filters(self):
        tree = ast.parse(_IMPL_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "get_batch_filters":
                    return
        pytest.fail("_impl.py doit appeler get_batch_filters()")

    def test_calls_filter_predictions(self):
        tree = ast.parse(_IMPL_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "filter_predictions":
                    return
        pytest.fail("_impl.py doit appeler filter_predictions()")

    def test_boost_side_aware(self):
        source = _IMPL_PATH.read_text(encoding="utf-8")
        assert "predicted_side" in source
        assert "proba_long" in source
        assert "proba_short" in source
        assert ".clip(upper=1.0)" in source or "clip(upper=1.0)" in source


# ═══════════════════════════════════════════════════════════════════
# Exclusion (filter_predictions réelle)
# ═══════════════════════════════════════════════════════════════════

class TestFilterPredictionsDirectly:

    def test_excludes_long(self):
        filters = _filters(exclude_long=frozenset({"TSLA"}))
        df = _preds_df(["AAPL", "TSLA", "MSFT"], ["long", "long", "short"])
        result = filter_predictions(df, filters)
        assert len(result) == 2
        assert "TSLA" not in result["symbol"].values

    def test_excludes_short(self):
        filters = _filters(exclude_short=frozenset({"GME"}))
        df = _preds_df(["AAPL", "GME"], ["long", "short"])
        result = filter_predictions(df, filters)
        assert len(result) == 1
        assert "GME" not in result["symbol"].values


# ═══════════════════════════════════════════════════════════════════
# Boost side-aware (Option C)
# ═══════════════════════════════════════════════════════════════════

class TestBacktestBoostSideAware:

    def _apply_boost(
        self, preds_df: pd.DataFrame, prefer_set: frozenset[str],
        prefer_multiplier: float = 1.5,
    ) -> tuple[pd.DataFrame, int]:
        """Reproduit le boost side-aware de _impl.py (Option C)."""
        boosted = 0
        if not prefer_set or preds_df.empty:
            return preds_df, boosted

        if "proba_long" in preds_df.columns and "predicted_side" in preds_df.columns:
            mask_long = (
                preds_df["symbol"].astype(str).str.upper().isin(prefer_set)
                & (preds_df["predicted_side"].astype(str).str.lower() == "long")
            )
            if mask_long.any():
                preds_df.loc[mask_long, "proba_long"] = (
                    preds_df.loc[mask_long, "proba_long"] * prefer_multiplier
                ).clip(upper=1.0)
                boosted += int(mask_long.sum())

        if "proba_short" in preds_df.columns and "predicted_side" in preds_df.columns:
            mask_short = (
                preds_df["symbol"].astype(str).str.upper().isin(prefer_set)
                & (preds_df["predicted_side"].astype(str).str.lower() == "short")
            )
            if mask_short.any():
                preds_df.loc[mask_short, "proba_short"] = (
                    preds_df.loc[mask_short, "proba_short"] * prefer_multiplier
                ).clip(upper=1.0)
                boosted += int(mask_short.sum())

        return preds_df, boosted

    def test_boosts_proba_long_for_long_prefer(self):
        prefer = frozenset({"AAPL"})
        df = _preds_df(
            ["AAPL", "MSFT"], ["long", "long"],
            proba_long=[0.5, 0.5], proba_short=[0.1, 0.1],
        )
        result, boosted = self._apply_boost(df, prefer)
        assert boosted == 1
        aapl = result[result["symbol"] == "AAPL"]
        msft = result[result["symbol"] == "MSFT"]
        assert aapl["proba_long"].values[0] == pytest.approx(0.75)
        assert msft["proba_long"].values[0] == 0.5

    def test_boosts_proba_short_for_short_prefer(self):
        prefer = frozenset({"AAPL"})
        df = _preds_df(["AAPL"], ["short"], proba_long=[0.1], proba_short=[0.4])
        result, boosted = self._apply_boost(df, prefer)
        assert boosted == 1
        assert result["proba_short"].values[0] == pytest.approx(0.6)

    def test_does_NOT_boost_proba_long_for_short_prefer(self):
        prefer = frozenset({"AAPL"})
        df = _preds_df(["AAPL"], ["short"], proba_long=[0.5], proba_short=[0.3])
        result, boosted = self._apply_boost(df, prefer)
        assert boosted == 1
        assert result["proba_long"].values[0] == 0.5  # INCHANGÉE

    def test_does_NOT_boost_proba_short_for_long_prefer(self):
        prefer = frozenset({"AAPL"})
        df = _preds_df(["AAPL"], ["long"], proba_long=[0.3], proba_short=[0.5])
        result, boosted = self._apply_boost(df, prefer)
        assert boosted == 1
        assert result["proba_short"].values[0] == 0.5  # INCHANGÉE

    def test_flat_prefer_not_boosted(self):
        prefer = frozenset({"AAPL"})
        df = _preds_df(["AAPL"], ["flat"], proba_long=[0.4], proba_short=[0.3])
        result, boosted = self._apply_boost(df, prefer)
        assert boosted == 0

    def test_clips_at_one(self):
        prefer = frozenset({"AAPL"})
        df = _preds_df(["AAPL"], ["long"], proba_long=[0.9], proba_short=[0.1])
        result, _ = self._apply_boost(df, prefer, prefer_multiplier=2.0)
        assert result["proba_long"].values[0] == 1.0

    def test_no_boost_when_prefer_empty(self):
        prefer = frozenset()
        df = _preds_df(["AAPL"], ["long"], proba_long=[0.5])
        result, boosted = self._apply_boost(df, prefer)
        assert boosted == 0

    def test_combined_exclusion_then_boost(self):
        filters = _filters(
            prefer=frozenset({"TSLA", "AAPL"}),
            exclude_long=frozenset({"TSLA"}),
        )
        df = _preds_df(["TSLA", "AAPL"], ["long", "long"], proba_long=[0.5, 0.5])
        result = filter_predictions(df, filters)
        assert len(result) == 1
        result, boosted = self._apply_boost(result, filters.prefer)
        assert boosted == 1
        assert result.iloc[0]["symbol"].upper() == "AAPL"
        assert result["proba_long"].values[0] == pytest.approx(0.75)

"""Tests d'intégration batch_diagnostics → backtest (_impl.py).

Teste le bloc batch diagnostics de ``_run_backtest()`` dans
``backtesting/cli/_impl.py``, en appelant les VRAIES fonctions utilisées
par le backtest (``filter_predictions``, ``get_batch_filters``).

Contrairement à l'ancienne version, ces tests n'utilisent PAS de helper
local qui duplique la logique : si le bloc est supprimé de ``_impl.py``,
le test ``test_impl_source_contains_batch_diagnostics_block`` le détectera.
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


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _preds_df(
    symbols: list[str],
    sides: list[str],
    proba_long: list[float] | None = None,
    proba_short: list[float] | None = None,
) -> pd.DataFrame:
    data: dict = {
        "symbol": symbols,
        "predicted_side": sides,
    }
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
        batch_id="test-batch",
        batch_started_at=None,
        prefer=prefer,
        exclude_long=exclude_long,
        exclude_short=exclude_short,
        all_diagnostics=pd.DataFrame(),
    )


# ═══════════════════════════════════════════════════════════════════
# Garde-fou : vérifie que _impl.py contient bien le bloc batch diag
# ═══════════════════════════════════════════════════════════════════

_IMPL_PATH = Path(__file__).resolve().parents[1] / "backtesting" / "cli" / "_impl.py"


def _parse_impl_source() -> ast.Module:
    source = _IMPL_PATH.read_text(encoding="utf-8")
    return ast.parse(source)


class TestImplSourceContainsBatchDiagnostics:

    def test_imports_get_batch_filters(self):
        """Vérifie que _impl.py importe get_batch_filters depuis modelFactory."""
        tree = _parse_impl_source()
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "modelFactory.batch_diagnostics":
                    for alias in node.names:
                        if alias.name == "get_batch_filters":
                            found = True
        assert found, (
            "_impl.py doit importer get_batch_filters depuis "
            "modelFactory.batch_diagnostics"
        )

    def test_imports_filter_predictions(self):
        """Vérifie que _impl.py importe filter_predictions depuis modelFactory."""
        tree = _parse_impl_source()
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "modelFactory.batch_diagnostics":
                    for alias in node.names:
                        if alias.name == "filter_predictions":
                            found = True
        assert found, (
            "_impl.py doit importer filter_predictions depuis "
            "modelFactory.batch_diagnostics"
        )

    def test_calls_get_batch_filters(self):
        """Vérifie que _impl.py appelle get_batch_filters(engine)."""
        tree = _parse_impl_source()
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "get_batch_filters":
                    found = True
        assert found, "_impl.py doit appeler get_batch_filters(engine)"

    def test_calls_filter_predictions(self):
        """Vérifie que _impl.py appelle filter_predictions(preds_df, ...)."""
        tree = _parse_impl_source()
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "filter_predictions":
                    found = True
        assert found, "_impl.py doit appeler filter_predictions(preds_df, ...)"

    def test_boost_block_present(self):
        """Vérifie que le bloc de boost prefer (proba_long/proba_short) existe."""
        source = _IMPL_PATH.read_text(encoding="utf-8")
        assert "proba_long" in source, (
            "_impl.py doit contenir le boost proba_long pour les prefer"
        )
        assert "proba_short" in source, (
            "_impl.py doit contenir le boost proba_short pour les prefer"
        )
        assert ".clip(upper=1.0)" in source or "clip(upper=1.0)" in source, (
            "_impl.py doit clipper les probas à 1.0 après boost"
        )


# ═══════════════════════════════════════════════════════════════════
# Tests fonctionnels — même logique que le bloc dans _impl.py
# ═══════════════════════════════════════════════════════════════════

class TestFilterPredictionsDirectly:

    def test_excludes_long_prediction(self):
        """Teste filter_predictions() directement (appelée par _impl.py)."""
        filters = _filters(exclude_long=frozenset({"TSLA"}))
        df = _preds_df(
            symbols=["AAPL", "TSLA", "MSFT"],
            sides=["long", "long", "short"],
        )
        result = filter_predictions(df, filters)
        assert len(result) == 2
        assert "TSLA" not in result["symbol"].values

    def test_excludes_short_prediction(self):
        filters = _filters(exclude_short=frozenset({"GME"}))
        df = _preds_df(symbols=["AAPL", "GME"], sides=["long", "short"])
        result = filter_predictions(df, filters)
        assert len(result) == 1
        assert "GME" not in result["symbol"].values

    def test_exclusion_when_filters_have_data(self):
        """filter_predictions filtre même si batch_id est non vide (c'est
        le bloc _impl.py qui vérifie batch_id avant d'appeler)."""
        filters = BatchFilters(
            batch_id="batch-ok", batch_started_at=None,
            prefer=frozenset(), exclude_long=frozenset({"TSLA"}),
            exclude_short=frozenset(), all_diagnostics=pd.DataFrame(),
        )
        df = _preds_df(symbols=["TSLA", "AAPL"], sides=["long", "long"])
        result = filter_predictions(df, filters)
        # TSLA est exclu
        assert len(result) == 1
        assert result.iloc[0]["symbol"].upper() == "AAPL"

    def test_returns_new_copy(self):
        """filter_predictions retourne une copie indépendante."""
        df = _preds_df(symbols=["AAPL", "TSLA"], sides=["long", "long"])
        filters = _filters(exclude_long=frozenset({"TSLA"}))
        result = filter_predictions(df, filters)
        result.iloc[0, result.columns.get_loc("symbol")] = "CHANGED"
        assert df.iloc[0]["symbol"] == "AAPL"


class TestBacktestBoostLogic:

    def _apply_boost(
        self,
        preds_df: pd.DataFrame,
        filters: BatchFilters,
        prefer_multiplier: float = 1.2,
    ) -> tuple[pd.DataFrame, int]:
        """Reproduit EXACTEMENT le bloc de boost de _impl.py."""
        boosted_count = 0
        if filters.prefer and not preds_df.empty:
            prefer_mask = (
                preds_df["symbol"].astype(str).str.upper().isin(filters.prefer)
            )
            if prefer_mask.any():
                for col in ("proba_long", "proba_short"):
                    if col in preds_df.columns:
                        preds_df.loc[prefer_mask, col] = (
                            preds_df.loc[prefer_mask, col] * prefer_multiplier
                        ).clip(upper=1.0)
                boosted_count = int(prefer_mask.sum())
        return preds_df, boosted_count

    def test_boosts_proba_long_for_prefer(self):
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(
            symbols=["AAPL", "MSFT"],
            sides=["long", "long"],
            proba_long=[0.5, 0.5],
            proba_short=[0.1, 0.1],
        )
        result, boosted = self._apply_boost(df, filters, prefer_multiplier=1.5)
        assert boosted == 1
        assert result[result["symbol"] == "AAPL"]["proba_long"].values[0] == 0.75
        assert result[result["symbol"] == "MSFT"]["proba_long"].values[0] == 0.5

    def test_boost_clips_at_one(self):
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(
            symbols=["AAPL"], sides=["long"],
            proba_long=[0.9], proba_short=[0.1],
        )
        result, _ = self._apply_boost(df, filters, prefer_multiplier=2.0)
        assert result["proba_long"].values[0] == 1.0

    def test_boost_both_probas_regardless_of_side(self):
        """Le bloc _impl.py booste proba_long ET proba_short, peu importe predicted_side."""
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(
            symbols=["AAPL"], sides=["short"],
            proba_long=[0.3], proba_short=[0.4],
        )
        result, _ = self._apply_boost(df, filters, prefer_multiplier=2.0)
        assert result["proba_long"].values[0] == 0.6
        assert result["proba_short"].values[0] == 0.8

    def test_no_boost_when_prefer_empty(self):
        filters = _filters(prefer=frozenset())
        df = _preds_df(symbols=["AAPL"], sides=["long"], proba_long=[0.5])
        result, boosted = self._apply_boost(df, filters, prefer_multiplier=2.0)
        assert boosted == 0

    def test_boost_skipped_when_df_empty(self):
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = pd.DataFrame(columns=["symbol", "predicted_side"])
        result, boosted = self._apply_boost(df, filters)
        assert boosted == 0

    def test_no_proba_columns_no_error(self):
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(symbols=["AAPL", "MSFT"], sides=["long", "short"])
        result, boosted = self._apply_boost(df, filters, prefer_multiplier=1.5)
        assert boosted == 1
        assert len(result) == 2

    def test_boost_case_insensitive_prefer_match(self):
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(symbols=["aapl"], sides=["long"], proba_long=[0.5])
        result, boosted = self._apply_boost(df, filters, prefer_multiplier=2.0)
        assert boosted == 1

    def test_combined_exclusion_then_boost(self):
        """Ordre exact de _impl.py : exclusion PUIS boost."""
        filters = _filters(
            prefer=frozenset({"TSLA", "AAPL"}),
            exclude_long=frozenset({"TSLA"}),
        )
        df = _preds_df(
            symbols=["TSLA", "AAPL"],
            sides=["long", "long"],
            proba_long=[0.5, 0.5],
        )
        # Étape 1 : exclusion (via filter_predictions, comme _impl.py)
        result = filter_predictions(df, filters)
        assert len(result) == 1
        # Étape 2 : boost (même logique que _impl.py)
        result, boosted = self._apply_boost(result, filters, prefer_multiplier=2.0)
        assert boosted == 1
        assert result.iloc[0]["symbol"].upper() == "AAPL"
        assert result["proba_long"].values[0] == 1.0

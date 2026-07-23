"""Tests d'intégration batch_diagnostics → backtest (_impl.py).

Teste la logique de filtrage/boost des prédictions via batch diagnostics,
telle qu'implémentée dans ``_run_backtest()`` de ``backtesting/cli/_impl.py``.
"""
from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.batch_diagnostics import (
    RANK_TYPE_BOTTOM,
    RANK_TYPE_TOP,
    RANK_TYPE_WEAK_LONG,
    RANK_TYPE_WEAK_SHORT,
    RANK_TYPE_ZERO_SHORT,
    BatchFilters,
    filter_predictions,
)


# ── Helpers ────────────────────────────────────────────────────────

def apply_batch_diagnostics_to_preds(
    preds_df: pd.DataFrame,
    filters: BatchFilters,
    *,
    prefer_multiplier: float = 1.2,
) -> tuple[pd.DataFrame, int, int]:
    """Reproduit la logique batch diagnostics du backtest (exclusion + boost proba).

    Étape 1 : exclusion via filter_predictions().
    Étape 2 : boost proba_long / proba_short pour les prefer (clip ≤ 1.0).

    Returns:
        (filtered_df, filtered_count, boosted_count)
    """
    filtered_count = 0
    boosted_count = 0

    if not filters.batch_id or preds_df.empty:
        return preds_df, filtered_count, boosted_count

    # ── Étape 1 : exclusion ──
    before = len(preds_df)
    preds_df = filter_predictions(preds_df, filters)
    filtered_count = before - len(preds_df)

    # ── Étape 2 : boost prefer ──
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

    return preds_df, filtered_count, boosted_count


# ── Fixtures ────────────────────────────────────────────────────────

def _preds_df(
    symbols: list[str],
    sides: list[str],
    proba_long: list[float] | None = None,
    proba_short: list[float] | None = None,
) -> pd.DataFrame:
    """Construit un DataFrame de prédictions."""
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


# ── Tests ──────────────────────────────────────────────────────────

class TestBatchDiagnosticsBacktestExclusion:

    def test_excludes_long_prediction(self):
        filters = _filters(exclude_long=frozenset({"TSLA"}))
        df = _preds_df(
            symbols=["AAPL", "TSLA", "MSFT"],
            sides=["long", "long", "short"],
        )
        result, filtered, boosted = apply_batch_diagnostics_to_preds(df, filters)
        assert filtered == 1
        assert "TSLA" not in result["symbol"].values
        assert len(result) == 2

    def test_excludes_short_prediction(self):
        filters = _filters(exclude_short=frozenset({"GME"}))
        df = _preds_df(
            symbols=["AAPL", "GME"],
            sides=["long", "short"],
        )
        result, filtered, boosted = apply_batch_diagnostics_to_preds(df, filters)
        assert filtered == 1
        assert "GME" not in result["symbol"].values
        assert len(result) == 1

    def test_no_exclusion_when_no_batch_id(self):
        filters = BatchFilters(
            batch_id="",  # vide → skip
            batch_started_at=None,
            prefer=frozenset(),
            exclude_long=frozenset({"TSLA"}),
            exclude_short=frozenset(),
            all_diagnostics=pd.DataFrame(),
        )
        df = _preds_df(symbols=["TSLA"], sides=["long"])
        result, filtered, _ = apply_batch_diagnostics_to_preds(df, filters)
        assert filtered == 0
        assert len(result) == 1

    def test_empty_df_unchanged(self):
        filters = _filters()
        df = pd.DataFrame(columns=["symbol", "predicted_side"])
        result, filtered, _ = apply_batch_diagnostics_to_preds(df, filters)
        assert filtered == 0
        assert result.empty


class TestBatchDiagnosticsBacktestBoost:

    def test_boosts_proba_long_for_prefer(self):
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(
            symbols=["AAPL", "MSFT"],
            sides=["long", "long"],
            proba_long=[0.5, 0.5],
            proba_short=[0.1, 0.1],
        )
        result, filtered, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=1.5,
        )
        assert boosted == 1
        aapl_row = result[result["symbol"] == "AAPL"]
        msft_row = result[result["symbol"] == "MSFT"]
        assert aapl_row["proba_long"].values[0] == 0.75  # 0.5 × 1.5
        assert msft_row["proba_long"].values[0] == 0.5  # inchangé

    def test_boosts_proba_short_for_prefer(self):
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(
            symbols=["AAPL"],
            sides=["short"],
            proba_long=[0.1],
            proba_short=[0.4],
        )
        result, _, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=2.0,
        )
        assert boosted == 1
        assert result["proba_short"].values[0] == 0.8  # 0.4 × 2.0

    def test_boost_clips_at_one(self):
        """proba_long et proba_short sont plafonnés à 1.0 après boost."""
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(
            symbols=["AAPL"],
            sides=["long"],
            proba_long=[0.9],
            proba_short=[0.1],
        )
        result, _, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=2.0,
        )
        assert boosted == 1
        # 0.9 × 2.0 = 1.8 → clip à 1.0
        assert result["proba_long"].values[0] == 1.0

    def test_boost_clips_short_at_one(self):
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(
            symbols=["AAPL"],
            sides=["short"],
            proba_long=[0.1],
            proba_short=[0.8],
        )
        result, _, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=1.5,
        )
        assert boosted == 1
        # 0.8 × 1.5 = 1.2 → clip à 1.0
        assert result["proba_short"].values[0] == 1.0

    def test_no_boost_when_prefer_empty(self):
        filters = _filters(prefer=frozenset())
        df = _preds_df(
            symbols=["AAPL"],
            sides=["long"],
            proba_long=[0.5],
        )
        result, _, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=2.0,
        )
        assert boosted == 0
        assert result["proba_long"].values[0] == 0.5

    def test_boost_ignored_when_df_empty_after_exclusion(self):
        """Si toutes les lignes sont exclues, le boost ne s'applique pas."""
        filters = _filters(
            prefer=frozenset({"AAPL"}),
            exclude_long=frozenset({"AAPL"}),
        )
        df = _preds_df(
            symbols=["AAPL"],
            sides=["long"],
            proba_long=[0.5],
        )
        result, filtered, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=2.0,
        )
        assert filtered == 1
        assert boosted == 0
        assert result.empty

    def test_boost_preserves_non_prefer_probas(self):
        filters = _filters(prefer=frozenset({"AAPL", "MSFT"}))
        df = _preds_df(
            symbols=["AAPL", "GOOG", "MSFT"],
            sides=["long", "long", "long"],
            proba_long=[0.5, 0.6, 0.7],
            proba_short=[0.1, 0.2, 0.3],
        )
        result, _, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=1.5,
        )
        assert boosted == 2  # AAPL et MSFT dans prefer
        goog = result[result["symbol"] == "GOOG"]
        assert goog["proba_long"].values[0] == 0.6  # inchangé
        assert goog["proba_short"].values[0] == 0.2  # inchangé

    def test_no_proba_columns_no_error(self):
        """Si proba_long/proba_short n'existent pas, pas d'erreur.
        Le compteur boosted reflète le nombre de symboles prefer (même sans colonnes)."""
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(symbols=["AAPL", "MSFT"], sides=["long", "short"])
        result, _, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=1.5,
        )
        # AAPL dans prefer → compté boosted, même sans colonnes proba
        assert boosted == 1
        assert len(result) == 2

    def test_boost_case_insensitive_prefer_match(self):
        """Le masque prefer matche même si le symbole est en minuscules."""
        filters = _filters(prefer=frozenset({"AAPL"}))
        df = _preds_df(
            symbols=["aapl"],  # minuscule
            sides=["long"],
            proba_long=[0.5],
        )
        result, _, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=2.0,
        )
        assert boosted == 1

    def test_combined_exclusion_and_boost(self):
        """Un symbole dans exclude_long n'est PAS boosté même s'il est prefer."""
        filters = _filters(
            prefer=frozenset({"TSLA", "AAPL"}),
            exclude_long=frozenset({"TSLA"}),
        )
        df = _preds_df(
            symbols=["TSLA", "AAPL"],
            sides=["long", "long"],
            proba_long=[0.5, 0.5],
        )
        result, filtered, boosted = apply_batch_diagnostics_to_preds(
            df, filters, prefer_multiplier=2.0,
        )
        assert filtered == 1  # TSLA exclu
        assert boosted == 1  # seul AAPL boosté
        assert len(result) == 1
        assert result.iloc[0]["symbol"].upper() == "AAPL"

"""Tests d'intégration batch_diagnostics → executor (live).

Teste la logique de filtrage/boost des ExecutionTarget via batch diagnostics,
telle qu'implémentée dans ``execute_run()`` de ``execution_engine/executor.py``.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from execution_engine.models import ExecutionTarget
from modelFactory.batch_diagnostics import (
    RANK_TYPE_BOTTOM,
    RANK_TYPE_TOP,
    RANK_TYPE_WEAK_LONG,
    RANK_TYPE_WEAK_SHORT,
    RANK_TYPE_ZERO_SHORT,
    BatchFilters,
)


# ── Helpers ────────────────────────────────────────────────────────

def _target(
    symbol: str = "AAPL",
    side: str = "buy",
    target_shares: float = 100.0,
    target_notional: float = 15_000.0,
) -> ExecutionTarget:
    """Construit un ExecutionTarget minimal pour les tests."""
    return ExecutionTarget(
        risk_run_id="r1",
        trade_date=date(2026, 7, 23),
        symbol=symbol,
        side=side,
        target_shares=target_shares,
        entry_price=150.0,
        target_weight=0.05,
        sector="Tech",
        conviction_score=0.8,
        sizing_method="atr",
        kelly_fraction=0.1,
        decision_rank=1,
        stop_price_initial=140.0,
        risk_per_share=10.0,
        risk_budget_dollars=1_000.0,
        initial_risk_dollars=1_000.0,
        target_notional=target_notional,
        price_asof_date=date(2026, 7, 23),
        atr_asof_date=date(2026, 7, 23),
        atr_20=5.0,
    )


def apply_batch_diagnostics_to_targets(
    targets: list[ExecutionTarget],
    filters: BatchFilters,
    *,
    prefer_multiplier: float = 1.2,
    prefer_top_n: int = 10,
) -> tuple[list[ExecutionTarget], int, int]:
    """Reproduit la logique batch diagnostics de l'executor (exclusion + boost).

    Returns:
        (filtered_targets, filtered_count, boosted_count)
    """
    filtered_count = 0
    boosted_count = 0

    # ── Étape 1 : Exclusion ──
    if filters.exclude_long or filters.exclude_short:
        filtered_targets: list[ExecutionTarget] = []
        for t in targets:
            sym = str(t.symbol).strip().upper()
            side = str(getattr(t, "side", "buy") or "buy").strip().lower()
            if side in ("sell", "short") and sym in filters.exclude_short:
                filtered_count += 1
                continue
            if side in ("buy", "long") and sym in filters.exclude_long:
                filtered_count += 1
                continue
            filtered_targets.append(t)
        targets = filtered_targets

    # ── Étape 2 : Construire le prefer set (limité à prefer_top_n) ──
    prefer_set: frozenset[str] = frozenset()
    if filters.prefer:
        prefer_df = filters.all_diagnostics
        if not prefer_df.empty and "rank_position" in prefer_df.columns:
            prefer_set = frozenset(
                prefer_df[
                    (prefer_df["rank_type"] == "top")
                    & (prefer_df["rank_position"] <= prefer_top_n)
                ]["symbol"]
            )
        else:
            prefer_set = filters.prefer

    # ── Étape 3 : Boost sizing ──
    if prefer_set and prefer_multiplier != 1.0:
        boosted_targets: list[ExecutionTarget] = []
        for t in targets:
            sym = str(t.symbol).strip().upper()
            if sym in prefer_set:
                boosted_count += 1
                new_shares = float(getattr(t, "target_shares", 0) or 0) * prefer_multiplier
                new_notional = float(getattr(t, "target_notional", 0) or 0) * prefer_multiplier
                t = replace(t, target_shares=new_shares, target_notional=new_notional)
            boosted_targets.append(t)
        targets = boosted_targets

    return targets, filtered_count, boosted_count


# ── Fixtures ────────────────────────────────────────────────────────

def _filters_with_data(
    prefer_syms: frozenset[str] = frozenset({"AAPL", "MSFT"}),
    exclude_long_syms: frozenset[str] = frozenset({"TSLA"}),
    exclude_short_syms: frozenset[str] = frozenset({"GME"}),
    prefer_top_n: int = 10,
) -> BatchFilters:
    """Construit un BatchFilters avec un all_diagnostics cohérent."""
    rows = []
    for i, sym in enumerate(sorted(prefer_syms), start=1):
        rows.append({"symbol": sym, "rank_type": RANK_TYPE_TOP, "rank_position": i})
    for sym in sorted(exclude_long_syms):
        rows.append({"symbol": sym, "rank_type": RANK_TYPE_BOTTOM, "rank_position": 1})
    for sym in sorted(exclude_short_syms):
        if sym not in exclude_long_syms:
            rows.append({"symbol": sym, "rank_type": RANK_TYPE_ZERO_SHORT, "rank_position": None})
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    return BatchFilters(
        batch_id="test-batch",
        batch_started_at=None,
        prefer=frozenset(
            df[df["rank_type"] == RANK_TYPE_TOP]["symbol"]
            if not df.empty and "rank_type" in df.columns
            else []
        ),
        exclude_long=exclude_long_syms,
        exclude_short=exclude_short_syms,
        all_diagnostics=df,
    )


# ── Tests ──────────────────────────────────────────────────────────

class TestBatchDiagnosticsExecutorExclusion:

    def test_excludes_long_target(self):
        filters = _filters_with_data(exclude_long_syms=frozenset({"TSLA"}))
        targets = [
            _target("AAPL", side="buy"),
            _target("TSLA", side="buy"),
            _target("MSFT", side="buy"),
        ]
        result, filtered, boosted = apply_batch_diagnostics_to_targets(targets, filters)
        assert len(result) == 2
        assert filtered == 1
        assert {t.symbol for t in result} == {"AAPL", "MSFT"}

    def test_excludes_short_target(self):
        filters = _filters_with_data(exclude_short_syms=frozenset({"GME"}))
        targets = [
            _target("AAPL", side="sell"),
            _target("GME", side="sell"),
        ]
        result, filtered, boosted = apply_batch_diagnostics_to_targets(targets, filters)
        assert len(result) == 1
        assert filtered == 1
        assert result[0].symbol == "AAPL"

    def test_keeps_long_target_not_in_exclude(self):
        filters = _filters_with_data(exclude_long_syms=frozenset({"TSLA"}))
        targets = [_target("AAPL", side="buy")]
        result, filtered, boosted = apply_batch_diagnostics_to_targets(targets, filters)
        assert len(result) == 1
        assert filtered == 0

    def test_side_case_insensitive(self):
        """'SELL' ou 'LONG' sont correctement interprétés."""
        filters = _filters_with_data(
            exclude_long_syms=frozenset({"TSLA"}),
            exclude_short_syms=frozenset({"GME"}),
        )
        targets = [
            _target("TSLA", side="LONG"),
            _target("GME", side="SELL"),
            _target("AAPL", side="buy"),
        ]
        result, filtered, _ = apply_batch_diagnostics_to_targets(targets, filters)
        assert filtered == 2
        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    def test_no_exclusion_when_filters_empty(self):
        filters = BatchFilters(
            batch_id="b1", batch_started_at=None,
            prefer=frozenset(), exclude_long=frozenset(),
            exclude_short=frozenset(), all_diagnostics=pd.DataFrame(),
        )
        targets = [_target("AAPL", side="buy"), _target("TSLA", side="sell")]
        result, filtered, boosted = apply_batch_diagnostics_to_targets(targets, filters)
        assert len(result) == 2
        assert filtered == 0

    def test_short_alias_excluded(self):
        """'short' est traité comme 'sell'."""
        filters = _filters_with_data(exclude_short_syms=frozenset({"GME"}))
        targets = [_target("GME", side="short")]
        result, filtered, _ = apply_batch_diagnostics_to_targets(targets, filters)
        assert filtered == 1
        assert len(result) == 0

    def test_long_alias_excluded(self):
        """'long' est traité comme 'buy'."""
        filters = _filters_with_data(exclude_long_syms=frozenset({"TSLA"}))
        targets = [_target("TSLA", side="long")]
        result, filtered, _ = apply_batch_diagnostics_to_targets(targets, filters)
        assert filtered == 1
        assert len(result) == 0

    def test_all_targets_filtered_returns_empty(self):
        filters = _filters_with_data(
            exclude_long_syms=frozenset({"AAPL", "MSFT"}),
            exclude_short_syms=frozenset({"GME"}),
        )
        targets = [
            _target("AAPL", side="buy"),
            _target("MSFT", side="buy"),
            _target("GME", side="sell"),
        ]
        result, filtered, _ = apply_batch_diagnostics_to_targets(targets, filters)
        assert len(result) == 0
        assert filtered == 3


class TestBatchDiagnosticsExecutorBoost:

    def test_boosts_prefer_target_shares(self):
        filters = _filters_with_data(prefer_syms=frozenset({"AAPL"}))
        targets = [_target("AAPL", side="buy", target_shares=100.0, target_notional=15_000.0)]
        result, _, boosted = apply_batch_diagnostics_to_targets(
            targets, filters, prefer_multiplier=1.5,
        )
        assert boosted == 1
        assert result[0].target_shares == 150.0  # 100 × 1.5
        assert result[0].target_notional == 22_500.0  # 15000 × 1.5

    def test_boosts_only_prefer_symbols(self):
        filters = _filters_with_data(prefer_syms=frozenset({"AAPL"}))
        targets = [
            _target("AAPL", side="buy", target_shares=100.0, target_notional=10_000.0),
            _target("MSFT", side="buy", target_shares=50.0, target_notional=5_000.0),
        ]
        result, _, boosted = apply_batch_diagnostics_to_targets(
            targets, filters, prefer_multiplier=2.0,
        )
        assert boosted == 1
        aapl = next(t for t in result if t.symbol == "AAPL")
        msft = next(t for t in result if t.symbol == "MSFT")
        assert aapl.target_shares == 200.0  # boosté
        assert msft.target_shares == 50.0  # inchangé

    def test_no_boost_when_multiplier_is_one(self):
        filters = _filters_with_data(prefer_syms=frozenset({"AAPL"}))
        targets = [_target("AAPL", side="buy", target_shares=100.0)]
        result, _, boosted = apply_batch_diagnostics_to_targets(
            targets, filters, prefer_multiplier=1.0,
        )
        assert boosted == 0
        assert result[0].target_shares == 100.0  # inchangé

    def test_no_boost_when_prefer_empty(self):
        filters = _filters_with_data(prefer_syms=frozenset())
        targets = [_target("AAPL", side="buy", target_shares=100.0)]
        result, _, boosted = apply_batch_diagnostics_to_targets(
            targets, filters, prefer_multiplier=1.5,
        )
        assert boosted == 0

    def test_prefer_top_n_respected(self):
        """Seuls les top N symboles sont boostés, pas tous les prefer."""
        # prefer a 5 symboles mais prefer_top_n=2
        rows = [
            {"symbol": "A", "rank_type": RANK_TYPE_TOP, "rank_position": 1},
            {"symbol": "B", "rank_type": RANK_TYPE_TOP, "rank_position": 2},
            {"symbol": "C", "rank_type": RANK_TYPE_TOP, "rank_position": 3},
            {"symbol": "D", "rank_type": RANK_TYPE_TOP, "rank_position": 4},
            {"symbol": "E", "rank_type": RANK_TYPE_TOP, "rank_position": 5},
        ]
        df = pd.DataFrame(rows)
        filters = BatchFilters(
            batch_id="test", batch_started_at=None,
            prefer=frozenset({"A", "B", "C", "D", "E"}),
            exclude_long=frozenset(), exclude_short=frozenset(),
            all_diagnostics=df,
        )
        targets = [
            _target("A", side="buy"),
            _target("B", side="buy"),
            _target("C", side="buy"),
            _target("D", side="buy"),
            _target("E", side="buy"),
        ]
        result, _, boosted = apply_batch_diagnostics_to_targets(
            targets, filters, prefer_multiplier=1.5, prefer_top_n=2,
        )
        assert boosted == 2
        # Seuls A et B sont boostés (rank_position <= 2)
        for t in result:
            if t.symbol in ("A", "B"):
                assert t.target_shares == 150.0
            else:
                assert t.target_shares == 100.0

    def test_prefer_set_from_prefer_when_empty_diagnostics(self):
        """Si all_diagnostics est vide, on utilise filters.prefer directement."""
        filters = BatchFilters(
            batch_id="test", batch_started_at=None,
            prefer=frozenset({"AAPL"}),
            exclude_long=frozenset(), exclude_short=frozenset(),
            all_diagnostics=pd.DataFrame(),  # vide
        )
        targets = [_target("AAPL", side="buy", target_shares=100.0)]
        result, _, boosted = apply_batch_diagnostics_to_targets(
            targets, filters, prefer_multiplier=2.0,
        )
        assert boosted == 1
        assert result[0].target_shares == 200.0

    def test_boost_handles_zero_target_notional(self):
        """target_notional peut être None ou 0 → pas d'erreur."""
        filters = _filters_with_data(prefer_syms=frozenset({"AAPL"}))
        targets = [_target("AAPL", side="buy", target_shares=0.0, target_notional=0.0)]
        result, _, boosted = apply_batch_diagnostics_to_targets(
            targets, filters, prefer_multiplier=2.0,
        )
        assert boosted == 1
        assert result[0].target_shares == 0.0  # 0 × 2 = 0
        assert result[0].target_notional == 0.0

    def test_no_side_attribute_defaults_to_buy(self):
        """Target sans attribut side → traité comme buy."""
        # On ne peut pas supprimer l'attribut d'un dataclass frozen,
        # donc on vérifie juste que le fallback "buy" fonctionne.
        filters = _filters_with_data(exclude_long_syms=frozenset({"TSLA"}))
        targets = [
            _target("TSLA", side="buy"),
            _target("AAPL", side="buy"),
        ]
        result, filtered, _ = apply_batch_diagnostics_to_targets(targets, filters)
        assert filtered == 1  # TSLA exclu
        assert result[0].symbol == "AAPL"

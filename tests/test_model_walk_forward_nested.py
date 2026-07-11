"""Tests pour le walk-forward et la validation statistique — Sprint Maître 7."""

from __future__ import annotations

import numpy as np
import pytest

from backtesting.statistical_validation import (
    WalkForwardPlan,
    block_bootstrap_sharpe,
    compute_promotion_score,
    deflated_sharpe_ratio,
    multiple_testing_correction,
)


# ── WalkForwardPlan ─────────────────────────────────────────────────────────

def test_walk_forward_plan_construction() -> None:
    plan = WalkForwardPlan(
        train_start="2020-01-01", train_end="2022-12-31",
        val_start="2023-01-01", val_end="2023-06-30",
        test_start="2023-07-01", test_end="2023-12-31",
        purge_days=5, embargo_days=10, fold_index=0,
    )
    assert plan.fold_index == 0
    assert plan.purge_days == 5
    d = plan.to_dict()
    assert d["train_start"] == "2020-01-01"


def test_walk_forward_plan_purge_embargo_positive() -> None:
    """La purge et l'embargo doivent être ≥ 0."""
    plan = WalkForwardPlan(
        train_start="2020-01-01", train_end="2021-01-01",
        val_start="2021-01-02", val_end="2021-06-30",
        test_start="2021-07-01", test_end="2021-12-31",
        purge_days=0, embargo_days=0,
    )
    assert plan.purge_days >= 0
    assert plan.embargo_days >= 0


# ── Deflated Sharpe Ratio ───────────────────────────────────────────────────

def test_deflated_sharpe_positive_returns() -> None:
    """Des rendements positifs donnent un Sharpe > 0."""
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.01, 500)  # Sharpe ≈ 1.58
    result = deflated_sharpe_ratio(returns, n_trials=10)
    assert result.annual_sharpe > 0
    assert result.p_value >= 0.0


def test_deflated_sharpe_random_returns() -> None:
    """Des rendements aléatoires (mu≈0) donnent un Sharpe proche de 0."""
    np.random.seed(42)
    returns = np.random.normal(0.0, 0.01, 500)
    result = deflated_sharpe_ratio(returns, n_trials=100)
    # Le DSR corrigé doit être faible ou négatif
    assert result.deflated_sharpe < 2.0


def test_deflated_sharpe_insufficient_data() -> None:
    """Moins de 20 observations → pas de calcul."""
    result = deflated_sharpe_ratio(np.array([0.01, 0.02]), n_trials=10)
    assert result.annual_sharpe == 0.0
    assert result.p_value == 1.0
    assert result.is_significant is False


def test_deflated_sharpe_more_trials_harder() -> None:
    """Plus de trials → Deflated Sharpe plus faible."""
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.01, 500)
    r1 = deflated_sharpe_ratio(returns, n_trials=5)
    r2 = deflated_sharpe_ratio(returns, n_trials=100)
    assert r2.deflated_sharpe <= r1.deflated_sharpe


# ── Block Bootstrap Sharpe ──────────────────────────────────────────────────

def test_block_bootstrap_basic() -> None:
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.01, 252)
    result = block_bootstrap_sharpe(returns, n_iterations=200, block_size=10)
    assert "mean_sharpe" in result
    assert result["ci_low_sharpe"] <= result["mean_sharpe"] <= result["ci_high_sharpe"]


def test_block_bootstrap_insufficient_data() -> None:
    result = block_bootstrap_sharpe(np.array([0.01, 0.02, 0.03]), block_size=5)
    assert result["mean_sharpe"] == 0.0


# ── Multiple Testing Correction ─────────────────────────────────────────────

def test_bonferroni_correction() -> None:
    p_values = [0.01, 0.02, 0.05, 0.10]
    corrected = multiple_testing_correction(p_values, method="bonferroni")
    assert len(corrected) == 4
    # Bonferroni : p * n
    assert corrected[0] == pytest.approx(0.04)  # 0.01 * 4
    assert corrected[3] == pytest.approx(0.40)  # 0.10 * 4


def test_bh_correction() -> None:
    p_values = [0.01, 0.02, 0.05, 0.10]
    corrected = multiple_testing_correction(p_values, method="bh")
    assert len(corrected) == 4
    assert all(0.0 <= p <= 1.0 for p in corrected)


def test_multiple_testing_empty() -> None:
    assert multiple_testing_correction([]) == []


# ── Promotion Score ─────────────────────────────────────────────────────────

def test_promotion_score_excellent() -> None:
    result = compute_promotion_score(
        sharpe=2.0, sortino=2.5, calmar=3.0,
        max_drawdown_pct=10.0, profit_factor=2.0,
        win_rate=0.60, n_trades=500,
        cost_ratio=0.15, fold_stability=0.85,
    )
    assert result.total_score > 0.80
    assert result.is_promotable is True


def test_promotion_score_poor() -> None:
    result = compute_promotion_score(
        sharpe=0.5, sortino=0.5, calmar=0.5,
        max_drawdown_pct=30.0, profit_factor=1.05,
        win_rate=0.45, n_trades=50,
        cost_ratio=0.50, fold_stability=0.40,
    )
    assert result.total_score < 0.50
    assert result.is_promotable is False


def test_promotion_score_borderline() -> None:
    """Score proche de 0.60 = limite de promotion."""
    result = compute_promotion_score(
        sharpe=1.0, sortino=1.2, calmar=1.5,
        max_drawdown_pct=15.0, profit_factor=1.30,
        win_rate=0.55, n_trades=200,
        cost_ratio=0.25, fold_stability=0.70,
    )
    assert 0.40 < result.total_score < 0.85


def test_promotion_score_deflated_sharpe() -> None:
    """Le Deflated Sharpe remplace le Sharpe s'il est fourni."""
    r1 = compute_promotion_score(
        sharpe=2.0, sortino=2.0, calmar=2.0,
        max_drawdown_pct=10.0, profit_factor=1.5,
        win_rate=0.55, n_trades=200,
        cost_ratio=0.20, fold_stability=0.70,
    )
    r2 = compute_promotion_score(
        sharpe=2.0, sortino=2.0, calmar=2.0,
        max_drawdown_pct=10.0, profit_factor=1.5,
        win_rate=0.55, n_trades=200,
        cost_ratio=0.20, fold_stability=0.70,
        sharpe_deflated=0.5,  # faible
    )
    assert r2.total_score < r1.total_score


def test_promotion_score_to_dict() -> None:
    result = compute_promotion_score(
        sharpe=1.5, sortino=1.8, calmar=2.0,
        max_drawdown_pct=12.0, profit_factor=1.6,
        win_rate=0.58, n_trades=300,
        cost_ratio=0.18, fold_stability=0.75,
    )
    d = result.to_dict()
    assert "total_score" in d
    assert "is_promotable" in d
    assert all(0.0 <= d[k] <= 1.0 for k in ["sharpe_score", "drawdown_score", "profit_factor_score"])

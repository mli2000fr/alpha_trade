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


# ── Section 17 Point 7 : walk-forward engine integration ───────────────────

def test_walk_forward_config_defaults() -> None:
    """WalkForwardConfig a des valeurs par défaut raisonnables."""
    from backtesting.walk_forward_engine import WalkForwardConfig

    cfg = WalkForwardConfig()
    assert cfg.initial_equity == 100_000.0
    assert cfg.commission_bps == 1.0
    assert cfg.execution_model == "next_open"
    assert cfg.annual_factor == 252


def test_fold_financials_to_dict() -> None:
    """FoldFinancials se sérialise correctement."""
    import numpy as np
    from backtesting.walk_forward_engine import FoldFinancials

    f = FoldFinancials(
        fold_index=0,
        test_start="2025-01-01",
        test_end="2025-06-30",
        total_return_pct=12.5,
        sharpe_ratio=1.25,
        max_drawdown_pct=8.0,
        total_trades=45,
        win_rate_pct=55.0,
        profit_factor=1.5,
        long_trades=30,
        short_trades=15,
        daily_returns=np.array([0.001, -0.002, 0.003]),
        n_trading_days=126,
    )
    d = f.to_dict()
    assert d["fold_index"] == 0
    assert d["total_return_pct"] == 12.5
    assert d["sharpe_ratio"] == 1.25
    assert d["total_trades"] == 45
    assert d["long_trades"] == 30
    assert d["short_trades"] == 15


def test_walk_forward_result_empty() -> None:
    """WalkForwardResult sans folds a des valeurs par défaut à zéro."""
    from backtesting.walk_forward_engine import WalkForwardResult

    r = WalkForwardResult()
    assert r.n_folds == 0
    assert r.n_folds_positive == 0
    assert r.median_sharpe == 0.0
    assert not r.is_promotable


def test_walk_forward_result_to_dict() -> None:
    """WalkForwardResult se sérialise correctement avec folds."""
    import numpy as np
    from backtesting.walk_forward_engine import FoldFinancials, WalkForwardResult

    folds = [
        FoldFinancials(
            fold_index=i,
            test_start=f"2025-0{i+1}-01",
            test_end=f"2025-0{i+1}-30",
            total_return_pct=10.0 + i * 5,
            sharpe_ratio=1.0 + i * 0.2,
            daily_returns=np.array([0.001] * 10),
            total_trades=20 + i * 5,
            win_rate_pct=50.0 + i * 5,
            n_trading_days=21,
            profit_factor=1.3 + i * 0.1,
        )
        for i in range(3)
    ]
    r = WalkForwardResult(
        folds=folds,
        n_folds=3,
        n_folds_positive=3,
        median_sharpe=1.2,
        percentile_25_sharpe=1.0,
        median_return_pct=15.0,
        median_max_dd_pct=10.0,
        median_profit_factor=1.5,
        fold_stability_pct=100.0,
        avg_cost_ratio_pct=25.0,
        promotion_score=0.65,
        is_promotable=True,
        total_trades_all_folds=75,
    )
    d = r.to_dict()
    assert d["n_folds"] == 3
    assert d["n_folds_positive"] == 3
    assert d["is_promotable"] is True
    assert len(d["folds"]) == 3
    assert d["folds"][0]["fold_index"] == 0


def test_compute_equity_metrics_positive() -> None:
    """Des returns positifs produisent un Sharpe > 0."""
    import numpy as np
    from backtesting.walk_forward_engine import _compute_equity_metrics

    rets = np.array([0.001] * 252)  # ~28.5% annual
    m = _compute_equity_metrics(rets)
    assert m["total_return_pct"] > 20
    assert m["sharpe_ratio"] > 0  # tr Ès élevé car pas de variance
    assert m["max_drawdown_pct"] == 0.0
    assert m["n_trading_days"] == 252


def test_compute_equity_metrics_negative() -> None:
    """Des returns négatifs produisent un Sharpe < 0."""
    import numpy as np
    from backtesting.walk_forward_engine import _compute_equity_metrics

    rets = np.array([-0.002] * 252)
    m = _compute_equity_metrics(rets)
    assert m["total_return_pct"] < -30
    assert m["sharpe_ratio"] < 0
    assert m["max_drawdown_pct"] > 0


def test_compute_trade_metrics_mixed() -> None:
    """Métriques de trading sur une distribution mixte."""
    import pandas as pd
    from backtesting.walk_forward_engine import _compute_trade_metrics

    df = pd.DataFrame({
        "return_pct": [5.0, -2.0, 3.0, -1.0, 4.0],
        "bars_held": [5, 3, 7, 2, 4],
        "side": ["long", "short", "long", "long", "short"],
        "pnl": [500.0, -200.0, 300.0, -100.0, 400.0],
        "costs": [5.0, 5.0, 5.0, 5.0, 5.0],
    })
    m = _compute_trade_metrics(df, 100_000.0)
    assert m["total_trades"] == 5
    assert m["win_rate_pct"] == 60.0  # 3 sur 5 positifs
    assert m["profit_factor"] > 1.0
    assert m["long_trades"] == 3
    assert m["short_trades"] == 2
    assert m["total_costs"] == 25.0


def test_walk_forward_result_integration() -> None:
    """Test d'intégration : construction d'un WalkForwardResult complet
    avec métriques avancées (Deflated Sharpe, bootstrap, promotion)."""
    import numpy as np
    from backtesting.statistical_validation import compute_promotion_score, deflated_sharpe_ratio
    from backtesting.walk_forward_engine import FoldFinancials, WalkForwardResult

    # Simuler 5 folds avec des résultats plausibles
    np.random.seed(42)
    folds = []
    for i in range(5):
        # Générer des returns synthétiques réalistes
        daily_rets = np.random.normal(0.001, 0.015, size=60)
        folds.append(FoldFinancials(
            fold_index=i,
            test_start=f"2025-Q{i+1}",
            test_end=f"2025-Q{i+1}",
            total_return_pct=float(np.sum(daily_rets) * 100),
            sharpe_ratio=float(np.mean(daily_rets) / np.std(daily_rets) * np.sqrt(252)),
            sortino_ratio=float(np.mean(daily_rets) / max(np.std(daily_rets[daily_rets < 0]), 1e-9) * np.sqrt(252)),
            calmar_ratio=1.5,
            max_drawdown_pct=abs(float(np.min(np.cumprod(1 + daily_rets) / np.maximum.accumulate(np.cumprod(1 + daily_rets)) - 1))) * 100,
            total_trades=15 + i * 3,
            win_rate_pct=50.0 + i * 3,
            profit_factor=1.2 + i * 0.1,
            daily_returns=daily_rets,
            n_trading_days=60,
            long_trades=10 + i * 2,
            short_trades=5 + i,
            cost_ratio_pct=22.0,
        ))

    # Agréger
    all_rets = np.concatenate([f.daily_returns for f in folds])
    sharpes = [f.sharpe_ratio for f in folds]

    dsr = deflated_sharpe_ratio(all_rets, n_trials=100)

    promo = compute_promotion_score(
        sharpe=float(np.median(sharpes)),
        sortino=float(np.median([f.sortino_ratio for f in folds])),
        calmar=float(np.median([f.calmar_ratio for f in folds])),
        max_drawdown_pct=float(np.median([f.max_drawdown_pct for f in folds])),
        profit_factor=float(np.median([f.profit_factor for f in folds])),
        win_rate=float(np.mean([f.win_rate_pct for f in folds])),
        n_trades=sum(f.total_trades for f in folds),
        cost_ratio=float(np.mean([f.cost_ratio_pct for f in folds])),
        fold_stability=sum(1 for f in folds if f.total_return_pct > 0) / len(folds),
        sharpe_deflated=dsr.deflated_sharpe,
    )

    result = WalkForwardResult(
        folds=folds,
        n_folds=len(folds),
        n_folds_positive=sum(1 for f in folds if f.total_return_pct > 0),
        median_sharpe=float(np.median(sharpes)),
        percentile_25_sharpe=float(np.percentile(sharpes, 25)),
        median_return_pct=float(np.median([f.total_return_pct for f in folds])),
        median_max_dd_pct=float(np.median([f.max_drawdown_pct for f in folds])),
        median_profit_factor=float(np.median([f.profit_factor for f in folds])),
        fold_stability_pct=sum(1 for f in folds if f.total_return_pct > 0) / len(folds) * 100,
        avg_cost_ratio_pct=float(np.mean([f.cost_ratio_pct for f in folds])),
        combined_daily_returns=all_rets,
        total_trades_all_folds=sum(f.total_trades for f in folds),
        deflated_sharpe=dsr.deflated_sharpe,
        deflated_sharpe_pvalue=dsr.p_value,
        is_deflated_significant=dsr.is_significant,
        promotion_score=promo.total_score,
        is_promotable=promo.is_promotable,
    )

    # Vérifications
    assert result.n_folds == 5
    assert result.n_folds_positive >= 0
    assert result.total_trades_all_folds > 0
    d = result.to_dict()
    assert "folds" in d
    assert len(d["folds"]) == 5
    assert d["folds"][0]["fold_index"] == 0
    assert d["folds"][-1]["fold_index"] == 4
    assert d["deflated_sharpe"] is not None
    assert d["promotion_score"] is not None


# ── Section 17 Point 7-R2 : DataProvider DB ────────────────────────────────

def test_create_db_data_provider_filters_by_date_range() -> None:
    """Le DataProvider filtre correctement par plage de dates."""
    import pandas as pd
    from backtesting.walk_forward_engine import create_db_data_provider

    scores = pd.DataFrame({
        "trade_date": pd.date_range("2025-01-01", "2025-06-30", freq="D"),
        "symbol": ["AAPL"] * 181,
        "final_score": 0.5,
    })
    provider = create_db_data_provider(scores_df=scores)
    data = provider(pd.Timestamp("2025-03-01").date(), pd.Timestamp("2025-03-15").date())
    assert data["scores_df"] is not None
    assert len(data["scores_df"]) == 15


def test_create_db_data_provider_handles_missing_dataframes() -> None:
    """Le DataProvider gère les DataFrames None."""
    import pandas as pd
    from backtesting.walk_forward_engine import create_db_data_provider

    provider = create_db_data_provider(scores_df=pd.DataFrame())
    data = provider(pd.Timestamp("2025-01-01").date(), pd.Timestamp("2025-01-10").date())
    assert data["predictions_df"] is None  # non fourni
    assert data["close_df"] is None


# ── Section 17 Point 7-R3 : regime segmentation ────────────────────────────

def test_fold_financials_regime_metrics_serializable() -> None:
    """Les metrics par régime sont sérialisables dans to_dict."""
    from backtesting.walk_forward_engine import FoldFinancials

    f = FoldFinancials(
        fold_index=0,
        regime_metrics={
            "normal": {"sharpe": 1.5, "trades": 10, "win_rate": 60.0},
            "defensive": {"sharpe": -0.5, "trades": 2, "win_rate": 0.0},
        },
    )
    d = f.to_dict()
    assert "regime_metrics" in d
    assert d["regime_metrics"]["normal"]["sharpe"] == 1.5


# ── Section 17 Point 7-R4 : WalkForwardReport ──────────────────────────────

def test_walk_forward_report_to_dict() -> None:
    """WalkForwardReport produit un dict avec gates et résultat."""
    from backtesting.walk_forward_engine import WalkForwardReport, WalkForwardResult

    result = WalkForwardResult(
        n_folds=3,
        n_folds_positive=3,
        median_sharpe=1.2,
        percentile_25_sharpe=0.5,
        median_return_pct=15.0,
        median_max_dd_pct=10.0,
        median_profit_factor=1.5,
        fold_stability_pct=100.0,
        avg_cost_ratio_pct=20.0,
        deflated_sharpe=2.1,
        deflated_sharpe_pvalue=0.02,
        is_deflated_significant=True,
        promotion_score=0.75,
        is_promotable=True,
    )
    report = WalkForwardReport(
        result=result,
        config_fingerprint="abc123",
        generated_at="2026-07-12T00:00:00Z",
    )
    d = report.to_dict()
    assert d["engine_version"] == "1.0.0"
    assert d["config_fingerprint"] == "abc123"
    assert "gates" in d
    assert d["gates"]["sharpe_median_gate"]["passed"] is True
    assert d["gates"]["fold_stability_gate"]["passed"] is True
    assert d["gates"]["promotion_gate"]["passed"] is True


def test_walk_forward_report_gates_fail_when_below_threshold() -> None:
    """Les gates échouent quand les métriques sont sous les seuils."""
    from backtesting.walk_forward_engine import WalkForwardReport, WalkForwardResult

    result = WalkForwardResult(
        n_folds=5,
        n_folds_positive=2,
        median_sharpe=0.5,
        percentile_25_sharpe=-0.2,
        median_max_dd_pct=25.0,
        median_profit_factor=0.9,
        fold_stability_pct=40.0,
        avg_cost_ratio_pct=45.0,
        is_deflated_significant=False,
        is_promotable=False,
    )
    report = WalkForwardReport(result=result)
    gates = report._compute_gates()
    assert gates["sharpe_median_gate"]["passed"] is False
    assert gates["sharpe_p25_gate"]["passed"] is False
    assert gates["profit_factor_gate"]["passed"] is False
    assert gates["cost_ratio_gate"]["passed"] is False


def test_walk_forward_report_to_json(tmp_path) -> None:
    """Le rapport est persisté en JSON atomique."""
    import json
    from backtesting.walk_forward_engine import WalkForwardReport, WalkForwardResult

    result = WalkForwardResult(n_folds=1, n_folds_positive=1)
    report = WalkForwardReport(result=result, config_fingerprint="test")
    path = str(tmp_path / "report.json")
    report.to_json(path)
    with open(path) as f:
        data = json.load(f)
    assert data["config_fingerprint"] == "test"
    assert "gates" in data


def test_generate_walk_forward_report_with_output(tmp_path) -> None:
    """generate_walk_forward_report persiste si output_path fourni."""
    import os
    from backtesting.statistical_validation import WalkForwardPlan
    from backtesting.walk_forward_engine import WalkForwardResult, generate_walk_forward_report

    result = WalkForwardResult(n_folds=3, n_folds_positive=2)
    plans = [
        WalkForwardPlan(
            train_start="2025-01-01", train_end="2025-06-30",
            val_start="2025-07-01", val_end="2025-09-30",
            test_start="2025-10-01", test_end="2025-12-31",
            fold_index=i,
        )
        for i in range(3)
    ]
    path = str(tmp_path / "oos_report.json")
    report = generate_walk_forward_report(result, None, plans, output_path=path)
    assert os.path.exists(path)
    assert report.config_fingerprint == ""

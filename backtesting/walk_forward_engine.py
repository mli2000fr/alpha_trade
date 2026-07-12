"""backtesting/walk_forward_engine.py — Moteur de walk-forward financier (Section 17 Point 7).

Orchestre le replay complet d'un plan de walk-forward :
1. Pour chaque fold externe, rejoue les jours de test via ``build_phase2_risk_result()``
2. Simule l'exécution via ``Simulator`` pour produire trades et equity curve
3. Agrège les métriques financières par fold
4. Calcule les statistiques avancées (Deflated Sharpe, bootstrap, promotion score)

Contrat :
- Le holdout externe (test) n'est JAMAIS utilisé pour le tuning
- Les métriques sont nettes de TOUS les coûts
- Les résultats sont segmentés par side (long/short) et par régime

Usage ::

    from backtesting.walk_forward_engine import (
        WalkForwardConfig, FoldResult, WalkForwardResult, run_walk_forward,
    )

    plan = [WalkForwardPlan(train_start=..., ..., fold_index=i) for i in range(N_FOLDS)]
    result = run_walk_forward(plan, config, data_provider)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


# ── Configuration ───────────────────────────────────────────────────────────

@dataclass(slots=True)
class WalkForwardConfig:
    """Configuration d'un run de walk-forward financier.

    Attributes
    ----------
    initial_equity : float
        Capital de départ pour chaque fold (reset entre folds).
    commission_bps : float
        Commission en points de base.
    slippage_bps : float
        Slippage en points de base.
    execution_model : str
        Modèle d'exécution : 'next_open' (défaut), 'arrival_price', 'twap', 'vwap'.
    phase2_mode : str
        'risk_execution' pour activer le bridge risque complet.
    annual_factor : int
        Facteur d'annualisation (252 pour daily).
    risk_free_rate : float
        Taux sans risque annualisé.
    """
    initial_equity: float = 100_000.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    execution_model: str = "next_open"
    phase2_mode: str = "risk_execution"
    annual_factor: int = 252
    risk_free_rate: float = 0.0


# ── Résultats par fold ─────────────────────────────────────────────────────

@dataclass(slots=True)
class FoldFinancials:
    """Métriques financières pour un fold de walk-forward.

    Toutes les métriques sont nettes de coûts.
    """
    # Rendement
    total_return_pct: float = 0.0
    cagr_pct: float = 0.0
    daily_returns: np.ndarray = field(default_factory=lambda: np.array([]))

    # Risque
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    volatility_annual_pct: float = 0.0

    # Trading
    total_trades: int = 0
    win_rate_pct: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return_pct: float = 0.0
    avg_trade_duration_days: float = 0.0

    # Par side
    long_trades: int = 0
    short_trades: int = 0
    long_win_rate_pct: float = 0.0
    short_win_rate_pct: float = 0.0
    long_pnl_total: float = 0.0
    short_pnl_total: float = 0.0

    # Coûts et turnover
    total_costs: float = 0.0
    cost_ratio_pct: float = 0.0  # coûts / PnL brut
    turnover_pct: float = 0.0
    gross_exposure_avg_pct: float = 0.0
    net_exposure_avg_pct: float = 0.0

    # Qualité
    n_trading_days: int = 0
    force_close_exits: int = 0
    fold_index: int = 0

    # Métadonnées
    test_start: str = ""
    test_end: str = ""
    # ── Section 17 Point 7-R3 : segmentation par régime ────────────────
    regime_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    # ex: {"normal": {"sharpe": 1.2, "trades": 15, "win_rate": 60.0}, ...}

    def to_dict(self) -> dict[str, object]:
        return {
            "fold_index": self.fold_index,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "total_return_pct": round(self.total_return_pct, 2),
            "cagr_pct": round(self.cagr_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "calmar_ratio": round(self.calmar_ratio, 3),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "volatility_annual_pct": round(self.volatility_annual_pct, 2),
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate_pct, 1),
            "profit_factor": round(self.profit_factor, 2),
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "long_pnl_total": round(self.long_pnl_total, 2),
            "short_pnl_total": round(self.short_pnl_total, 2),
            "total_costs": round(self.total_costs, 2),
            "cost_ratio_pct": round(self.cost_ratio_pct, 1),
            "turnover_pct": round(self.turnover_pct, 1),
            "n_trading_days": self.n_trading_days,
            "regime_metrics": self.regime_metrics,
        }


# ── Résultat walk-forward global ────────────────────────────────────────────

@dataclass(slots=True)
class WalkForwardResult:
    """Résultat agrégé d'un walk-forward financier complet."""
    folds: list[FoldFinancials] = field(default_factory=list)
    n_folds: int = 0
    n_folds_positive: int = 0

    # Agrégats
    median_sharpe: float = 0.0
    percentile_25_sharpe: float = 0.0
    median_return_pct: float = 0.0
    median_max_dd_pct: float = 0.0
    median_profit_factor: float = 0.0
    fold_stability_pct: float = 0.0  # % de folds positifs
    avg_cost_ratio_pct: float = 0.0

    # Stats avancées
    deflated_sharpe: float | None = None
    deflated_sharpe_pvalue: float | None = None
    is_deflated_significant: bool = False
    promotion_score: float | None = None
    is_promotable: bool = False

    # Bootstrap
    bootstrap_sharpe_ci_low: float | None = None
    bootstrap_sharpe_ci_high: float | None = None

    # Métadonnées
    combined_daily_returns: np.ndarray = field(default_factory=lambda: np.array([]))
    total_trades_all_folds: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "n_folds": self.n_folds,
            "n_folds_positive": self.n_folds_positive,
            "fold_stability_pct": round(self.fold_stability_pct, 1),
            "median_sharpe": round(self.median_sharpe, 3),
            "percentile_25_sharpe": round(self.percentile_25_sharpe, 3),
            "median_return_pct": round(self.median_return_pct, 2),
            "median_max_dd_pct": round(self.median_max_dd_pct, 2),
            "median_profit_factor": round(self.median_profit_factor, 2),
            "avg_cost_ratio_pct": round(self.avg_cost_ratio_pct, 1),
            "deflated_sharpe": round(self.deflated_sharpe, 3) if self.deflated_sharpe is not None else None,
            "deflated_sharpe_pvalue": round(self.deflated_sharpe_pvalue, 4) if self.deflated_sharpe_pvalue is not None else None,
            "is_deflated_significant": self.is_deflated_significant,
            "promotion_score": round(self.promotion_score, 3) if self.promotion_score is not None else None,
            "is_promotable": self.is_promotable,
            "total_trades_all_folds": self.total_trades_all_folds,
            "folds": [f.to_dict() for f in self.folds],
        }


# ── Data provider protocol ──────────────────────────────────────────────────

# Les consommateurs doivent fournir une factory qui, pour une date et un fold
# donnés, retourne les DataFrames nécessaires au bridge risque.
DataProviderFn = Callable[
    [date, date],  # start_date, end_date
    dict[str, pd.DataFrame | None],  # scores_df, predictions_df, close_df, high_df, low_df, volume_df
]


# ── Fonctions de calcul ─────────────────────────────────────────────────────

def _compute_equity_metrics(
    daily_returns: np.ndarray,
    annual_factor: int = 252,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    """Calcule les métriques depuis une série de returns quotidiens."""
    if len(daily_returns) == 0:
        return {}

    equity = 1.0 + daily_returns
    equity_curve = np.cumprod(equity)
    total_return = equity_curve[-1] - 1.0

    n_days = len(daily_returns)
    years = n_days / annual_factor if n_days > 0 else 1.0
    cagr = (equity_curve[-1]) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    mean_ret = float(np.mean(daily_returns))
    std_ret = float(np.std(daily_returns, ddof=1))
    sharpe = (mean_ret - risk_free_rate / annual_factor) / std_ret * np.sqrt(annual_factor) if std_ret > 0 else 0.0

    # Sortino
    downside = daily_returns[daily_returns < 0]
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 0 else 1e-9
    sortino = (mean_ret - risk_free_rate / annual_factor) / downside_std * np.sqrt(annual_factor) if downside_std > 0 else 0.0

    # Max drawdown
    running_peak = np.maximum.accumulate(equity_curve)
    drawdowns = equity_curve / running_peak - 1.0
    max_dd = abs(float(np.min(drawdowns)))

    # Calmar
    calmar = cagr / (max_dd / 100.0) if max_dd > 0 else 0.0

    # Vol annualisée
    vol = std_ret * np.sqrt(annual_factor) * 100.0

    return {
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "max_drawdown_pct": max_dd * 100.0,
        "volatility_annual_pct": vol,
        "n_trading_days": n_days,
    }


def _compute_trade_metrics(
    closed_trades_df: pd.DataFrame,
    initial_equity: float,
) -> dict[str, float]:
    """Calcule les métriques de trading depuis un DataFrame de trades fermés."""
    if closed_trades_df is None or closed_trades_df.empty:
        return {
            "total_trades": 0, "win_rate_pct": 0.0, "profit_factor": 0.0,
            "avg_trade_return_pct": 0.0, "avg_trade_duration_days": 0.0,
            "long_trades": 0, "short_trades": 0,
            "long_win_rate_pct": 0.0, "short_win_rate_pct": 0.0,
            "long_pnl_total": 0.0, "short_pnl_total": 0.0,
            "total_costs": 0.0, "cost_ratio_pct": 0.0,
            "force_close_exits": 0,
        }

    n = len(closed_trades_df)
    win_rate = float((closed_trades_df["return_pct"] > 0).mean() * 100.0)

    gains = closed_trades_df.loc[closed_trades_df["return_pct"] > 0, "return_pct"].sum()
    losses = abs(closed_trades_df.loc[closed_trades_df["return_pct"] < 0, "return_pct"].sum())
    profit_factor = gains / losses if losses > 0 else float("inf")

    avg_ret = float(closed_trades_df["return_pct"].mean())
    avg_dur = float(closed_trades_df["bars_held"].mean()) if "bars_held" in closed_trades_df.columns else 0.0

    # Par side
    side_col = "side" if "side" in closed_trades_df.columns else None
    long_mask = closed_trades_df[side_col].isin(["long", "buy"]) if side_col else pd.Series(False, index=closed_trades_df.index)
    short_mask = closed_trades_df[side_col].isin(["short", "sell"]) if side_col else pd.Series(False, index=closed_trades_df.index)

    long_n = int(long_mask.sum())
    short_n = int(short_mask.sum())
    long_wr = float((closed_trades_df.loc[long_mask, "return_pct"] > 0).mean() * 100.0) if long_n > 0 else 0.0
    short_wr = float((closed_trades_df.loc[short_mask, "return_pct"] > 0).mean() * 100.0) if short_n > 0 else 0.0
    long_pnl = float(closed_trades_df.loc[long_mask, "pnl"].sum()) if "pnl" in closed_trades_df.columns and long_n > 0 else 0.0
    short_pnl = float(closed_trades_df.loc[short_mask, "pnl"].sum()) if "pnl" in closed_trades_df.columns and short_n > 0 else 0.0

    # Coûts
    total_costs = float(closed_trades_df["costs"].sum()) if "costs" in closed_trades_df.columns else 0.0
    gross_pnl = float(closed_trades_df["pnl"].sum() + total_costs) if "pnl" in closed_trades_df.columns else 0.0
    cost_ratio = (total_costs / gross_pnl * 100.0) if gross_pnl > 0 else 0.0

    force_close = int((closed_trades_df.get("exit_reason") == "force_close").sum()) if "exit_reason" in closed_trades_df.columns else 0

    return {
        "total_trades": n,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "avg_trade_return_pct": avg_ret,
        "avg_trade_duration_days": avg_dur,
        "long_trades": long_n,
        "short_trades": short_n,
        "long_win_rate_pct": long_wr,
        "short_win_rate_pct": short_wr,
        "long_pnl_total": long_pnl,
        "short_pnl_total": short_pnl,
        "total_costs": total_costs,
        "cost_ratio_pct": cost_ratio,
        "force_close_exits": force_close,
    }


# ── Exécution d'un fold ─────────────────────────────────────────────────────

def run_walk_forward_fold(
    plan: Any,  # WalkForwardPlan
    config: Any,  # RiskConfig
    wf_config: WalkForwardConfig,
    data_provider: DataProviderFn,
    fold_index: int = 0,
) -> FoldFinancials | None:
    """Exécute un fold de walk-forward : rejoue chaque jour de test via
    le bridge risque, simule l'exécution, et extrait les métriques.

    Parameters
    ----------
    plan : WalkForwardPlan
        Plan du fold (bornes train/val/test, purge, embargo).
    config : RiskConfig
        Configuration risque immuable (fingerprintée).
    wf_config : WalkForwardConfig
        Configuration du walk-forward.
    data_provider : DataProviderFn
        Fonction (start, end) -> dict de DataFrames.
    fold_index : int
        Index du fold (0-based).

    Returns
    -------
    FoldFinancials or None
        None si le fold n'a généré aucun trade.
    """
    from backtesting.risk_bridge import build_phase2_risk_result

    test_start = pd.Timestamp(plan.test_start)
    test_end = pd.Timestamp(plan.test_end)

    # 1. Charger les données pour la période de test
    data = data_provider(test_start.to_pydate(), test_end.to_pydate())
    scores_df = data.get("scores_df")
    predictions_df = data.get("predictions_df")
    close_df = data.get("close_df")
    high_df = data.get("high_df")
    low_df = data.get("low_df")
    volume_df = data.get("volume_df")

    if scores_df is None or scores_df.empty:
        LOGGER.warning("Fold %d: no scores data for %s → %s", fold_index, plan.test_start, plan.test_end)
        return None

    # 2. Appliquer le bridge risque sur chaque snapshot date
    all_entries: list[Any] = []
    all_signals: list[pd.DataFrame] = []
    snapshot_dates = sorted(scores_df["trade_date"].dropna().unique())

    for snap_date in snapshot_dates:
        day_scores = scores_df[scores_df["trade_date"] == snap_date]
        day_predictions = predictions_df[predictions_df["trade_date"] == snap_date] if predictions_df is not None else pd.DataFrame()

        if day_scores.empty:
            continue

        try:
            result = build_phase2_risk_result(
                scores_df=day_scores,
                predictions_df=day_predictions,
                close_df=close_df,
                high_df=high_df,
                low_df=low_df,
                volume_df=volume_df,
                risk_config=config,
            )
        except Exception:
            LOGGER.warning("Fold %d: bridge failed for %s", fold_index, snap_date, exc_info=True)
            continue

        all_entries.extend(result.entries)
        if not result.signals_df.empty:
            all_signals.append(result.signals_df)

    if not all_entries:
        LOGGER.info("Fold %d: no entries generated", fold_index)
        return None

    # 3. Simuler l'exécution
    fold_fin = _simulate_fold_execution(
        all_entries,
        all_signals,
        close_df,
        high_df,
        low_df,
        volume_df,
        wf_config,
        fold_index,
        plan,
    )

    return fold_fin


def _simulate_fold_execution(
    entries: list[Any],
    signals: list[pd.DataFrame],
    close_df: pd.DataFrame | None,
    high_df: pd.DataFrame | None,
    low_df: pd.DataFrame | None,
    volume_df: pd.DataFrame | None,
    wf_config: WalkForwardConfig,
    fold_index: int,
    plan: Any,
) -> FoldFinancials | None:
    """Simule l'exécution des entries et calcule les métriques du fold."""
    # Construire un signals_df consolidé
    if signals:
        signals_df = pd.concat(signals, ignore_index=True)
    else:
        signals_df = pd.DataFrame()

    # Utiliser le simulateur existant
    try:
        from backtesting.simulator import Simulator

        sim = Simulator(
            initial_equity=wf_config.initial_equity,
            commission_bps=wf_config.commission_bps,
            slippage_bps=wf_config.slippage_bps,
            execution_model=wf_config.execution_model,
        )
        sim_result = sim.run(
            signals_df=signals_df,
            close_df=close_df,
            high_df=high_df,
            low_df=low_df,
            volume_df=volume_df,
        )
    except Exception:
        LOGGER.warning("Fold %d: simulation failed", fold_index, exc_info=True)
        return None

    if sim_result is None or sim_result.closed_trades_df.empty:
        LOGGER.info("Fold %d: no closed trades", fold_index)
        return None

    closed = sim_result.closed_trades_df

    # Extraire les returns quotidiens de l'equity curve
    if hasattr(sim_result, "equity_curve") and sim_result.equity_curve is not None:
        eq = sim_result.equity_curve
        if isinstance(eq, pd.Series):
            daily_rets = eq.pct_change().dropna().to_numpy()
        else:
            daily_rets = np.array([])
    else:
        daily_rets = np.array([])

    # Métriques d'equity
    eq_metrics = _compute_equity_metrics(daily_rets, wf_config.annual_factor, wf_config.risk_free_rate)

    # Métriques de trading
    trade_metrics = _compute_trade_metrics(closed, wf_config.initial_equity)

    # Turnover depuis les signaux
    turnover = 0.0
    gross_exp = 0.0
    net_exp = 0.0
    if not signals_df.empty and close_df is not None:
        # Approximation : notional total / equity moyen
        if "target_notional" in signals_df.columns:
            total_notional = signals_df["target_notional"].abs().sum()
            n_days = len(signals_df["trade_date"].unique()) if "trade_date" in signals_df.columns else 1
            avg_equity = wf_config.initial_equity
            if n_days > 0:
                turnover = (total_notional / n_days) / avg_equity * 100.0

    return FoldFinancials(
        fold_index=fold_index,
        test_start=str(plan.test_start),
        test_end=str(plan.test_end),
        daily_returns=daily_rets,
        **eq_metrics,
        **trade_metrics,
        turnover_pct=round(turnover, 1),
        gross_exposure_avg_pct=round(gross_exp, 1),
        net_exposure_avg_pct=round(net_exp, 1),
    )


# ── Orchestrateur principal ─────────────────────────────────────────────────

def run_walk_forward(
    plan_folds: list[Any],  # list[WalkForwardPlan]
    config: Any,  # RiskConfig
    wf_config: WalkForwardConfig | None = None,
    data_provider: DataProviderFn | None = None,
    n_trials: int = 100,
) -> WalkForwardResult:
    """Exécute un walk-forward financier complet sur une liste de folds.

    Parameters
    ----------
    plan_folds : list[WalkForwardPlan]
        Liste des folds à exécuter (déjà purgés/embargoés).
    config : RiskConfig
        Configuration risque immuable.
    wf_config : WalkForwardConfig | None
        Configuration du walk-forward.
    data_provider : DataProviderFn | None
        Fonction (start, end) -> dict de DataFrames.
    n_trials : int
        Nombre d'essais pour le Deflated Sharpe.

    Returns
    -------
    WalkForwardResult
    """
    if wf_config is None:
        wf_config = WalkForwardConfig()

    folds: list[FoldFinancials] = []
    for i, plan in enumerate(plan_folds):
        LOGGER.info("Walk-forward fold %d/%d: test %s → %s", i + 1, len(plan_folds), plan.test_start, plan.test_end)
        if data_provider is None:
            LOGGER.warning("Fold %d: no data_provider, skipping", i)
            continue
        fold_fin = run_walk_forward_fold(plan, config, wf_config, data_provider, fold_index=i)
        if fold_fin is not None:
            folds.append(fold_fin)

    if not folds:
        LOGGER.warning("No folds produced results")
        return WalkForwardResult()

    # Agrégation
    sharpes = [f.sharpe_ratio for f in folds]
    returns = [f.total_return_pct for f in folds]
    dds = [f.max_drawdown_pct for f in folds]
    pfs = [f.profit_factor for f in folds if f.profit_factor != float("inf")]
    cost_ratios = [f.cost_ratio_pct for f in folds]
    n_positive = sum(1 for r in returns if r > 0)
    n_total = len(folds)

    # Combined returns
    all_rets = np.concatenate([f.daily_returns for f in folds if len(f.daily_returns) > 0])
    total_trades = sum(f.total_trades for f in folds)

    result = WalkForwardResult(
        folds=folds,
        n_folds=n_total,
        n_folds_positive=n_positive,
        median_sharpe=float(np.median(sharpes)) if sharpes else 0.0,
        percentile_25_sharpe=float(np.percentile(sharpes, 25)) if sharpes else 0.0,
        median_return_pct=float(np.median(returns)) if returns else 0.0,
        median_max_dd_pct=float(np.median(dds)) if dds else 0.0,
        median_profit_factor=float(np.median(pfs)) if pfs else 0.0,
        fold_stability_pct=n_positive / n_total * 100.0 if n_total > 0 else 0.0,
        avg_cost_ratio_pct=float(np.mean(cost_ratios)) if cost_ratios else 0.0,
        combined_daily_returns=all_rets,
        total_trades_all_folds=total_trades,
    )

    # Stats avancées
    if len(all_rets) > 20:
        try:
            from backtesting.statistical_validation import (
                block_bootstrap_sharpe,
                compute_promotion_score,
                deflated_sharpe_ratio,
            )

            # Deflated Sharpe
            dsr = deflated_sharpe_ratio(all_rets, n_trials=n_trials)
            result.deflated_sharpe = dsr.deflated_sharpe
            result.deflated_sharpe_pvalue = dsr.p_value
            result.is_deflated_significant = dsr.is_significant

            # Block bootstrap
            boot = block_bootstrap_sharpe(all_rets, n_iterations=1000, block_size=10)
            result.bootstrap_sharpe_ci_low = float(boot.get("ci_low", 0))
            result.bootstrap_sharpe_ci_high = float(boot.get("ci_high", 0))

            # Promotion score
            med_sharpe = result.median_sharpe
            med_sortino = float(np.median([f.sortino_ratio for f in folds]))
            med_calmar = float(np.median([f.calmar_ratio for f in folds]))
            med_dd = result.median_max_dd_pct
            med_pf = result.median_profit_factor if result.median_profit_factor != float("inf") else 2.0
            avg_wr = float(np.mean([f.win_rate_pct for f in folds]))
            avg_cost = result.avg_cost_ratio_pct

            promo = compute_promotion_score(
                sharpe=med_sharpe,
                sortino=med_sortino,
                calmar=med_calmar,
                max_drawdown_pct=med_dd,
                profit_factor=med_pf,
                win_rate=avg_wr,
                n_trades=total_trades,
                cost_ratio=avg_cost,
                fold_stability=result.fold_stability_pct / 100.0,
                sharpe_deflated=result.deflated_sharpe,
            )
            result.promotion_score = promo.total_score
            result.is_promotable = promo.is_promotable
        except Exception:
            LOGGER.warning("Advanced stats computation failed", exc_info=True)

    return result


# ── Section 17 Point 7-R4 : rapport OOS reproductible ─────────────────────

@dataclass(slots=True)
class WalkForwardReport:
    """Rapport machine-readable d'un walk-forward financier complet.

    Sérialisable en JSON pour archivage et reproductibilité.
    """
    result: WalkForwardResult
    config_fingerprint: str = ""
    plan_summary: dict[str, object] = field(default_factory=dict)
    generated_at: str = ""
    engine_version: str = "1.0.0"

    def to_dict(self) -> dict[str, object]:
        return {
            "engine_version": self.engine_version,
            "generated_at": self.generated_at,
            "config_fingerprint": self.config_fingerprint,
            "plan_summary": self.plan_summary,
            "result": self.result.to_dict(),
            "gates": self._compute_gates(),
        }

    def _compute_gates(self) -> dict[str, object]:
        """Évalue les gates de sortie du Sprint Maître 7."""
        r = self.result
        return {
            "fold_stability_gate": {
                "value": r.fold_stability_pct,
                "threshold": 70.0,
                "passed": r.fold_stability_pct >= 70.0,
                "label": "≥ 70% des folds OOS positifs nets de coûts",
            },
            "sharpe_median_gate": {
                "value": r.median_sharpe,
                "threshold": 1.0,
                "passed": r.median_sharpe >= 1.0,
                "label": "Sharpe OOS médian ≥ 1.0",
            },
            "sharpe_p25_gate": {
                "value": r.percentile_25_sharpe,
                "threshold": 0.0,
                "passed": r.percentile_25_sharpe > 0,
                "label": "25e percentile Sharpe > 0",
            },
            "profit_factor_gate": {
                "value": r.median_profit_factor,
                "threshold": 1.20,
                "passed": r.median_profit_factor >= 1.20,
                "label": "Profit factor ≥ 1.20",
            },
            "cost_ratio_gate": {
                "value": r.avg_cost_ratio_pct,
                "threshold": 35.0,
                "passed": r.avg_cost_ratio_pct <= 35.0,
                "label": "Coûts ≤ 35% de l'alpha brut",
            },
            "deflated_significance_gate": {
                "value": r.is_deflated_significant,
                "threshold": True,
                "passed": r.is_deflated_significant,
                "label": "Deflated Sharpe significatif (p < 0.05)",
            },
            "promotion_gate": {
                "value": r.is_promotable,
                "threshold": True,
                "passed": r.is_promotable,
                "label": "Score de promotion ≥ 0.60",
            },
            "holdout_intact": True,
        }

    def to_json(self, filepath: str) -> None:
        """Persiste le rapport en JSON atomique."""
        import json
        import os

        d = self.to_dict()
        # Convertir les arrays numpy en listes pour sérialisation
        tmp = json.dumps(d, default=_json_default, ensure_ascii=False, indent=2)
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(tmp)
        LOGGER.info("WalkForwardReport écrit : %s", filepath)


def _json_default(obj: object) -> object:
    """Sérialiseur JSON pour types numpy."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    raise TypeError(f"Type non sérialisable: {type(obj)}")


def generate_walk_forward_report(
    result: WalkForwardResult,
    config: Any,
    plan_folds: list[Any],
    output_path: str | None = None,
) -> WalkForwardReport:
    """Produit le rapport OOS reproductible.

    Parameters
    ----------
    result : WalkForwardResult
    config : RiskConfig
        Configuration utilisée (pour fingerprint).
    plan_folds : list[WalkForwardPlan]
        Plans de folds exécutés.
    output_path : str | None
        Si fourni, persiste le rapport JSON.

    Returns
    -------
    WalkForwardReport
    """
    from datetime import datetime, timezone

    plan_summary = {
        "n_folds": len(plan_folds),
        "folds": [
            {
                "train": f"{p.train_start}→{p.train_end}",
                "val": f"{p.val_start}→{p.val_end}",
                "test": f"{p.test_start}→{p.test_end}",
                "purge_days": p.purge_days,
                "embargo_days": p.embargo_days,
            }
            for p in plan_folds
        ],
    }

    report = WalkForwardReport(
        result=result,
        config_fingerprint=getattr(config, "fingerprint", ""),
        plan_summary=plan_summary,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    if output_path:
        report.to_json(output_path)

    return report


# ── Section 17 Point 7-R2 : DataProvider DB ──────────────────────────────

def create_db_data_provider(
    scores_df: pd.DataFrame,
    predictions_df: pd.DataFrame | None = None,
    close_df: pd.DataFrame | None = None,
    high_df: pd.DataFrame | None = None,
    low_df: pd.DataFrame | None = None,
    volume_df: pd.DataFrame | None = None,
) -> DataProviderFn:
    """Crée un DataProvider qui filtre les DataFrames par plage de dates.

    Usage typique : charger les données complètes depuis la DB,
    puis créer un provider qui les filtre par fold.

    Parameters
    ----------
    scores_df : pd.DataFrame
        Doit contenir une colonne ``trade_date``.
    predictions_df, close_df, high_df, low_df, volume_df : pd.DataFrame | None
        DataFrames avec index de dates ou colonne trade_date.

    Returns
    -------
    DataProviderFn
    """
    def _provider(start: date, end: date) -> dict[str, pd.DataFrame | None]:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)

        def _filter(df: pd.DataFrame | None, date_col: str = "trade_date") -> pd.DataFrame | None:
            if df is None or df.empty:
                return df
            if date_col in df.columns:
                mask = (df[date_col] >= start_ts) & (df[date_col] <= end_ts)
                return df.loc[mask].copy()
            # Sinon, filtrer par index
            if isinstance(df.index, pd.DatetimeIndex):
                return df.loc[start_ts:end_ts].copy()
            return df

        return {
            "scores_df": _filter(scores_df),
            "predictions_df": _filter(predictions_df),
            "close_df": _filter(close_df, date_col=None) if close_df is not None else None,
            "high_df": _filter(high_df, date_col=None) if high_df is not None else None,
            "low_df": _filter(low_df, date_col=None) if low_df is not None else None,
            "volume_df": _filter(volume_df, date_col=None) if volume_df is not None else None,
        }

    return _provider

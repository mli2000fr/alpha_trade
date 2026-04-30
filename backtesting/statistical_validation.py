"""
backtesting/statistical_validation.py
======================================
Phase G — validation statistique post-backtest.

- G1. Monte Carlo bootstrap des trades pour intervalles de confiance
      sur Sharpe / CAGR / Max DD / Win Rate.
- G2. Analyse de sensibilité (perturbations ±X% de chaque paramètre clé).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# G1 — Bootstrap des trades
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class BootstrapResult:
    n_iterations: int
    sample_size: int
    mean_total_return_pct: float
    median_total_return_pct: float
    ci_low_total_return_pct: float
    ci_high_total_return_pct: float
    mean_sharpe: float
    ci_low_sharpe: float
    ci_high_sharpe: float
    mean_max_dd_pct: float
    ci_high_max_dd_pct: float
    win_rate_pct: float

    def to_dict(self) -> dict[str, float]:
        return {
            "n_iterations": int(self.n_iterations),
            "sample_size": int(self.sample_size),
            "mean_total_return_pct": float(self.mean_total_return_pct),
            "median_total_return_pct": float(self.median_total_return_pct),
            "ci_low_total_return_pct": float(self.ci_low_total_return_pct),
            "ci_high_total_return_pct": float(self.ci_high_total_return_pct),
            "mean_sharpe": float(self.mean_sharpe),
            "ci_low_sharpe": float(self.ci_low_sharpe),
            "ci_high_sharpe": float(self.ci_high_sharpe),
            "mean_max_dd_pct": float(self.mean_max_dd_pct),
            "ci_high_max_dd_pct": float(self.ci_high_max_dd_pct),
            "win_rate_pct": float(self.win_rate_pct),
        }


def bootstrap_trades(
    closed_trades_df: pd.DataFrame,
    *,
    n_iterations: int = 1000,
    sample_size: int | None = None,
    initial_equity: float = 100_000.0,
    confidence: float = 0.95,
    seed: int | None = 0,
) -> BootstrapResult:
    """Bootstrap (resampling avec remise) des trades pour IC sur métriques.

    Convention :
    - simule chaque itération comme une **séquence aléatoire** (même nombre)
      de trades tirés avec remise dans ``closed_trades_df`` ;
    - reconstruit une equity curve par produit cumulé des ``return_pct/100`` ;
    - évalue total_return, sharpe (sur les returns par trade) et max DD.
    """
    if closed_trades_df is None or closed_trades_df.empty:
        return BootstrapResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    rng = np.random.default_rng(seed)
    rets = closed_trades_df["return_pct"].astype(float).to_numpy() / 100.0
    n_trades = len(rets)
    sample_size = sample_size or n_trades
    if sample_size <= 0 or n_trades == 0:
        return BootstrapResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    total_returns = np.empty(n_iterations, dtype=float)
    sharpes = np.empty(n_iterations, dtype=float)
    max_dds = np.empty(n_iterations, dtype=float)

    for i in range(n_iterations):
        sample = rng.choice(rets, size=sample_size, replace=True)
        equity = initial_equity * np.cumprod(1.0 + sample)
        total_returns[i] = (equity[-1] / initial_equity - 1.0) * 100.0
        std = float(sample.std(ddof=0))
        sharpes[i] = float(sample.mean() / std) * math.sqrt(252.0) if std > 0 else 0.0
        running_peak = np.maximum.accumulate(equity)
        dd = equity / running_peak - 1.0
        max_dds[i] = abs(float(dd.min())) * 100.0

    alpha = (1.0 - confidence) / 2.0
    ci_low_tr = float(np.quantile(total_returns, alpha))
    ci_high_tr = float(np.quantile(total_returns, 1 - alpha))
    ci_low_sh = float(np.quantile(sharpes, alpha))
    ci_high_sh = float(np.quantile(sharpes, 1 - alpha))
    ci_high_dd = float(np.quantile(max_dds, 1 - alpha))
    win_rate = float((rets > 0).mean() * 100.0)
    return BootstrapResult(
        n_iterations=n_iterations,
        sample_size=sample_size,
        mean_total_return_pct=float(total_returns.mean()),
        median_total_return_pct=float(np.median(total_returns)),
        ci_low_total_return_pct=ci_low_tr,
        ci_high_total_return_pct=ci_high_tr,
        mean_sharpe=float(sharpes.mean()),
        ci_low_sharpe=ci_low_sh,
        ci_high_sharpe=ci_high_sh,
        mean_max_dd_pct=float(max_dds.mean()),
        ci_high_max_dd_pct=ci_high_dd,
        win_rate_pct=win_rate,
    )


# ---------------------------------------------------------------------------
# G2 — Analyse de sensibilité
# ---------------------------------------------------------------------------


def parameter_sensitivity(
    base_params: dict[str, float],
    metric_fn: Callable[[dict[str, float]], float],
    *,
    perturbation: float = 0.10,
    parameters: list[str] | None = None,
) -> pd.DataFrame:
    """Évalue la sensibilité d'une métrique aux perturbations ±X% des params.

    Args
    ----
    base_params : dict des paramètres de référence (ex {"tp": 0.08, "ts": 0.05}).
    metric_fn   : fonction qui prend un dict params → renvoie une métrique scalaire.
    perturbation: amplitude relative (0.10 = ±10%).
    parameters  : sous-liste à tester (sinon toutes les clés de base_params).

    Returns
    -------
    DataFrame [parameter, value_minus, value_plus, metric_minus, metric_plus,
               metric_base, sensitivity_pct]
    """
    parameters = parameters or list(base_params.keys())
    base_metric = float(metric_fn(dict(base_params)))
    rows: list[dict[str, float]] = []
    for param in parameters:
        if param not in base_params:
            continue
        base_value = float(base_params[param])
        if base_value == 0:
            continue
        v_minus = base_value * (1.0 - perturbation)
        v_plus = base_value * (1.0 + perturbation)
        m_minus = float(metric_fn({**base_params, param: v_minus}))
        m_plus = float(metric_fn({**base_params, param: v_plus}))
        sensitivity = ((m_plus - m_minus) / (2.0 * perturbation)) / max(abs(base_metric), 1e-9)
        rows.append(
            {
                "parameter": param,
                "value_base": base_value,
                "value_minus": v_minus,
                "value_plus": v_plus,
                "metric_base": base_metric,
                "metric_minus": m_minus,
                "metric_plus": m_plus,
                "sensitivity_pct": float(sensitivity * 100.0),
            }
        )
    return pd.DataFrame(rows).sort_values("sensitivity_pct", key=abs, ascending=False)


__all__ = [
    "BootstrapResult",
    "bootstrap_trades",
    "parameter_sensitivity",
]


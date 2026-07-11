"""
backtesting/statistical_validation.py
======================================
Phase G — validation statistique post-backtest.

- G1. Monte Carlo bootstrap des trades pour intervalles de confiance
      sur Sharpe / CAGR / Max DD / Win Rate.
- G2. Analyse de sensibilité (perturbations ±X% de chaque paramètre clé).

Sprint Maître 7 — ajouts :
- G3. Deflated Sharpe Ratio (DSR) avec correction multiple testing.
- G4. Block bootstrap pour séries temporelles avec dépendance.
- G5. Promotion score composite (dimensionnellement cohérent).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Callable

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
    "block_bootstrap_sharpe",
    "deflated_sharpe_ratio",
    "multiple_testing_correction",
    "compute_promotion_score",
    "parameter_sensitivity",
    "WalkForwardPlan",
    "PromotionScoreResult",
]


# ── Sprint Maître 7 ─────────────────────────────────────────────────────────

@dataclass(slots=True)
class WalkForwardPlan:
    """Plan de walk-forward nested avec purge et embargo (Sprint Maître 7).

    Attributes
    ----------
    train_start, train_end : date
        Bornes de la période d'entraînement interne.
    val_start, val_end : date
        Bornes de validation.
    test_start, test_end : date
        Bornes du test externe (fold OOS).
    purge_days : int
        Jours de purge entre train et val (évite chevauchement labels).
    embargo_days : int
        Jours d'embargo entre val et test.
    fold_index : int
        Index du fold.
    """

    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str
    purge_days: int = 5
    embargo_days: int = 10
    fold_index: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "fold_index": self.fold_index,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "val_start": self.val_start,
            "val_end": self.val_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "purge_days": self.purge_days,
            "embargo_days": self.embargo_days,
        }


@dataclass(slots=True)
class DeflatedSharpeResult:
    """Résultat du Deflated Sharpe Ratio (Sprint Maître 7)."""

    annual_sharpe: float
    deflated_sharpe: float
    p_value: float
    n_trials: int
    skewness: float
    kurtosis: float
    is_significant: bool  # p_value < 0.05

    def to_dict(self) -> dict[str, float]:
        return {
            "annual_sharpe": round(self.annual_sharpe, 4),
            "deflated_sharpe": round(self.deflated_sharpe, 4),
            "p_value": round(self.p_value, 4),
            "n_trials": self.n_trials,
            "skewness": round(self.skewness, 4),
            "kurtosis": round(self.kurtosis, 4),
            "is_significant": float(self.is_significant),
        }


def deflated_sharpe_ratio(
    returns: np.ndarray,
    *,
    n_trials: int = 100,
    annual_factor: float = 252.0,
) -> DeflatedSharpeResult:
    """Deflated Sharpe Ratio (DSR) — corrige le multiple testing (Sprint Maître 7).

    Basé sur Harvey & Liu (2015). Le DSR ajuste le Sharpe observé
    pour tenir compte du nombre de stratégies testées (n_trials).

    .. math::
        DSR = P(Sharpe > E[max Sharpe sous H0])

    Parameters
    ----------
    returns : np.ndarray
        Rendements journaliers.
    n_trials : int
        Nombre de stratégies/testes alternatives (correction Bonferroni implicite).
    annual_factor : float
        Facteur d'annualisation (252 pour daily).

    Returns
    -------
    DeflatedSharpeResult
    """
    returns = np.asarray(returns, float)
    n = len(returns)
    if n < 20:
        return DeflatedSharpeResult(0.0, 0.0, 1.0, n_trials, 0.0, 0.0, False)

    mu = float(np.mean(returns))
    sigma = float(np.std(returns, ddof=1))
    annual_sharpe = (mu / sigma) * math.sqrt(annual_factor) if sigma > 0 else 0.0

    # Moments
    skew = float(_skewness(returns))
    kurt = float(_kurtosis(returns))

    # Sharpe asymptotique sous H0 (stratégie aléatoire)
    # E[max Sharpe] ≈ sqrt(2 * log(n_trials))
    expected_max_sr = math.sqrt(2.0 * math.log(max(n_trials, 1)))

    # Variance asymptotique du Sharpe ratio
    sharpe_var = (1.0 + 0.5 * annual_sharpe ** 2 - skew * annual_sharpe
                  + (kurt - 3.0) / 4.0 * annual_sharpe ** 2) / n

    if sharpe_var <= 0:
        return DeflatedSharpeResult(annual_sharpe, 0.0, 1.0, n_trials, skew, kurt, False)

    # Deflated Sharpe
    dsr = (annual_sharpe - expected_max_sr) / math.sqrt(sharpe_var)

    # p-value (Normale asymptotique)
    from math import erfc
    p_value = float(0.5 * erfc(dsr / math.sqrt(2.0)))

    return DeflatedSharpeResult(
        annual_sharpe=annual_sharpe,
        deflated_sharpe=dsr,
        p_value=min(p_value, 1.0),
        n_trials=n_trials,
        skewness=skew,
        kurtosis=kurt,
        is_significant=p_value < 0.05,
    )


def block_bootstrap_sharpe(
    returns: np.ndarray,
    *,
    n_iterations: int = 1000,
    block_size: int = 10,
    confidence: float = 0.95,
    annual_factor: float = 252.0,
    seed: int | None = 42,
) -> dict[str, float]:
    """Block bootstrap pour le Sharpe ratio (Sprint Maître 7).

    Contrairement au bootstrap i.i.d., le block bootstrap préserve
    la structure de dépendance temporelle (auto-corrélation,
    volatility clustering).

    Parameters
    ----------
    returns : np.ndarray
        Rendements journaliers.
    n_iterations : int
        Nombre d'itérations bootstrap.
    block_size : int
        Taille des blocs (10 jours ≈ 2 semaines).
    confidence : float
        Niveau de confiance pour les intervalles.
    annual_factor : float
        Facteur d'annualisation.

    Returns
    -------
    dict avec mean_sharpe, ci_low_sharpe, ci_high_sharpe.
    """
    returns = np.asarray(returns, float)
    n = len(returns)
    if n < block_size * 2:
        return {"mean_sharpe": 0.0, "ci_low_sharpe": 0.0, "ci_high_sharpe": 0.0}

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    blocks = [returns[i * block_size:(i + 1) * block_size] for i in range(n_blocks)]
    blocks = [b for b in blocks if len(b) > 0]

    sharpes = np.empty(n_iterations, float)
    for i in range(n_iterations):
        sampled_indices = rng.integers(0, len(blocks), size=n_blocks)
        sampled = np.concatenate([blocks[idx] for idx in sampled_indices])
        sampled = sampled[:n]  # tronquer à la longueur originale
        mu = float(np.mean(sampled))
        sigma = float(np.std(sampled, ddof=1))
        sharpes[i] = (mu / sigma) * math.sqrt(annual_factor) if sigma > 0 else 0.0

    alpha = (1.0 - confidence) / 2.0
    return {
        "mean_sharpe": round(float(np.mean(sharpes)), 4),
        "ci_low_sharpe": round(float(np.quantile(sharpes, alpha)), 4),
        "ci_high_sharpe": round(float(np.quantile(sharpes, 1 - alpha)), 4),
    }


def multiple_testing_correction(
    p_values: list[float],
    *,
    method: str = "bonferroni",
) -> list[float]:
    """Correction pour tests multiples (Sprint Maître 7).

    Parameters
    ----------
    p_values : list[float]
        p-valeurs brutes.
    method : str
        ``"bonferroni"`` (p * n) ou ``"bh"`` (Benjamini-Hochberg).

    Returns
    -------
    list[float]
        p-valeurs corrigées.
    """
    n = len(p_values)
    if n == 0:
        return []

    if method == "bh":
        # Benjamini-Hochberg
        sorted_idx = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_idx]
        corrected = np.minimum(1.0, sorted_p * n / (np.arange(n) + 1))
        # Monotonicité
        for i in range(n - 2, -1, -1):
            corrected[i] = min(corrected[i], corrected[i + 1])
        result = np.zeros(n)
        result[sorted_idx] = corrected
        return [float(x) for x in result]

    # Bonferroni par défaut
    return [min(1.0, p * n) for p in p_values]


@dataclass(slots=True)
class PromotionScoreResult:
    """Score de promotion composite (Sprint Maître 7).

    Combine plusieurs métriques en un score unique dimensionnellement
    cohérent pour la décision GO/NO-GO.
    """

    total_score: float
    sharpe_score: float
    drawdown_score: float
    profit_factor_score: float
    stability_score: float
    cost_efficiency_score: float
    is_promotable: bool

    def to_dict(self) -> dict[str, float]:
        return {
            "total_score": round(self.total_score, 4),
            "sharpe_score": round(self.sharpe_score, 4),
            "drawdown_score": round(self.drawdown_score, 4),
            "profit_factor_score": round(self.profit_factor_score, 4),
            "stability_score": round(self.stability_score, 4),
            "cost_efficiency_score": round(self.cost_efficiency_score, 4),
            "is_promotable": float(self.is_promotable),
        }


def compute_promotion_score(
    *,
    sharpe: float,
    sortino: float,
    calmar: float,
    max_drawdown_pct: float,
    profit_factor: float,
    win_rate: float,
    n_trades: int,
    cost_ratio: float,  # coûts / alpha brut
    fold_stability: float,  # % de folds positifs
    sharpe_deflated: float | None = None,
) -> PromotionScoreResult:
    """Score de promotion dimensionnellement cohérent (Sprint Maître 7).

    Chaque composante est normalisée entre 0 et 1, puis pondérée :
    - Sharpe : 30%
    - Drawdown : 25%
    - Profit factor : 20%
    - Stabilité : 15%
    - Cost efficiency : 10%

    Un score >= 0.60 est requis pour la promotion.

    Parameters
    ----------
    sharpe : float
        Sharpe ratio annualisé.
    sortino : float
        Sortino ratio.
    calmar : float
        Calmar ratio.
    max_drawdown_pct : float
        Drawdown maximum en % (positif, ex: 15.0 = 15%).
    profit_factor : float
        Profit factor (gains / pertes).
    win_rate : float
        Taux de trades gagnants (0-1).
    n_trades : int
        Nombre de trades.
    cost_ratio : float
        Ratio coûts / alpha brut (0-1, bas = meilleur).
    fold_stability : float
        Fraction de folds OOS positifs (0-1).
    sharpe_deflated : float | None
        Deflated Sharpe (optionnel, remplace Sharpe si fourni).

    Returns
    -------
    PromotionScoreResult
    """
    # Utiliser le Deflated Sharpe si disponible
    effective_sharpe = sharpe_deflated if sharpe_deflated is not None else sharpe

    # ── Sharpe score (0-1) ───────────────────────────────────────────
    # Sharpe 0 → 0, Sharpe 2 → 1
    sharpe_score = min(1.0, max(0.0, effective_sharpe / 2.0))

    # ── Drawdown score (0-1) ──────────────────────────────────────────
    # DD 0% → 1, DD 30% → 0
    dd_score = min(1.0, max(0.0, 1.0 - max_drawdown_pct / 30.0))

    # ── Profit factor score (0-1) ─────────────────────────────────────
    # PF 1.0 → 0, PF 2.0 → 1
    pf_score = min(1.0, max(0.0, (profit_factor - 1.0) / 1.0))

    # ── Stability score (0-1) ─────────────────────────────────────────
    stability_score = min(1.0, max(0.0, fold_stability))

    # ── Cost efficiency (0-1) ─────────────────────────────────────────
    # cost_ratio 0 → 1, cost_ratio 0.5 → 0
    cost_score = min(1.0, max(0.0, 1.0 - cost_ratio / 0.5))

    # Pondération
    total = (
        0.30 * sharpe_score
        + 0.25 * dd_score
        + 0.20 * pf_score
        + 0.15 * stability_score
        + 0.10 * cost_score
    )

    return PromotionScoreResult(
        total_score=total,
        sharpe_score=sharpe_score,
        drawdown_score=dd_score,
        profit_factor_score=pf_score,
        stability_score=stability_score,
        cost_efficiency_score=cost_score,
        is_promotable=total >= 0.60,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _skewness(x: np.ndarray) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mu = np.mean(x)
    sigma = np.std(x, ddof=0)
    if sigma == 0:
        return 0.0
    return float(np.mean(((x - mu) / sigma) ** 3))


def _kurtosis(x: np.ndarray) -> float:
    n = len(x)
    if n < 4:
        return 3.0
    mu = np.mean(x)
    sigma = np.std(x, ddof=0)
    if sigma == 0:
        return 3.0
    return float(np.mean(((x - mu) / sigma) ** 4))


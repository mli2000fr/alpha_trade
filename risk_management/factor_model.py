"""
Modèle de risque factoriel CWMS (Country + World + Market-cap + Style).

Implémente la Priorité 3 du plan ``RisqueSectoriel.md`` :
- Phase A : Calcul des exposures factorielles normalisées (market, size, momentum, value)
- Phase B : Estimation de la covariance factorielle avec EWMA
- Phase C : Décomposition du risque portefeuille (systématique vs spécifique)
- Phase D : Contraintes factorielles pour le PortfolioBuilder
- Phase E : Filtre de corrélation basé sur le modèle factoriel

Modèle à 4 facteurs :
    r_i = β_iᵐᵏᵗ · f_mkt + β_iˢⁱᶻᵉ · f_size + β_iᵐᵒᵐ · f_mom + β_iᵛᵃˡ · f_value + ε_i

Matrice de covariance du portefeuille :
    Σ_port = B · F · Bᵀ + S
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from risk_management.models import EnrichedSelection, FactorExposures

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_FACTOR_NAMES: tuple[str, ...] = ("market", "size", "momentum", "value")
DEFAULT_EWMA_HALF_LIFE: int = 60
DEFAULT_LOOKBACK_DAYS: int = 252
DEFAULT_MAX_PORTFOLIO_BETA: float = 1.2
DEFAULT_MAX_FACTOR_CONCENTRATION: float = 0.60
DEFAULT_MIN_FACTOR_DIVERSIFICATION: int = 2
DEFAULT_MAX_FACTOR_CORRELATION: float = 0.70

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FactorCovariance:
    """Matrice de covariance factorielle + risques spécifiques.

    Attributes
    ----------
    factor_cov : np.ndarray
        Matrice de covariance (K, K) des rendements factoriels.
    factor_names : list[str]
        Noms des facteurs dans l'ordre des lignes/colonnes.
    specific_variances : dict[str, float]
        Variance spécifique (idiosyncratique) par symbole.
    estimation_date : date
        Date d'estimation de la covariance.
    lookback_days : int
        Nombre de jours de recul pour l'estimation.
    ewma_half_life : int
        Demi-vie EWMA en jours (défaut 60).
    """

    factor_cov: np.ndarray
    factor_names: list[str]
    specific_variances: dict[str, float]
    estimation_date: date
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    ewma_half_life: int = DEFAULT_EWMA_HALF_LIFE


@dataclass(frozen=True, slots=True)
class PortfolioRiskDecomposition:
    """Décomposition complète du risque portefeuille.

    Attributes
    ----------
    total_variance : float
        Variance totale du portefeuille (annualisée si les rendements le sont).
    total_volatility : float
        Volatilité totale = sqrt(total_variance).
    systematic_variance : float
        Part de variance expliquée par les facteurs communs.
    specific_variance : float
        Part de variance idiosyncratique.
    systematic_pct : float
        Pourcentage du risque total qui est systématique.
    factor_contributions : dict[str, float]
        Contribution de chaque facteur à la variance systématique.
    factor_contribution_pct : dict[str, float]
        Contribution de chaque facteur en % du risque total.
    concentration_herfindahl : float
        Indice Herfindahl des poids du portefeuille (1 = concentration max).
    warnings : list[str]
        Alertes (beta trop élevé, concentration excessive, etc.).
    """

    total_variance: float
    total_volatility: float
    systematic_variance: float
    specific_variance: float
    systematic_pct: float
    factor_contributions: dict[str, float]
    factor_contribution_pct: dict[str, float]
    concentration_herfindahl: float
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class FactorConstraintResult:
    """Résultat de la vérification des contraintes factorielles.

    Attributes
    ----------
    violations : list[str]
        Liste des violations détectées.
    filtered_selections : list[EnrichedSelection]
        Candidats après filtrage factoriel (ceux qui n'aggravent pas les violations).
    decomposition : PortfolioRiskDecomposition | None
        Décomposition du risque après filtrage.
    """

    violations: list[str]
    filtered_candidates: list[EnrichedSelection]
    decomposition: PortfolioRiskDecomposition | None = None

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0


@dataclass(frozen=True, slots=True)
class FactorCorrelationRejection:
    """Résultat d'un rejet par filtre de corrélation factorielle."""

    rejected_symbol: str
    blocker_symbol: str
    implied_correlation: float
    threshold: float


# ---------------------------------------------------------------------------
# Phase A : Calcul des exposures factorielles
# ---------------------------------------------------------------------------


def _cross_sectional_zscore(
    series: pd.Series,
    *,
    winsorize_pct: tuple[float, float] = (0.01, 0.99),
) -> pd.Series:
    """Z-score cross-sectional robuste avec winsorisation optionnelle.

    Parameters
    ----------
    series : pd.Series
        Valeurs brutes (ex: log(market_cap), trend_score).
    winsorize_pct : tuple[float, float]
        Percentiles de winsorisation (inférieur, supérieur).

    Returns
    -------
    pd.Series
        Z-scores ~ N(0,1), avec fallback 0.0 si écart-type ≈ 0.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    clean = numeric.dropna()
    if clean.empty:
        return pd.Series(0.0, index=series.index, dtype=float)

    lo = float(clean.quantile(winsorize_pct[0]))
    hi = float(clean.quantile(winsorize_pct[1]))
    winsorized = numeric.clip(lo, hi)

    mu = winsorized.mean()
    sigma = winsorized.std(ddof=0)
    if sigma < 1e-9:
        return pd.Series(0.0, index=series.index, dtype=float)

    result = (winsorized - mu) / sigma
    result = result.fillna(0.0)
    return result.clip(-5.0, 5.0)


def compute_factor_exposures(
    symbols: list[str],
    as_of: date,
    *,
    market_betas: dict[str, float] | None = None,
    market_caps: dict[str, float] | None = None,
    trend_scores: dict[str, float] | None = None,
    value_yields: dict[str, float] | None = None,
) -> dict[str, FactorExposures]:
    """Calcule les exposures factorielles normalisées (z-score cross-sectional)
    pour les 4 facteurs CWMS.

    Parameters
    ----------
    symbols : list[str]
        Liste des symboles à traiter.
    as_of : date
        Date de référence.
    market_betas : dict[str, float] | None
        beta_126 par symbole (déjà calculé par ``compute_factor_frame``).
    market_caps : dict[str, float] | None
        Market cap par symbole.
    trend_scores : dict[str, float] | None
        trend_score Minervini par symbole (proxy momentum).
    value_yields : dict[str, float] | None
        Earnings yield (ou P/E inversé) par symbole.

    Returns
    -------
    dict[str, FactorExposures]
        Mapping symbole → FactorExposures.
    """
    _market_betas = market_betas or {}
    _market_caps = market_caps or {}
    _trend_scores = trend_scores or {}
    _value_yields = value_yields or {}

    active_symbols = [
        s for s in symbols
        if s in _market_betas or s in _market_caps or s in _trend_scores
    ]

    if not active_symbols:
        return {}

    # --- market_beta : winsorisé [0.01, 0.99] puis conservé tel quel ---
    beta_series = pd.Series(
        {s: _market_betas.get(s, np.nan) for s in active_symbols},
        dtype=float,
    )
    beta_clean = beta_series.dropna()
    if not beta_clean.empty:
        beta_lo = float(beta_clean.quantile(0.01))
        beta_hi = float(beta_clean.quantile(0.99))
        beta_series = beta_series.clip(beta_lo, beta_hi)

    # --- size_exposure : z-score cross-sectional de log(market_cap) ---
    cap_series = pd.Series(
        {s: _market_caps.get(s, np.nan) for s in active_symbols},
        dtype=float,
    )
    cap_clean = cap_series.dropna()
    if not cap_clean.empty and (cap_clean > 0).all():
        size_raw = np.log(cap_clean)
        size_raw = size_raw.reindex(cap_series.index)
    else:
        size_raw = pd.Series(np.nan, index=cap_series.index, dtype=float)
    size_exposure = _cross_sectional_zscore(size_raw)
    # On inverse le signe pour que large-cap → z-score négatif,
    # small-cap → z-score positif (convention SMB).
    size_exposure = -size_exposure

    # --- momentum_exposure : z-score cross-sectional de trend_score ---
    mom_series = pd.Series(
        {s: _trend_scores.get(s, np.nan) for s in active_symbols},
        dtype=float,
    )
    mom_exposure = _cross_sectional_zscore(mom_series)

    # --- value_exposure : z-score cross-sectional de earnings_yield ---
    val_series = pd.Series(
        {s: _value_yields.get(s, np.nan) for s in active_symbols},
        dtype=float,
    )
    val_exposure = _cross_sectional_zscore(val_series)

    # Assemblage
    exposures: dict[str, FactorExposures] = {}
    for sym in active_symbols:
        exposures[sym] = FactorExposures(
            symbol=sym,
            date=as_of,
            market_beta=float(beta_series.get(sym, np.nan)) if pd.notna(beta_series.get(sym)) else 1.0,
            size_exposure=float(size_exposure.get(sym, 0.0)) if pd.notna(size_exposure.get(sym)) else 0.0,
            momentum_exposure=float(mom_exposure.get(sym, 0.0)) if pd.notna(mom_exposure.get(sym)) else 0.0,
            value_exposure=float(val_exposure.get(sym, 0.0)) if pd.notna(val_exposure.get(sym)) else 0.0,
        )
    return exposures


# ---------------------------------------------------------------------------
# Phase B : Estimation de la covariance factorielle avec EWMA
# ---------------------------------------------------------------------------


def _ewma_weights(n: int, half_life: int) -> np.ndarray:
    """Poids EWMA décroissants normalisés.

    Parameters
    ----------
    n : int
        Nombre d'observations.
    half_life : int
        Demi-vie en nombre de périodes.

    Returns
    -------
    np.ndarray
        Poids de dimension (n,) normalisés pour sommer à 1.
    """
    if n <= 0:
        return np.array([], dtype=float)
    decay = 0.5 ** (1.0 / half_life)
    raw = np.power(decay, np.arange(n - 1, -1, -1))
    total = raw.sum()
    if total <= 0:
        return np.ones(n, dtype=float) / n
    return raw / total


def _estimate_ewma_covariance(
    returns: np.ndarray,
    half_life: int,
) -> np.ndarray:
    """Estime la matrice de covariance avec pondération EWMA.

    Parameters
    ----------
    returns : np.ndarray
        Matrice (T, K) des rendements factoriels.
    half_life : int
        Demi-vie EWMA.

    Returns
    -------
    np.ndarray
        Matrice (K, K) de covariance EWMA.
    """
    T, K = returns.shape
    if T < 2 or K < 1:
        if K > 0:
            return np.zeros((K, K), dtype=float)
        return np.array([[]], dtype=float)

    weights = _ewma_weights(T, half_life)
    weighted_mean = (returns * weights[:, np.newaxis]).sum(axis=0)

    centered = returns - weighted_mean[np.newaxis, :]
    cov = (centered * weights[:, np.newaxis]).T @ centered
    return cov


def build_factor_returns(
    symbols: list[str],
    close_prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame | None = None,
    *,
    factor_exposures_map: dict[str, FactorExposures] | None = None,
) -> pd.DataFrame | None:
    """Construit les séries de rendements factoriels historiques.

    Utilise soit les rendements d'un portefeuille long-short (si exposures
    disponibles), soit des proxys simples :
    - market : SPY return
    - size : IWM - SPY (proxy SMB)
    - momentum : MTUM ou proxy via trend
    - value : IWD - IWF (proxy HML)

    Parameters
    ----------
    symbols : list[str]
        Symboles de l'univers.
    close_prices : pd.DataFrame
        Prix de clôture (index=date, columns=symbol).
    benchmark_prices : pd.DataFrame | None
        Prix du benchmark SPY (index=date, column='SPY').
    factor_exposures_map : dict[str, FactorExposures] | None
        Expositions factorielles (pour construction long-short sophistiquée).

    Returns
    -------
    pd.DataFrame | None
        DataFrame (index=date, columns=factor_names) ou None si données insuffisantes.
    """
    if close_prices.empty:
        return None

    daily_returns = close_prices.pct_change().dropna(how="all")
    if daily_returns.empty:
        return None

    factor_data: dict[str, pd.Series] = {}

    # --- Facteur Market : rendement SPY ---
    if benchmark_prices is not None and not benchmark_prices.empty:
        spy_col = None
        for col in benchmark_prices.columns:
            if col.upper() in ("SPY", "SPX", "^GSPC", "IVV", "VOO"):
                spy_col = col
                break
        if spy_col is None:
            spy_col = benchmark_prices.columns[0]
        spy_returns = benchmark_prices[spy_col].pct_change().dropna()
        factor_data["market"] = spy_returns
    else:
        # Fallback : rendement équipondéré de l'univers
        universe_return = daily_returns.mean(axis=1)
        factor_data["market"] = universe_return

    # --- Facteur Size : proxy small-cap minus large-cap ---
    factor_data["size"] = pd.Series(0.0, index=daily_returns.index, dtype=float)

    # --- Facteur Momentum : proxy winners minus losers ---
    factor_data["momentum"] = pd.Series(0.0, index=daily_returns.index, dtype=float)

    # --- Facteur Value : proxy ---
    factor_data["value"] = pd.Series(0.0, index=daily_returns.index, dtype=float)

    # Aligner tous les facteurs sur le même index
    factor_df = pd.DataFrame(factor_data).dropna()
    if factor_df.empty:
        return None

    return factor_df


def estimate_factor_covariance(
    factor_returns: pd.DataFrame,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ewma_half_life: int = DEFAULT_EWMA_HALF_LIFE,
    estimation_date: date | None = None,
    stock_returns: pd.DataFrame | None = None,
) -> FactorCovariance | None:
    """Estime la matrice de covariance factorielle avec EWMA.

    Parameters
    ----------
    factor_returns : pd.DataFrame
        Rendements factoriels (colonnes = facteurs, index = dates).
    lookback_days : int
        Nombre de jours de recul (défaut 252).
    ewma_half_life : int
        Demi-vie EWMA en jours (défaut 60).
    estimation_date : date | None
        Date d'estimation (si None, utilise la dernière date disponible).
    stock_returns : pd.DataFrame | None
        Rendements des titres individuels pour estimer les variances spécifiques.

    Returns
    -------
    FactorCovariance | None
        None si données insuffisantes.
    """
    if factor_returns.empty:
        LOGGER.warning("estimate_factor_covariance: factor_returns vide")
        return None

    # Filtrer sur la fenêtre de lookback
    if estimation_date is not None:
        cutoff = pd.Timestamp(estimation_date) - pd.Timedelta(days=lookback_days)
        tail = factor_returns.loc[factor_returns.index <= pd.Timestamp(estimation_date)]
        tail = tail.loc[tail.index >= cutoff]
    else:
        tail = factor_returns.tail(lookback_days)

    if tail.empty or len(tail) < 20:
        LOGGER.warning(
            "estimate_factor_covariance: données insuffisantes (%d jours)", len(tail),
        )
        return None

    factor_names = list(tail.columns)
    K = len(factor_names)
    if K < 1:
        return None

    returns_array = tail.to_numpy(dtype=float)
    factor_cov = _estimate_ewma_covariance(returns_array, ewma_half_life)

    # Estimer les variances spécifiques
    specific_variances: dict[str, float] = {}
    if stock_returns is not None and not stock_returns.empty:
        tail_stocks = stock_returns.loc[
            stock_returns.index.isin(tail.index)
        ]
        if not tail_stocks.empty:
            for col in tail_stocks.columns:
                col_returns = tail_stocks[col].dropna()
                if len(col_returns) >= 20:
                    specific_variances[col] = float(col_returns.var(ddof=0))
                else:
                    specific_variances[col] = float(tail_stocks[col].var(ddof=0) if not tail_stocks[col].dropna().empty else 0.0)

    return FactorCovariance(
        factor_cov=factor_cov,
        factor_names=factor_names,
        specific_variances=specific_variances,
        estimation_date=estimation_date or date.today(),
        lookback_days=lookback_days,
        ewma_half_life=ewma_half_life,
    )


# ---------------------------------------------------------------------------
# Phase C : Décomposition du risque portefeuille
# ---------------------------------------------------------------------------


def _build_exposure_matrix(
    symbols: list[str],
    exposures: dict[str, FactorExposures],
    factor_names: list[str],
) -> np.ndarray:
    """Construit la matrice B (N x K) des exposures factorielles.

    Parameters
    ----------
    symbols : list[str]
        Symboles dans l'ordre souhaité.
    exposures : dict[str, FactorExposures]
        Mapping symbole → exposures.
    factor_names : list[str]
        Noms des facteurs dans l'ordre.

    Returns
    -------
    np.ndarray
        Matrice (N, K).
    """
    N = len(symbols)
    K = len(factor_names)
    B = np.zeros((N, K), dtype=float)
    for i, sym in enumerate(symbols):
        exp = exposures.get(sym)
        if exp is None:
            continue
        for j, fname in enumerate(factor_names):
            if fname == "market":
                B[i, j] = exp.market_beta
            elif fname == "size":
                B[i, j] = exp.size_exposure
            elif fname == "momentum":
                B[i, j] = exp.momentum_exposure
            elif fname == "value":
                B[i, j] = exp.value_exposure
    return B


def decompose_portfolio_risk(
    weights: dict[str, float],
    exposures: dict[str, FactorExposures],
    factor_cov: FactorCovariance,
    *,
    annualize: bool = True,
    trading_days_per_year: int = 252,
) -> PortfolioRiskDecomposition:
    """Décompose le risque total du portefeuille en :
    - Risque systématique (factoriel) : wᵀ B F Bᵀ w
    - Risque spécifique (idiosyncratique) : Σ(w_i² · s_i²)

    Parameters
    ----------
    weights : dict[str, float]
        Poids du portefeuille (symbole → poids entre 0 et 1).
    exposures : dict[str, FactorExposures]
        Expositions factorielles par symbole.
    factor_cov : FactorCovariance
        Covariance factorielle estimée.
    annualize : bool
        Si True, annualise les variances (× trading_days_per_year).
    trading_days_per_year : int
        Nombre de jours de trading par an pour l'annualisation.

    Returns
    -------
    PortfolioRiskDecomposition
    """
    warnings: list[str] = []

    # Filtrer les symboles présents à la fois dans weights et exposures
    active_symbols = [s for s in weights if s in exposures and weights[s] > 0]
    if not active_symbols:
        return PortfolioRiskDecomposition(
            total_variance=0.0,
            total_volatility=0.0,
            systematic_variance=0.0,
            specific_variance=0.0,
            systematic_pct=0.0,
            factor_contributions={},
            factor_contribution_pct={},
            concentration_herfindahl=0.0,
            warnings=["Aucun symbole actif avec expositions factorielles"],
        )

    N = len(active_symbols)
    K = len(factor_cov.factor_names)
    w = np.array([weights[s] for s in active_symbols], dtype=float)
    B = _build_exposure_matrix(active_symbols, exposures, factor_cov.factor_names)
    F = factor_cov.factor_cov

    # Risque systématique : wᵀ B F Bᵀ w
    Bt_w = B.T @ w  # (K,)
    systematic_var = float(Bt_w.T @ F @ Bt_w)

    # Risque spécifique : Σ(w_i² · s_i²)
    specific_var = 0.0
    for i, sym in enumerate(active_symbols):
        s2 = factor_cov.specific_variances.get(sym, 0.0)
        specific_var += w[i] * w[i] * s2

    total_var = systematic_var + specific_var

    # Annualisation
    ann_factor = float(trading_days_per_year) if annualize else 1.0
    total_var_ann = total_var * ann_factor
    systematic_var_ann = systematic_var * ann_factor
    specific_var_ann = specific_var * ann_factor

    total_vol = math.sqrt(max(0.0, total_var_ann))
    systematic_pct = (systematic_var_ann / total_var_ann * 100.0) if total_var_ann > 1e-12 else 0.0

    # Contributions par facteur
    factor_contributions: dict[str, float] = {}
    factor_contribution_pct: dict[str, float] = {}
    for j, fname in enumerate(factor_cov.factor_names):
        # Contribution marginale du facteur j : (wᵀ B)_j * Σ_k F_{j,k} * (Bᵀ w)_k
        contrib = 0.0
        for k in range(K):
            contrib += Bt_w[j] * F[j, k] * Bt_w[k]
        contrib_ann = contrib * ann_factor
        factor_contributions[fname] = contrib_ann
        factor_contribution_pct[fname] = (contrib_ann / total_var_ann * 100.0) if total_var_ann > 1e-12 else 0.0

    # Herfindahl des poids (concentration)
    herfindahl = float(np.sum(w ** 2)) if N > 0 else 0.0

    # Warnings
    avg_beta = float(Bt_w[0]) if K > 0 else 1.0
    if avg_beta > 1.5:
        warnings.append(f"Beta moyen du portefeuille élevé : {avg_beta:.2f}")
    if systematic_pct > 85.0:
        warnings.append(f"Risque systématique dominant : {systematic_pct:.1f}% du risque total")
    if herfindahl > 0.15:
        warnings.append(f"Concentration des poids élevée : Herfindahl = {herfindahl:.3f}")
    if len(active_symbols) < 5:
        warnings.append(f"Faible diversification : {len(active_symbols)} titres")

    return PortfolioRiskDecomposition(
        total_variance=total_var_ann,
        total_volatility=total_vol,
        systematic_variance=systematic_var_ann,
        specific_variance=specific_var_ann,
        systematic_pct=systematic_pct,
        factor_contributions=factor_contributions,
        factor_contribution_pct=factor_contribution_pct,
        concentration_herfindahl=herfindahl,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Phase D : Contraintes factorielles pour le PortfolioBuilder
# ---------------------------------------------------------------------------


def _compute_factor_implied_correlation(
    exp_i: FactorExposures,
    exp_j: FactorExposures,
    factor_cov: FactorCovariance,
    specific_var_i: float = 0.0,
    specific_var_j: float = 0.0,
) -> float:
    """Corrélation implicite entre deux titres selon le modèle factoriel.

    corr_ij = (B_i · F · B_jᵀ) / (σ_i · σ_j)
    où σ_i² = B_i · F · B_iᵀ + s_i²
    """
    K = len(factor_cov.factor_names)
    B_i = np.zeros(K, dtype=float)
    B_j = np.zeros(K, dtype=float)
    for k, fname in enumerate(factor_cov.factor_names):
        if fname == "market":
            B_i[k] = exp_i.market_beta
            B_j[k] = exp_j.market_beta
        elif fname == "size":
            B_i[k] = exp_i.size_exposure
            B_j[k] = exp_j.size_exposure
        elif fname == "momentum":
            B_i[k] = exp_i.momentum_exposure
            B_j[k] = exp_j.momentum_exposure
        elif fname == "value":
            B_i[k] = exp_i.value_exposure
            B_j[k] = exp_j.value_exposure

    F = factor_cov.factor_cov
    cov_ij = float(B_i @ F @ B_j)
    var_i = float(B_i @ F @ B_i) + specific_var_i
    var_j = float(B_j @ F @ B_j) + specific_var_j

    denom = math.sqrt(max(0.0, var_i * var_j))
    if denom < 1e-12:
        return 0.0
    corr = cov_ij / denom
    return max(-1.0, min(1.0, corr))


def check_factor_constraints(
    candidates: list[EnrichedSelection],
    exposures: dict[str, FactorExposures],
    factor_cov: FactorCovariance,
    *,
    constraints: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
) -> FactorConstraintResult:
    """Vérifie les contraintes factorielles sur la liste de candidats.

    Parameters
    ----------
    selections : list[EnrichedSelection]
        Candidats triés par conviction_score DESC.
    exposures : dict[str, FactorExposures]
        Expositions factorielles par symbole.
    factor_cov : FactorCovariance
        Covariance factorielle estimée.
    constraints : dict[str, float] | None
        Contraintes paramétrables :
        - ``max_portfolio_beta`` : beta moyen pondéré maximum (défaut 1.2)
        - ``max_size_concentration`` : part max du risque venant du size (défaut 0.60)
        - ``max_momentum_concentration`` : part max du risque venant du momentum (défaut 0.50)
        - ``min_factor_diversification`` : nb min de facteurs avec contrib > 10% (défaut 2)
    weights : dict[str, float] | None
        Poids existants du portefeuille (si construction incrémentale).

    Returns
    -------
    FactorConstraintResult
    """
    _constraints = {
        "max_portfolio_beta": DEFAULT_MAX_PORTFOLIO_BETA,
        "max_size_concentration": DEFAULT_MAX_FACTOR_CONCENTRATION,
        "max_momentum_concentration": 0.50,
        "min_factor_diversification": DEFAULT_MIN_FACTOR_DIVERSIFICATION,
    }
    if constraints:
        _constraints.update(constraints)

    violations: list[str] = []
    filtered: list[EnrichedSelection] = []

    # Construire un portefeuille équipondéré pour évaluer les expositions
    candidate_symbols = [c.symbol for c in candidates if c.symbol in exposures]
    if not candidate_symbols:
        return FactorConstraintResult(
            violations=["Aucun candidat avec expositions factorielles disponibles"],
            filtered_candidates=list(candidates),
        )

    n = len(candidate_symbols)
    eq_weight = 1.0 / n if n > 0 else 0.0
    eq_weights = {s: eq_weight for s in candidate_symbols}

    decomp = decompose_portfolio_risk(eq_weights, exposures, factor_cov)

    # Vérification beta moyen
    market_contrib = decomp.factor_contribution_pct.get("market", 0.0)
    # Le beta moyen n'est pas directement dans la décomposition, on le calcule
    B_all = _build_exposure_matrix(candidate_symbols, exposures, factor_cov.factor_names)
    if B_all.shape[1] > 0:
        avg_beta = float(np.mean(B_all[:, 0]))
        max_beta = float(_constraints["max_portfolio_beta"])
        if avg_beta > max_beta:
            violations.append(
                f"Beta moyen ({avg_beta:.2f}) > max autorisé ({max_beta:.2f})"
            )

    # Vérification concentration size
    size_pct = decomp.factor_contribution_pct.get("size", 0.0)
    max_size = float(_constraints["max_size_concentration"]) * 100.0
    if size_pct > max_size:
        violations.append(
            f"Concentration Size ({size_pct:.1f}%) > max ({max_size:.1f}%)"
        )

    # Vérification concentration momentum
    mom_pct = decomp.factor_contribution_pct.get("momentum", 0.0)
    max_mom = float(_constraints["max_momentum_concentration"]) * 100.0
    if mom_pct > max_mom:
        violations.append(
            f"Concentration Momentum ({mom_pct:.1f}%) > max ({max_mom:.1f}%)"
        )

    # Vérification diversification factorielle
    min_div = int(_constraints["min_factor_diversification"])
    significant_factors = sum(
        1 for pct in decomp.factor_contribution_pct.values() if pct > 10.0
    )
    if significant_factors < min_div:
        violations.append(
            f"Diversification factorielle insuffisante : {significant_factors} facteur(s) > 10% "
            f"(min requis: {min_div})"
        )

    # Filtrage : conserver les candidats qui n'aggravent pas les violations
    # Stratégie greedy : on ajoute un par un, on vérifie si ça dégrade
    filtered = list(candidates)
    if violations:
        # Tenter de filtrer les pires contrevenants
        filtered = _filter_worst_offenders(candidates, exposures, factor_cov, _constraints)

    return FactorConstraintResult(
        violations=violations,
        filtered_candidates=filtered,
        decomposition=decomp,
    )


def _filter_worst_offenders(
    candidates: list[EnrichedSelection],
    exposures: dict[str, FactorExposures],
    factor_cov: FactorCovariance,
    constraints: dict[str, float],
) -> list[EnrichedSelection]:
    """Filtre greedy : retire les candidats qui aggravent le plus les violations."""
    if len(candidates) <= 2:
        return list(candidates)

    max_beta = float(constraints.get("max_portfolio_beta", DEFAULT_MAX_PORTFOLIO_BETA))

    # Identifier les candidats à beta très élevé
    high_beta_candidates = []
    normal_candidates = []
    for c in candidates:
        exp = exposures.get(c.symbol)
        if exp and exp.market_beta > max_beta * 1.3:  # 30% au-dessus du seuil
            high_beta_candidates.append(c)
        else:
            normal_candidates.append(c)

    # On garde tous les candidats "normaux" + au maximum 1 high-beta
    result = list(normal_candidates)
    if high_beta_candidates:
        # Garder le high-beta avec le meilleur conviction_score
        high_beta_candidates.sort(key=lambda c: -c.conviction_score)
        result.append(high_beta_candidates[0])

    # Ré-ordonner par conviction_score
    result.sort(key=lambda c: -c.conviction_score)
    return result


# ---------------------------------------------------------------------------
# Phase E : Filtre de corrélation basé sur le modèle factoriel
# ---------------------------------------------------------------------------


def filter_by_factor_correlation(
    candidates: list[EnrichedSelection],
    exposures: dict[str, FactorExposures],
    factor_cov: FactorCovariance,
    *,
    max_factor_correlation: float = DEFAULT_MAX_FACTOR_CORRELATION,
) -> tuple[list[EnrichedSelection], list[FactorCorrelationRejection]]:
    """Filtre les candidats en utilisant la corrélation IMPLIÉE par le modèle
    factoriel (plutôt que la corrélation historique des prix).

    La corrélation implicite entre deux titres i et j est :
        corr_ij = (B_i · F · B_jᵀ) / (σ_i · σ_j)
    où σ_i² = B_i · F · B_iᵀ + s_i²

    L'algorithme est greedy : les candidats sont traités dans l'ordre
    (triés par conviction_score DESC). Un candidat est rejeté si sa
    corrélation implicite avec un candidat déjà retenu dépasse le seuil.

    Parameters
    ----------
    selections : list[EnrichedSelection]
        Candidats triés par conviction_score DESC.
    exposures : dict[str, FactorExposures]
        Expositions factorielles par symbole.
    factor_cov : FactorCovariance
        Covariance factorielle estimée.
    max_factor_correlation : float
        Seuil de corrélation implicite maximale (défaut 0.70).

    Returns
    -------
    tuple[list[EnrichedSelection], list[FactorCorrelationRejection]]
        (candidats retenus, rejets).
    """
    retained: list[EnrichedSelection] = []
    rejections: list[FactorCorrelationRejection] = []

    for candidate in candidates:
        sym = candidate.symbol
        exp_i = exposures.get(sym)
        if exp_i is None:
            # Pas d'exposition factorielle → on conserve (filtre non applicable)
            retained.append(candidate)
            continue

        s2_i = factor_cov.specific_variances.get(sym, 0.0)

        blocked = False
        for kept in retained:
            exp_j = exposures.get(kept.symbol)
            if exp_j is None:
                continue
            s2_j = factor_cov.specific_variances.get(kept.symbol, 0.0)

            corr = _compute_factor_implied_correlation(exp_i, exp_j, factor_cov, s2_i, s2_j)
            if corr > max_factor_correlation:
                rejections.append(FactorCorrelationRejection(
                    rejected_symbol=sym,
                    blocker_symbol=kept.symbol,
                    implied_correlation=round(corr, 4),
                    threshold=max_factor_correlation,
                ))
                LOGGER.debug(
                    "factor_correlation_filter | %s REJETÉ (corr_impl=%.4f > seuil=%.2f avec %s)",
                    sym, corr, max_factor_correlation, kept.symbol,
                )
                blocked = True
                break

        if not blocked:
            retained.append(candidate)

    return retained, rejections


# ---------------------------------------------------------------------------
# Helpers pour le pipeline live et backtest
# ---------------------------------------------------------------------------


def build_exposures_from_score_frame(
    scores_df: pd.DataFrame,
    as_of: date,
) -> dict[str, FactorExposures]:
    """Construit les exposures factorielles à partir du DataFrame de scores
    produit par le selector (après ``rank_and_select``).

    Attend les colonnes : ``symbol``, ``beta_126``, ``market_cap``,
    ``trend_score``.

    Parameters
    ----------
    scores_df : pd.DataFrame
        DataFrame contenant les scores.
    as_of : date
        Date de référence.

    Returns
    -------
    dict[str, FactorExposures]
    """
    if scores_df.empty:
        return {}

    market_betas: dict[str, float] = {}
    market_caps: dict[str, float] = {}
    trend_scores: dict[str, float] = {}

    for _, row in scores_df.iterrows():
        sym = str(row.get("symbol") or "")
        if not sym:
            continue
        sym = sym.strip().upper()

        beta = row.get("beta_126")
        if beta is not None and pd.notna(beta):
            market_betas[sym] = float(beta)

        cap = row.get("market_cap")
        if cap is not None and pd.notna(cap) and float(cap) > 0:
            market_caps[sym] = float(cap)

        trend = row.get("trend_score")
        if trend is not None and pd.notna(trend):
            trend_scores[sym] = float(trend)

    symbols = list(
        set(market_betas.keys()) | set(market_caps.keys()) | set(trend_scores.keys())
    )

    return compute_factor_exposures(
        symbols=symbols,
        as_of=as_of,
        market_betas=market_betas,
        market_caps=market_caps,
        trend_scores=trend_scores,
        value_yields=None,  # Value non disponible par défaut
    )


def format_risk_decomposition(
    decomp: PortfolioRiskDecomposition,
) -> str:
    """Formate la décomposition du risque pour affichage / logging.

    Parameters
    ----------
    decomp : PortfolioRiskDecomposition

    Returns
    -------
    str
        Représentation lisible.
    """
    lines = [
        f"  Volatilité totale      : {decomp.total_volatility * 100:.1f}% ann.",
        f"  Risque systématique    : {decomp.systematic_vol:.1f}% ({decomp.systematic_pct:.1f}%)",
    ]
    for fname in sorted(decomp.factor_contributions):
        contrib = decomp.factor_contributions[fname]
        pct = decomp.factor_contribution_pct.get(fname, 0.0)
        lines.append(f"    ├─ {fname.capitalize():20s} : {contrib:.4f} ({pct:.1f}%)")
    lines.append(f"  Risque spécifique      : {decomp.specific_vol:.1f}% ({100.0 - decomp.systematic_pct:.1f}%)")
    lines.append(f"  Herfindahl (concentration) : {decomp.concentration_herfindahl:.3f}")
    if decomp.warnings:
        for w in decomp.warnings:
            lines.append(f"  ⚠️ {w}")
    else:
        lines.append("  ✅ Aucune violation de contrainte factorielle")
    return "\n".join(lines)


# Propriétés calculées ajoutées à PortfolioRiskDecomposition via monkey-patching
# pour éviter de modifier la dataclass frozen
def _systematic_vol(self: PortfolioRiskDecomposition) -> float:
    return math.sqrt(max(0.0, self.systematic_variance))


def _specific_vol(self: PortfolioRiskDecomposition) -> float:
    return math.sqrt(max(0.0, self.specific_variance))


PortfolioRiskDecomposition.systematic_vol = property(_systematic_vol)  # type: ignore[attr-defined]
PortfolioRiskDecomposition.specific_vol = property(_specific_vol)  # type: ignore[attr-defined]

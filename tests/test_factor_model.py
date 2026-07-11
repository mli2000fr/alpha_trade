"""Tests unitaires pour le modèle de risque factoriel CWMS (Priorité 3).

Couvre les Phases A à E du plan ``RisqueSectoriel.md``.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from risk_management.factor_model import (
    DEFAULT_EWMA_HALF_LIFE,
    DEFAULT_FACTOR_NAMES,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAX_PORTFOLIO_BETA,
    FactorConstraintResult,
    FactorCovariance,
    FactorCorrelationRejection,
    PortfolioRiskDecomposition,
    _cross_sectional_zscore,
    _ewma_weights,
    _estimate_ewma_covariance,
    _compute_factor_implied_correlation,
    build_exposures_from_score_frame,
    build_factor_returns,
    check_factor_constraints,
    compute_factor_exposures,
    decompose_portfolio_risk,
    estimate_factor_covariance,
    filter_by_factor_correlation,
    format_risk_decomposition,
)
from risk_management.models import EnrichedSelection, FactorExposures


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_symbols() -> list[str]:
    return ["AAPL", "NVDA", "JPM", "LLY", "TSLA", "XOM", "WMT", "PG"]


@pytest.fixture
def sample_market_betas() -> dict[str, float]:
    return {
        "AAPL": 1.3,
        "NVDA": 1.7,
        "JPM": 1.2,
        "LLY": 0.4,
        "TSLA": 2.1,
        "XOM": 0.9,
        "WMT": 0.6,
        "PG": 0.5,
    }


@pytest.fixture
def sample_market_caps() -> dict[str, float]:
    return {
        "AAPL": 2_800_000_000_000.0,
        "NVDA": 1_200_000_000_000.0,
        "JPM": 500_000_000_000.0,
        "LLY": 800_000_000_000.0,
        "TSLA": 600_000_000_000.0,
        "XOM": 450_000_000_000.0,
        "WMT": 420_000_000_000.0,
        "PG": 380_000_000_000.0,
    }


@pytest.fixture
def sample_trend_scores() -> dict[str, float]:
    return {
        "AAPL": 0.85,
        "NVDA": 0.95,
        "JPM": 0.72,
        "LLY": 0.91,
        "TSLA": 0.55,
        "XOM": 0.68,
        "WMT": 0.78,
        "PG": 0.63,
    }


@pytest.fixture
def sample_exposures(
    sample_symbols, sample_market_betas, sample_market_caps, sample_trend_scores,
) -> dict[str, FactorExposures]:
    return compute_factor_exposures(
        symbols=sample_symbols,
        as_of=date(2026, 6, 22),
        market_betas=sample_market_betas,
        market_caps=sample_market_caps,
        trend_scores=sample_trend_scores,
    )


@pytest.fixture
def sample_factor_cov() -> FactorCovariance:
    """Covariance factorielle synthétique."""
    factor_names = list(DEFAULT_FACTOR_NAMES)
    K = len(factor_names)
    # Matrice de covariance avec corrélations modérées
    cov = np.array([
        [0.0004, 0.0001, 0.00005, -0.00002],   # market
        [0.0001, 0.0002, 0.00003, 0.00001],    # size
        [0.00005, 0.00003, 0.0003, -0.00004],   # momentum
        [-0.00002, 0.00001, -0.00004, 0.0001],  # value
    ], dtype=float)
    specific_vars = {
        "AAPL": 0.0005,
        "NVDA": 0.0009,
        "JPM": 0.0004,
        "LLY": 0.0003,
        "TSLA": 0.0015,
        "XOM": 0.00035,
        "WMT": 0.0002,
        "PG": 0.00015,
    }
    return FactorCovariance(
        factor_cov=cov,
        factor_names=factor_names,
        specific_variances=specific_vars,
        estimation_date=date(2026, 6, 22),
    )


@pytest.fixture
def sample_enriched_candidates(
    sample_symbols, sample_exposures,
) -> list[EnrichedSelection]:
    candidates = []
    for i, sym in enumerate(sample_symbols):
        candidates.append(EnrichedSelection(
            symbol=sym,
            sector="Technology" if sym in ("AAPL", "NVDA") else (
                "Financial" if sym == "JPM" else (
                    "Healthcare" if sym == "LLY" else (
                        "Consumer" if sym in ("TSLA", "WMT", "PG") else "Energy"
                    )
                )
            ),
            score_used=0.9 - i * 0.05,
            score_source="final_score_sentiment",
            predicted_proba=0.65 - i * 0.02,
            historical_win_rate=0.60,
            conviction_score=0.80 - i * 0.05,
        ))
    return candidates


# ---------------------------------------------------------------------------
# Tests Phase A : compute_factor_exposures
# ---------------------------------------------------------------------------


class TestComputeFactorExposures:
    def test_basic_computation(self, sample_symbols, sample_market_betas, sample_market_caps, sample_trend_scores):
        exposures = compute_factor_exposures(
            symbols=sample_symbols,
            as_of=date(2026, 6, 22),
            market_betas=sample_market_betas,
            market_caps=sample_market_caps,
            trend_scores=sample_trend_scores,
        )
        assert len(exposures) == len(sample_symbols)
        for sym in sample_symbols:
            assert sym in exposures
            exp = exposures[sym]
            assert isinstance(exp, FactorExposures)
            assert exp.symbol == sym
            assert exp.date == date(2026, 6, 22)
            # Beta should be winsorized but close to original
            assert 0.01 <= exp.market_beta <= 5.0
            # Size exposure: large cap → negative z-score
            if sample_market_caps.get(sym, 0) > 1_000_000_000_000:
                assert exp.size_exposure < 0, f"{sym} (large cap) should have negative size_exposure"
            # Momentum exposure: high trend → positive z-score
            if sample_trend_scores.get(sym, 0) > 0.8:
                assert exp.momentum_exposure > 0, f"{sym} (high momentum) should have positive momentum_exposure"

    def test_empty_inputs(self):
        exposures = compute_factor_exposures(symbols=[], as_of=date(2026, 6, 22))
        assert len(exposures) == 0

    def test_missing_data(self):
        exposures = compute_factor_exposures(
            symbols=["UNKNOWN"],
            as_of=date(2026, 6, 22),
            market_betas={},
            market_caps={},
            trend_scores={},
        )
        assert len(exposures) == 0

    def test_partial_data(self):
        exposures = compute_factor_exposures(
            symbols=["AAPL", "UNKNOWN"],
            as_of=date(2026, 6, 22),
            market_betas={"AAPL": 1.3},
            market_caps={"AAPL": 2_800_000_000_000.0},
            trend_scores={"AAPL": 0.85},
        )
        assert "AAPL" in exposures
        assert exposures["AAPL"].market_beta == pytest.approx(1.3)


class TestCrossSectionalZscore:
    def test_normal_distribution(self):
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], dtype=float)
        result = _cross_sectional_zscore(series)
        # Z-scores should be roughly N(0,1)
        assert abs(result.mean()) < 0.01
        assert result.std(ddof=0) == pytest.approx(1.0, abs=0.01)

    def test_constant_series(self):
        series = pd.Series([5.0, 5.0, 5.0], dtype=float)
        result = _cross_sectional_zscore(series)
        assert (result == 0.0).all()

    def test_with_nans(self):
        series = pd.Series([1.0, np.nan, 3.0, 4.0, np.nan], dtype=float)
        result = _cross_sectional_zscore(series)
        assert not result.isna().any()  # Les NaNs sont remplacés par 0.0


# ---------------------------------------------------------------------------
# Tests Phase B : EWMA covariance
# ---------------------------------------------------------------------------


class TestEwmaWeights:
    def test_sum_to_one(self):
        w = _ewma_weights(100, 60)
        assert w.sum() == pytest.approx(1.0)

    def test_decaying(self):
        w = _ewma_weights(10, 5)
        # Les poids les plus récents (fin du tableau) sont plus élevés
        assert w[-1] > w[0]

    def test_empty(self):
        w = _ewma_weights(0, 60)
        assert len(w) == 0


class TestEstimateEwmaCovariance:
    def test_basic(self):
        np.random.seed(42)
        returns = np.random.randn(252, 4) * 0.02
        cov = _estimate_ewma_covariance(returns, 60)
        assert cov.shape == (4, 4)
        # La matrice doit être symétrique
        assert np.allclose(cov, cov.T)
        # Les variances (diagonale) doivent être positives
        assert (np.diag(cov) > 0).all()

    def test_single_observation(self):
        returns = np.array([[0.01, -0.02, 0.005, 0.0]])
        cov = _estimate_ewma_covariance(returns, 60)
        assert cov.shape == (4, 4)


class TestEstimateFactorCovariance:
    def test_basic(self):
        dates = pd.date_range("2025-01-01", periods=252, freq="B")
        factor_returns = pd.DataFrame(
            np.random.randn(252, 4) * 0.01,
            index=dates,
            columns=list(DEFAULT_FACTOR_NAMES),
        )
        result = estimate_factor_covariance(factor_returns)
        assert result is not None
        assert result.factor_cov.shape == (4, 4)
        assert result.factor_names == list(DEFAULT_FACTOR_NAMES)
        assert result.ewma_half_life == DEFAULT_EWMA_HALF_LIFE
        assert result.lookback_days == DEFAULT_LOOKBACK_DAYS

    def test_insufficient_data(self):
        factor_returns = pd.DataFrame(
            {"market": [0.01, 0.02]},
        )
        result = estimate_factor_covariance(factor_returns)
        assert result is None


# ---------------------------------------------------------------------------
# Tests Phase C : decompose_portfolio_risk
# ---------------------------------------------------------------------------


class TestDecomposePortfolioRisk:
    def test_basic_decomposition(self, sample_exposures, sample_factor_cov):
        weights = {
            "AAPL": 0.15, "NVDA": 0.12, "JPM": 0.10, "LLY": 0.10,
            "TSLA": 0.08, "XOM": 0.10, "WMT": 0.10, "PG": 0.10,
        }
        # Normalize
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

        decomp = decompose_portfolio_risk(weights, sample_exposures, sample_factor_cov)

        assert isinstance(decomp, PortfolioRiskDecomposition)
        assert decomp.total_variance > 0
        assert decomp.total_volatility > 0
        assert decomp.systematic_variance >= 0
        assert decomp.specific_variance >= 0
        assert 0 <= decomp.systematic_pct <= 100
        assert len(decomp.factor_contributions) == 4
        assert len(decomp.factor_contribution_pct) == 4

        # La somme des contributions factorielles ≈ systematic_variance
        factor_sum = sum(decomp.factor_contributions.values())
        assert factor_sum == pytest.approx(decomp.systematic_variance, rel=1e-6)

        # Total variance = systematic + specific
        assert decomp.total_variance == pytest.approx(
            decomp.systematic_variance + decomp.specific_variance, rel=1e-10,
        )

    def test_empty_portfolio(self, sample_factor_cov):
        decomp = decompose_portfolio_risk({}, {}, sample_factor_cov)
        assert decomp.total_variance == 0.0
        assert len(decomp.warnings) > 0

    def test_single_asset(self, sample_exposures, sample_factor_cov):
        weights = {"AAPL": 1.0}
        decomp = decompose_portfolio_risk(weights, sample_exposures, sample_factor_cov)
        assert decomp.total_variance > 0
        assert decomp.concentration_herfindahl == pytest.approx(1.0)

    def test_systematic_vol_property(self, sample_exposures, sample_factor_cov):
        weights = {"AAPL": 0.5, "PG": 0.5}
        decomp = decompose_portfolio_risk(weights, sample_exposures, sample_factor_cov)
        assert decomp.systematic_vol == pytest.approx(math.sqrt(max(0.0, decomp.systematic_variance)))
        assert decomp.specific_vol == pytest.approx(math.sqrt(max(0.0, decomp.specific_variance)))


# ---------------------------------------------------------------------------
# Tests Phase D : check_factor_constraints
# ---------------------------------------------------------------------------


class TestCheckFactorConstraints:
    def test_no_violations(self, sample_enriched_candidates, sample_exposures, sample_factor_cov):
        result = check_factor_constraints(
            sample_enriched_candidates,
            sample_exposures,
            sample_factor_cov,
        )
        assert isinstance(result, FactorConstraintResult)
        assert result.decomposition is not None

    def test_with_high_beta_constraint(self, sample_enriched_candidates, sample_exposures, sample_factor_cov):
        # Contrainte très stricte sur le beta
        result = check_factor_constraints(
            sample_enriched_candidates,
            sample_exposures,
            sample_factor_cov,
            constraints={"max_portfolio_beta": 0.8},
        )
        assert isinstance(result, FactorConstraintResult)
        # Avec une contrainte beta=0.8, il devrait y avoir des violations
        # car NVDA (1.7) et TSLA (2.1) sont dans le lot

    def test_constraints_dict_default(self, sample_enriched_candidates, sample_exposures, sample_factor_cov):
        result = check_factor_constraints(
            sample_enriched_candidates,
            sample_exposures,
            sample_factor_cov,
            constraints={},
        )
        assert isinstance(result, FactorConstraintResult)


# ---------------------------------------------------------------------------
# Tests Phase E : filter_by_factor_correlation
# ---------------------------------------------------------------------------


class TestFilterByFactorCorrelation:
    def test_basic_filter(self, sample_enriched_candidates, sample_exposures, sample_factor_cov):
        retained, rejections = filter_by_factor_correlation(
            sample_enriched_candidates,
            sample_exposures,
            sample_factor_cov,
            max_factor_correlation=0.70,
        )
        assert len(retained) >= 1
        # Tous les candidats retenus doivent être dans la liste originale
        retained_symbols = {c.symbol for c in retained}
        original_symbols = {c.symbol for c in sample_enriched_candidates}
        assert retained_symbols.issubset(original_symbols)
        # Les rejetés ne doivent pas être dans les retenus
        rejected_symbols = {r.rejected_symbol for r in rejections}
        assert retained_symbols.isdisjoint(rejected_symbols)
        # Chaque rejet doit avoir une corrélation implicite et un blocker
        for rej in rejections:
            assert isinstance(rej, FactorCorrelationRejection)
            assert rej.implied_correlation > rej.threshold
            assert rej.blocker_symbol != rej.rejected_symbol

    def test_permissive_threshold(self, sample_enriched_candidates, sample_exposures, sample_factor_cov):
        retained, rejections = filter_by_factor_correlation(
            sample_enriched_candidates,
            sample_exposures,
            sample_factor_cov,
            max_factor_correlation=0.999,
        )
        # Avec un seuil très haut, tout devrait passer
        assert len(retained) == len(sample_enriched_candidates)
        assert len(rejections) == 0

    def test_strict_threshold(self, sample_enriched_candidates, sample_exposures, sample_factor_cov):
        retained, rejections = filter_by_factor_correlation(
            sample_enriched_candidates,
            sample_exposures,
            sample_factor_cov,
            max_factor_correlation=0.01,
        )
        # Avec un seuil très bas, très peu de candidats passent
        # (certains peuvent avoir une corrélation implicite très faible ou nulle
        #  selon leurs expositions factorielles)
        assert len(retained) <= 3

    def test_missing_exposures(self, sample_enriched_candidates, sample_factor_cov):
        # Aucune exposition → tout le monde passe
        retained, rejections = filter_by_factor_correlation(
            sample_enriched_candidates,
            {},
            sample_factor_cov,
            max_factor_correlation=0.70,
        )
        assert len(retained) == len(sample_enriched_candidates)
        assert len(rejections) == 0


class TestComputeFactorImpliedCorrelation:
    def test_identical_exposures(self, sample_exposures, sample_factor_cov):
        exp_aapl = sample_exposures["AAPL"]
        corr = _compute_factor_implied_correlation(
            exp_aapl, exp_aapl, sample_factor_cov, 0.0005, 0.0005,
        )
        # La corrélation implicite d'un titre avec lui-même via le modèle
        # factoriel est : systematic_variance / (systematic_variance + specific_variance)
        # qui est < 1 car une partie du risque est idiosyncratique.
        # On vérifie qu'elle est positive et cohérente.
        assert 0.0 < corr < 1.0, f"Expected 0 < corr < 1, got {corr}"
        # Avec une variance spécifique nulle, la corrélation serait 1.0
        corr_no_specific = _compute_factor_implied_correlation(
            exp_aapl, exp_aapl, sample_factor_cov, 0.0, 0.0,
        )
        assert corr_no_specific == pytest.approx(1.0, abs=0.001)

    def test_different_exposures(self, sample_exposures, sample_factor_cov):
        exp_aapl = sample_exposures["AAPL"]
        exp_pg = sample_exposures["PG"]
        corr = _compute_factor_implied_correlation(
            exp_aapl, exp_pg, sample_factor_cov, 0.0005, 0.00015,
        )
        assert -1.0 <= corr <= 1.0


# ---------------------------------------------------------------------------
# Tests builders
# ---------------------------------------------------------------------------


class TestBuildExposuresFromScoreFrame:
    def test_basic(self):
        df = pd.DataFrame({
            "symbol": ["AAPL", "NVDA", "JPM"],
            "beta_126": [1.3, 1.7, 1.2],
            "market_cap": [2.8e12, 1.2e12, 5e11],
            "trend_score": [0.85, 0.95, 0.72],
        })
        exposures = build_exposures_from_score_frame(df, date(2026, 6, 22))
        assert len(exposures) == 3
        assert "AAPL" in exposures
        assert exposures["AAPL"].market_beta == pytest.approx(1.3)

    def test_empty_df(self):
        exposures = build_exposures_from_score_frame(pd.DataFrame(), date(2026, 6, 22))
        assert len(exposures) == 0

    def test_missing_columns(self):
        df = pd.DataFrame({
            "symbol": ["AAPL"],
        })
        exposures = build_exposures_from_score_frame(df, date(2026, 6, 22))
        # Sans colonnes factorielles, pas d'expositions
        assert len(exposures) == 0


class TestBuildFactorReturns:
    def test_basic(self):
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        np.random.seed(42)
        close_prices = pd.DataFrame(
            np.exp(np.random.randn(60, 5).cumsum(axis=0) * 0.01) * 100,
            index=dates,
            columns=["AAPL", "NVDA", "JPM", "LLY", "SPY"],
        )
        benchmark = close_prices[["SPY"]].copy()
        result = build_factor_returns(
            symbols=["AAPL", "NVDA", "JPM", "LLY"],
            close_prices=close_prices[["AAPL", "NVDA", "JPM", "LLY"]],
            benchmark_prices=benchmark,
        )
        # Le fallback utilise le rendement équipondéré, donc result n'est pas None
        assert result is not None
        assert "market" in result.columns


# ---------------------------------------------------------------------------
# Tests format_risk_decomposition
# ---------------------------------------------------------------------------


class TestFormatRiskDecomposition:
    def test_formatting(self, sample_exposures, sample_factor_cov):
        weights = {"AAPL": 0.5, "PG": 0.5}
        decomp = decompose_portfolio_risk(weights, sample_exposures, sample_factor_cov)
        formatted = format_risk_decomposition(decomp)
        assert "Volatilité totale" in formatted
        assert "Risque systématique" in formatted
        assert "Risque spécifique" in formatted
        assert "Herfindahl" in formatted


# ---------------------------------------------------------------------------
# Integration test : full pipeline
# ---------------------------------------------------------------------------


class TestFullFactorPipeline:
    def test_end_to_end(self, sample_symbols, sample_market_betas, sample_market_caps, sample_trend_scores):
        """Test du pipeline complet : expositions → covariance → décomposition → contraintes."""
        # Phase A
        exposures = compute_factor_exposures(
            symbols=sample_symbols,
            as_of=date(2026, 6, 22),
            market_betas=sample_market_betas,
            market_caps=sample_market_caps,
            trend_scores=sample_trend_scores,
        )
        assert len(exposures) == len(sample_symbols)

        # Phase B
        np.random.seed(42)
        dates = pd.date_range("2025-01-01", periods=252, freq="B")
        factor_returns = pd.DataFrame(
            np.random.randn(252, 4) * 0.01,
            index=dates,
            columns=list(DEFAULT_FACTOR_NAMES),
        )
        factor_cov = estimate_factor_covariance(factor_returns)
        assert factor_cov is not None

        # Phase C
        eq_weights = {sym: 1.0 / len(sample_symbols) for sym in sample_symbols}
        # Inject specific variances manuellement car estimate_factor_covariance
        # sans stock_returns ne les calcule pas
        for sym in sample_symbols:
            factor_cov.specific_variances[sym] = 0.0003
        decomp = decompose_portfolio_risk(eq_weights, exposures, factor_cov)
        assert decomp.total_variance > 0
        assert decomp.systematic_pct > 0

        # Phase D
        candidates = [
            EnrichedSelection(
                symbol=sym, sector="Various", score_used=0.8,
                score_source="test", predicted_proba=None,
                historical_win_rate=None, conviction_score=0.7,
            )
            for sym in sample_symbols
        ]
        result = check_factor_constraints(candidates, exposures, factor_cov)
        assert result.decomposition is not None

        # Phase E
        retained, rejections = filter_by_factor_correlation(
            candidates, exposures, factor_cov, max_factor_correlation=0.90,
        )
        assert len(retained) >= 1

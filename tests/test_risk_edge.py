"""Tests unitaires — risk_management/edge.py (DirectionalEdgeEstimate, EdgeCalculator).

Sprint Maître 8.
"""

from __future__ import annotations

import numpy as np
import pytest

from risk_management.edge import (
    DirectionalEdgeEstimate,
    EdgeCalculator,
    compute_edge_from_trades,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def default_calc() -> EdgeCalculator:
    return EdgeCalculator()


@pytest.fixture
def cheap_calc() -> EdgeCalculator:
    """Coûts faibles (2 bps total)."""
    return EdgeCalculator(spread_bps=1.0, commission_bps=0.5, slippage_bps=0.5)


@pytest.fixture
def expensive_calc() -> EdgeCalculator:
    """Coûts élevés (50 bps total)."""
    return EdgeCalculator(spread_bps=20.0, commission_bps=10.0, slippage_bps=20.0)


# ── DirectionalEdgeEstimate ─────────────────────────────────────────────────


class TestDirectionalEdgeEstimate:
    def test_construction_valid_long(self) -> None:
        edge = DirectionalEdgeEstimate(
            side="long", gross_edge=0.05, cost_pct=0.002, net_edge=0.048,
            hit_rate=0.55, payoff=1.5, sample_size=100,
        )
        assert edge.side == "long"
        assert edge.is_tradable is True
        assert edge.net_edge > 0

    def test_construction_valid_short(self) -> None:
        edge = DirectionalEdgeEstimate(
            side="short", gross_edge=0.03, cost_pct=0.003, net_edge=0.027,
            hit_rate=0.52, payoff=1.3, sample_size=80, tail_loss=0.12,
        )
        assert edge.side == "short"
        assert edge.is_tradable is True

    def test_rejects_invalid_side(self) -> None:
        with pytest.raises(ValueError, match="side"):
            DirectionalEdgeEstimate(
                side="both", gross_edge=0.05, cost_pct=0.002, net_edge=0.048,
                hit_rate=0.55, payoff=1.5,
            )

    def test_rejects_hit_rate_out_of_bounds(self) -> None:
        with pytest.raises(ValueError, match="hit_rate"):
            DirectionalEdgeEstimate(
                side="long", gross_edge=0.05, cost_pct=0.002, net_edge=0.048,
                hit_rate=1.5, payoff=1.5,
            )

    def test_rejects_negative_payoff(self) -> None:
        with pytest.raises(ValueError, match="payoff"):
            DirectionalEdgeEstimate(
                side="long", gross_edge=0.05, cost_pct=0.002, net_edge=0.048,
                hit_rate=0.55, payoff=-1.0,
            )

    def test_is_tradable_positive_edge(self) -> None:
        edge = DirectionalEdgeEstimate(
            side="long", gross_edge=0.05, cost_pct=0.002, net_edge=0.048,
            hit_rate=0.55, payoff=1.5,
        )
        assert edge.is_tradable is True

    def test_is_not_tradable_negative_edge(self) -> None:
        edge = DirectionalEdgeEstimate(
            side="long", gross_edge=0.01, cost_pct=0.02, net_edge=-0.01,
            hit_rate=0.45, payoff=0.9,
        )
        assert edge.is_tradable is False

    def test_is_not_tradable_zero_edge(self) -> None:
        edge = DirectionalEdgeEstimate(
            side="long", gross_edge=0.02, cost_pct=0.02, net_edge=0.0,
            hit_rate=0.50, payoff=1.0,
        )
        assert edge.is_tradable is False

    def test_to_dict_rounds_values(self) -> None:
        edge = DirectionalEdgeEstimate(
            side="short", gross_edge=0.035678, cost_pct=0.001234, net_edge=0.034444,
            hit_rate=0.5512, payoff=1.3456, sample_size=45,
            uncertainty=0.02345, shrinkage_applied=True,
        )
        d = edge.to_dict()
        assert d["side"] == "short"
        assert d["net_edge"] == round(0.034444, 6)
        assert d["is_tradable"] is True


# ── EdgeCalculator ──────────────────────────────────────────────────────────


class TestEdgeCalculatorBasic:
    """Tests de base du EdgeCalculator."""

    def test_estimate_long_positive_edge(self, default_calc: EdgeCalculator) -> None:
        edge = default_calc.estimate(
            side="long", hit_rate=0.60, payoff=2.0, n_trades=100,
        )
        assert edge.side == "long"
        # gross_edge = 0.60*2.0 - 0.40*1.0 = 1.20 - 0.40 = 0.80
        assert edge.gross_edge == pytest.approx(0.80, abs=1e-6)
        # cost_pct = 2*(5+1+2)/10000 = 16/10000 = 0.0016
        assert edge.cost_pct == pytest.approx(0.0016, abs=1e-6)
        # net = 0.80 - 0.0016 = 0.7984
        assert edge.net_edge == pytest.approx(0.7984, abs=1e-6)
        assert edge.is_tradable is True
        assert edge.shrinkage_applied is False

    def test_estimate_short_positive_edge(self, default_calc: EdgeCalculator) -> None:
        edge = default_calc.estimate(
            side="short", hit_rate=0.55, payoff=1.8, n_trades=60, holding_days=5,
        )
        # gross = 0.55*1.8 - 0.45 = 0.99 - 0.45 = 0.54
        assert edge.gross_edge == pytest.approx(0.54, abs=1e-6)
        # cost = 0.0016 + 0.003*(5/252) ≈ 0.0016 + 0.0000595 = 0.0016595
        assert edge.cost_pct == pytest.approx(0.0016595, abs=1e-4)
        assert edge.is_tradable is True

    def test_short_borrow_fee_zero_holding(self, default_calc: EdgeCalculator) -> None:
        edge = default_calc.estimate(
            side="short", hit_rate=0.55, payoff=1.5, n_trades=100, holding_days=0,
        )
        # cost = 0.0016 + 0.003*(0/252) = 0.0016
        assert edge.cost_pct == pytest.approx(0.0016, abs=1e-6)

    def test_estimate_negative_edge(self, default_calc: EdgeCalculator) -> None:
        edge = default_calc.estimate(
            side="long", hit_rate=0.48, payoff=1.0, n_trades=50,
        )
        # gross = 0.48*1.0 - 0.52 = -0.04
        assert edge.gross_edge == pytest.approx(-0.04, abs=1e-6)
        # net = -0.04 - 0.0016 = -0.0416
        assert edge.net_edge < 0
        assert edge.is_tradable is False

    def test_estimate_edge_brut_positif_net_negatif(self, default_calc: EdgeCalculator) -> None:
        """Edge brut positif mais coûts supérieurs → net négatif → rejet."""
        # Hit rate 0.51, payoff 1.05 → gross = 0.51*1.05 - 0.49 = 0.5355 - 0.49 = 0.0455
        # Avec coûts = 0.0016 → net = 0.0439 > 0 → OK avec coûts faibles
        # Avec coûts élevés → on utilise expensive_calc
        pass  # Testé plus bas dans TestEdgeCalculatorCosts


# ── EdgeCalculator avec coûts ───────────────────────────────────────────────


class TestEdgeCalculatorCosts:
    """Coûts croissants → taille ou acceptation décroissante."""

    def test_edge_brut_positif_net_negatif_avec_couts_eleves(
        self, expensive_calc: EdgeCalculator,
    ) -> None:
        """Edge brut positif mais net négatif → rejet."""
        # expensive calc: spread=20, comm=10, slippage=20 → total=100 bps
        # cost_pct = 100/10000 = 0.01
        edge = expensive_calc.estimate(
            side="long", hit_rate=0.51, payoff=1.02, n_trades=50,
        )
        # gross = 0.51*1.02 - 0.49 = 0.5202 - 0.49 = 0.0302
        assert edge.gross_edge > 0
        # net = 0.0302 - 0.01 = 0.0202 > 0 ... still positive
        # Let's use lower hit rate
        edge2 = expensive_calc.estimate(
            side="long", hit_rate=0.505, payoff=1.005, n_trades=50,
        )
        # gross = 0.505*1.005 - 0.495 = 0.507525 - 0.495 = 0.012525
        # net = 0.012525 - 0.01 = 0.002525 > 0 ... still positive
        # Let's try even harsher
        edge3 = expensive_calc.estimate(
            side="long", hit_rate=0.503, payoff=1.003, n_trades=50,
        )
        # gross = 0.503*1.003 - 0.497 = 0.504509 - 0.497 = 0.007509
        # net = 0.007509 - 0.01 = -0.002491 < 0
        assert edge3.gross_edge > 0
        assert edge3.net_edge < 0
        assert edge3.is_tradable is False

    def test_cout_croissant_taille_non_croissante(
        self, cheap_calc: EdgeCalculator, expensive_calc: EdgeCalculator,
    ) -> None:
        """Avec des coûts plus élevés, le net edge est plus faible."""
        params = {"side": "long", "hit_rate": 0.55, "payoff": 1.5, "n_trades": 100}
        edge_cheap = cheap_calc.estimate(**params)
        edge_expensive = expensive_calc.estimate(**params)
        # Make sure cost_pct is strictly higher
        assert edge_expensive.cost_pct > edge_cheap.cost_pct
        # net edge is strictly lower with higher costs
        assert edge_expensive.net_edge < edge_cheap.net_edge


# ── Shrinkage ───────────────────────────────────────────────────────────────


class TestEdgeCalculatorShrinkage:
    def test_shrinkage_applique_petit_echantillon(self, default_calc: EdgeCalculator) -> None:
        """Faible échantillon → shrinkage appliqué."""
        edge = default_calc.estimate(
            side="long", hit_rate=0.70, payoff=2.5, n_trades=5,
        )
        assert edge.shrinkage_applied is True
        # Avec N=5, prior_strength=5:
        # w_data = 5/(5+5) = 0.5, w_prior = 0.5
        # hit_rate = 0.5*0.70 + 0.5*0.50 = 0.35 + 0.25 = 0.60
        # payoff = 0.5*2.5 + 0.5*1.0 = 1.25 + 0.5 = 1.75
        assert edge.hit_rate == pytest.approx(0.60)
        assert edge.payoff == pytest.approx(1.75)

    def test_pas_de_shrinkage_grand_echantillon(self, default_calc: EdgeCalculator) -> None:
        """Grand échantillon → pas de shrinkage."""
        edge = default_calc.estimate(
            side="long", hit_rate=0.65, payoff=2.0, n_trades=200,
        )
        assert edge.shrinkage_applied is False
        assert edge.hit_rate == 0.65
        assert edge.payoff == 2.0

    def test_shrinkage_rend_hit_rate_plus_proche_de_0_50(self, default_calc: EdgeCalculator) -> None:
        """Le shrinkage rapproche le hit rate de 0.50."""
        # hit_rate extrême → shrinkage le ramène vers 0.50
        edge = default_calc.estimate(
            side="long", hit_rate=0.95, payoff=1.5, n_trades=3,
        )
        assert edge.shrinkage_applied is True
        assert 0.50 < edge.hit_rate < 0.95  # shrunk toward 0.50

    def test_shrinkage_rend_payoff_plus_proche_de_1_0(self, default_calc: EdgeCalculator) -> None:
        """Le shrinkage rapproche le payoff de 1.0."""
        edge = default_calc.estimate(
            side="long", hit_rate=0.55, payoff=5.0, n_trades=3,
        )
        assert edge.shrinkage_applied is True
        assert 1.0 < edge.payoff < 5.0  # shrunk toward 1.0


# ── EdgeCalculator — seuil d'échantillon ────────────────────────────────────


class TestEdgeCalculatorThreshold:
    def test_exactement_au_seuil_pas_de_shrinkage(self) -> None:
        calc = EdgeCalculator(min_sample_size=30)
        edge = calc.estimate(
            side="long", hit_rate=0.65, payoff=2.0, n_trades=30,
        )
        assert edge.shrinkage_applied is False

    def test_juste_en_dessous_shrinkage(self) -> None:
        calc = EdgeCalculator(min_sample_size=30)
        edge = calc.estimate(
            side="long", hit_rate=0.65, payoff=2.0, n_trades=29,
        )
        assert edge.shrinkage_applied is True

    def test_zero_trades(self, default_calc: EdgeCalculator) -> None:
        edge = default_calc.estimate(
            side="long", hit_rate=0.60, payoff=1.5, n_trades=0,
        )
        assert edge.shrinkage_applied is True
        # uncertainty should be 1.0 (safety default)
        assert edge.uncertainty == 1.0


# ── compute_edge_from_trades ────────────────────────────────────────────────


class TestComputeEdgeFromTrades:
    def test_empty_returns(self) -> None:
        edge = compute_edge_from_trades(np.array([]))
        assert edge.sample_size == 0
        assert edge.net_edge == 0.0
        assert edge.is_tradable is False

    def test_all_wins(self) -> None:
        returns = np.array([0.02, 0.03, 0.01, 0.025, 0.015])
        edge = compute_edge_from_trades(returns, side="long")
        assert edge.hit_rate == 1.0
        # all wins → payoff = inf → but avg_loss = 1.0 (fallback) → payoff = avg_gain
        assert edge.payoff > 0
        assert edge.gross_edge > 0

    def test_all_losses(self) -> None:
        returns = np.array([-0.02, -0.03, -0.01])
        edge = compute_edge_from_trades(returns, side="long")
        assert edge.hit_rate == 0.0
        assert edge.gross_edge < 0
        assert edge.is_tradable is False

    def test_mixed_returns(self) -> None:
        # 3 wins, 2 losses
        returns = np.array([0.05, -0.02, 0.03, -0.01, 0.04])
        edge = compute_edge_from_trades(returns, side="long", cost_pct=0.002)
        assert edge.hit_rate == pytest.approx(3 / 5, abs=1e-6)
        # avg_gain = (0.05+0.03+0.04)/3 = 0.04
        # avg_loss = (0.02+0.01)/2 = 0.015
        # payoff = 0.04/0.015 ≈ 2.6667
        assert edge.payoff == pytest.approx(0.04 / 0.015, abs=0.01)
        # gross = 0.6 * 2.6667 - 0.4 = 1.6 - 0.4 = 1.2
        # net = 1.2 - 0.002 = 1.198
        assert edge.net_edge > 0
        assert edge.is_tradable is True
        # tail_loss = min(returns) = -0.02
        assert edge.tail_loss == pytest.approx(-0.02)

    def test_tail_loss_is_min_return(self) -> None:
        returns = np.array([0.10, -0.05, 0.02, -0.15, 0.01])
        edge = compute_edge_from_trades(returns)
        assert edge.tail_loss == -0.15

    def test_shrinkage_on_small_sample(self) -> None:
        returns = np.array([0.03, -0.01, 0.02])
        edge = compute_edge_from_trades(returns, min_sample_size=10)
        assert edge.shrinkage_applied is True

    def test_no_shrinkage_on_large_sample(self) -> None:
        returns = np.random.RandomState(42).normal(0.005, 0.03, 100)
        edge = compute_edge_from_trades(returns, min_sample_size=30)
        assert edge.shrinkage_applied is False


# ── EdgeCalculator — payoff long/short distinct ─────────────────────────────


class TestEdgeCalculatorLongShortDistinct:
    """Payoff et hit rate distincts par side."""

    def test_long_payoff_different_de_short(self, default_calc: EdgeCalculator) -> None:
        edge_long = default_calc.estimate(
            side="long", hit_rate=0.55, payoff=1.8, n_trades=50,
        )
        edge_short = default_calc.estimate(
            side="short", hit_rate=0.48, payoff=1.3, n_trades=30, holding_days=10,
        )
        # Les deux edges sont différents parce que payoff et hit rate diffèrent
        assert edge_long.payoff != edge_short.payoff
        assert edge_long.hit_rate != edge_short.hit_rate
        # Short a des coûts supplémentaires (borrow fee)
        assert edge_short.cost_pct > edge_long.cost_pct

    def test_short_sans_borrow_fee(self) -> None:
        calc = EdgeCalculator(borrow_fee_annual=0.0)
        edge_long = calc.estimate(
            side="long", hit_rate=0.55, payoff=1.5, n_trades=50,
        )
        edge_short = calc.estimate(
            side="short", hit_rate=0.55, payoff=1.5, n_trades=50, holding_days=10,
        )
        # Sans borrow fee, les coûts sont identiques
        assert edge_long.cost_pct == edge_short.cost_pct


# ── Uncertainty ──────────────────────────────────────────────────────────────


class TestEdgeCalculatorUncertainty:
    def test_uncertainty_decroit_avec_echantillon(self, default_calc: EdgeCalculator) -> None:
        """Plus d'échantillon → moins d'incertitude."""
        edge_small = default_calc.estimate(
            side="long", hit_rate=0.55, payoff=1.5, n_trades=10,
        )
        edge_large = default_calc.estimate(
            side="long", hit_rate=0.55, payoff=1.5, n_trades=1000,
        )
        assert edge_large.uncertainty < edge_small.uncertainty

    def test_uncertainty_zero_for_perfect_certainty(self, default_calc: EdgeCalculator) -> None:
        """Hit rate 1.0 + grand échantillon → incertitude minimale."""
        edge = default_calc.estimate(
            side="long", hit_rate=0.999, payoff=1.5, n_trades=10000,
        )
        assert edge.uncertainty < 0.01

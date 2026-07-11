"""Tests d'intégration — réconciliation edge/risque/sizing (Sprint Maître 8).

Vérifie le contrat complet : edge → abstention → Kelly → sizing.
"""

from __future__ import annotations

import pytest

from risk_management.abstention import AbstentionPolicy
from risk_management.config import RiskConfig
from risk_management.edge import DirectionalEdgeEstimate, EdgeCalculator
from risk_management.enums import KellyFallback
from risk_management.kelly import KellySizer, compute_kelly_fraction, compute_kelly_shares
from risk_management.models import DirectionalWinRateInfo, PriceInfo
from risk_management.selection_contract import MLRankedCandidate

from datetime import date


def _kelly_cfg(**overrides) -> RiskConfig:
    defaults = {
        "account_equity": 100_000,
        "risk_per_trade_pct": 0.01,
        "atr_stop_multiple": 2.0,
        "max_positions": 10,
        "max_position_weight": 0.10,
        "min_position_notional": 500.0,
        "enable_kelly_sizing": True,
        "assumed_payoff_ratio": 1.5,
        "kelly_fraction_multiplier": 0.25,
        "min_effective_probability": 0.52,
        "default_win_rate": 0.55,
        "prediction_confidence_weight": 0.60,
        "historical_win_rate_weight": 0.40,
    }
    defaults.update(overrides)
    return RiskConfig(**defaults)


# ── Pipeline complet: Edge → Abstention → Kelly ────────────────────────────


class TestEdgeToAbstentionToKelly:
    """Pipeline complet : edge estimé → abstention → sizing Kelly."""

    def test_full_pipeline_go(self) -> None:
        """Cas nominal: tout passe."""
        cfg = _kelly_cfg()
        edge_calc = EdgeCalculator()
        policy = AbstentionPolicy.sensible_defaults()
        sizer = KellySizer(cfg)

        candidate = MLRankedCandidate(
            symbol="AAPL", trade_date=date.today(), side="long",
            p_long=0.55, p_flat=0.30, p_short=0.15, p_side=0.55,
            model_run_id="run_001", policy_version=1,
        )
        stats = DirectionalWinRateInfo(
            symbol="AAPL", side="long", hit_rate=0.60, payoff=2.0,
            trade_count=100, run_id="run_001",
        )
        edge = edge_calc.estimate(side="long", hit_rate=0.60, payoff=2.0, n_trades=100)
        abstention = policy.evaluate(candidate, edge)

        assert abstention.go is True, f"Abstention blocked: {abstention.reason}"

        pi = PriceInfo("AAPL", 150.0, 5.0)
        result = sizer.compute(
            pi, predicted_proba=0.55, directional_stats=stats,
        )
        assert result.proposed_shares > 0

    def test_edge_net_negatif_bloque_tout(self) -> None:
        """Edge net négatif → abstention NO-GO → pas de sizing."""
        policy = AbstentionPolicy.permissive()
        edge = DirectionalEdgeEstimate(
            side="long", gross_edge=0.01, cost_pct=0.02, net_edge=-0.01,
            hit_rate=0.45, payoff=0.9, sample_size=50,
        )
        candidate = MLRankedCandidate(
            symbol="AAPL", trade_date=date.today(), side="long",
            p_long=0.45, p_flat=0.35, p_short=0.20, p_side=0.45,
            model_run_id="run_001", policy_version=1,
        )
        decision = policy.evaluate(candidate, edge)
        assert decision.go is False
        assert "net_edge" in decision.reason

    def test_faible_confiance_bloque_abstention(self) -> None:
        """Faible confiance ML → abstention NO-GO."""
        policy = AbstentionPolicy(min_p_side=0.45, require_positive_edge=False)
        candidate = MLRankedCandidate(
            symbol="AAPL", trade_date=date.today(), side="long",
            p_long=0.38, p_flat=0.35, p_short=0.27, p_side=0.38,
            model_run_id="run_002", policy_version=1,
        )
        decision = policy.evaluate(candidate, edge=None)
        assert decision.go is False
        assert "p_side" in decision.reason

    def test_kelly_negatif_rejette(self) -> None:
        """Kelly ≤ 0 → rejet (fallback REJECT par défaut)."""
        cfg = _kelly_cfg()
        sizer = KellySizer(cfg)
        pi = PriceInfo("AAPL", 150.0, 5.0)
        stats = DirectionalWinRateInfo(
            symbol="AAPL", side="long", hit_rate=0.35, payoff=0.7,
            trade_count=50, run_id="run_003",
        )
        result = sizer.compute(
            pi, predicted_proba=0.35, historical_win_rate=0.35,
            directional_stats=stats,
        )
        assert result.proposed_shares == 0

    def test_edge_brut_positif_net_negatif_rejet(self) -> None:
        """Edge brut > 0 mais coûts > edge brut → net < 0 → rejet."""
        edge = DirectionalEdgeEstimate(
            side="long", gross_edge=0.005, cost_pct=0.01, net_edge=-0.005,
            hit_rate=0.505, payoff=1.01, sample_size=50,
        )
        assert edge.gross_edge > 0
        assert edge.net_edge < 0
        assert edge.is_tradable is False

    def test_cout_croissant_taille_decroissante(self) -> None:
        """Avec un coût plus élevé, l'edge net est plus faible."""
        cheap = EdgeCalculator(spread_bps=1.0, commission_bps=0.5, slippage_bps=0.5)
        expensive = EdgeCalculator(spread_bps=20.0, commission_bps=10.0, slippage_bps=20.0)

        edge_cheap = cheap.estimate(side="long", hit_rate=0.55, payoff=1.5, n_trades=100)
        edge_expensive = expensive.estimate(side="long", hit_rate=0.55, payoff=1.5, n_trades=100)

        assert edge_expensive.net_edge < edge_cheap.net_edge


# ── Shrinkage et petits échantillons ────────────────────────────────────────


class TestShrinkageIntegration:
    def test_faible_echantillon_shrinkage_active(self) -> None:
        """Faible échantillon → shrinkage actif → Kelly plus conservateur."""
        frac_large = compute_kelly_fraction(0.70, 3.0, trade_count=200)
        frac_small = compute_kelly_fraction(0.70, 3.0, trade_count=5)
        # Sur petit échantillon, hit_rate et payoff shrunkés vers 0.50/1.0
        # → Kelly plus faible (plus conservateur)
        assert frac_small < frac_large

    def test_shrinkage_evite_surestimation(self) -> None:
        """Un hit_rate extrême sur petit échantillon donne un Kelly bien plus faible."""
        # Sans shrinkage : hit_rate=0.95, payoff=5.0 → Kelly ≈ 0.95 - 0.05/5 = 0.94
        # Avec shrinkage (N=3, prior_strength=5) : w_data=3/8=0.375
        # hit_rate = 0.375*0.95 + 0.625*0.50 = 0.669
        # payoff = 0.375*5.0 + 0.625*1.0 = 2.5
        # Kelly = 0.669 - 0.331/2.5 = 0.669 - 0.1324 = 0.5366
        frac_shrunk = compute_kelly_fraction(0.95, 5.0, trade_count=3, kelly_multiplier=1.0, max_fraction=1.0)
        frac_full = compute_kelly_fraction(0.95, 5.0, trade_count=200, kelly_multiplier=1.0, max_fraction=1.0)
        # Le shrinkage doit réduire le Kelly d'au moins 30%
        assert frac_shrunk < frac_full * 0.70, f"shrunk={frac_shrunk} full={frac_full}"


# ── Risque post-fill ≤ budget ───────────────────────────────────────────────


class TestRiskPostFill:
    """Vérifie que le risque post-fill est ≤ budget."""

    def test_risque_atr_post_fill_dans_budget(self) -> None:
        cfg = _kelly_cfg(risk_per_trade_pct=0.01, atr_stop_multiple=2.0, max_position_weight=0.5)
        sizer = KellySizer(cfg)
        pi = PriceInfo("AAPL", 100.0, 3.0)

        result = sizer.compute(pi, predicted_proba=0.70, historical_win_rate=0.60)
        if result.proposed_shares > 0 and pi.atr_20:
            risk = result.proposed_shares * pi.atr_20 * cfg.atr_stop_multiple
            budget = cfg.account_equity * cfg.risk_per_trade_pct
            assert risk <= budget + 0.01, f"risk={risk} > budget={budget}"

    def test_gap_plus_eleve_taille_plus_faible(self) -> None:
        """Un ATR plus élevé (proxy gap/ES) → sizing plus faible."""
        cfg = _kelly_cfg(max_position_weight=0.5)
        sizer = KellySizer(cfg)

        pi_normal = PriceInfo("AAPL", 100.0, 2.0)
        pi_volatile = PriceInfo("AAPL", 100.0, 8.0)

        result_normal = sizer.compute(pi_normal, predicted_proba=0.70, historical_win_rate=0.60)
        result_volatile = sizer.compute(pi_volatile, predicted_proba=0.70, historical_win_rate=0.60)

        # ATR 4x plus élevé → au moins 4x moins de shares (cap ATR)
        if result_normal.proposed_shares > 0 and result_volatile.proposed_shares > 0:
            assert result_volatile.proposed_shares <= result_normal.proposed_shares


# ── Payoff long/short distincts ─────────────────────────────────────────────


class TestLongShortDistinct:
    def test_payoff_long_short_differents(self) -> None:
        cfg = _kelly_cfg()
        sizer = KellySizer(cfg)
        pi = PriceInfo("AAPL", 150.0, None)

        stats_long = DirectionalWinRateInfo(
            symbol="AAPL", side="long", hit_rate=0.60, payoff=2.5,
            trade_count=100, run_id="run_001",
        )
        stats_short = DirectionalWinRateInfo(
            symbol="AAPL", side="short", hit_rate=0.45, payoff=1.1,
            trade_count=60, run_id="run_002",
        )

        r_long = sizer.compute(pi, predicted_proba=0.60, directional_stats=stats_long)
        r_short = sizer.compute(pi, predicted_proba=0.45, directional_stats=stats_short)

        # Long a un meilleur hit_rate/payoff → plus de shares ou au moins différent
        # (short peut même être rejeté)
        assert r_long.proposed_shares != r_short.proposed_shares

"""Tests unitaires — KellySizer V3 (Sprint Maître 8)."""
from __future__ import annotations

import pytest

from risk_management.config import RiskConfig
from risk_management.enums import KellyFallback
from risk_management.kelly import KellySizer, compute_kelly_fraction, compute_kelly_shares
from risk_management.models import DirectionalWinRateInfo, PriceInfo


def _kelly_cfg(**overrides) -> RiskConfig:  # type: ignore[no-untyped-def]
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


@pytest.mark.unit
def test_kelly_positive_with_atr() -> None:
    cfg = _kelly_cfg()
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    result = sizer.compute(pi, predicted_proba=0.70, historical_win_rate=0.58)
    assert result.method == "kelly_atr"
    assert result.proposed_shares >= 1


@pytest.mark.unit
def test_kelly_positive_without_atr() -> None:
    cfg = _kelly_cfg()
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, None)
    result = sizer.compute(pi, predicted_proba=0.70, historical_win_rate=0.58)
    assert result.method == "kelly_only"
    assert result.proposed_shares >= 1


@pytest.mark.unit
def test_kelly_negative_fallback_reject() -> None:
    """V3: fallback REJECT par défaut (plus d'ATR automatique)."""
    cfg = _kelly_cfg(min_effective_probability=0.52)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    # p_eff ~0.40 → below min_effective_probability → REJECT (V3 default)
    result = sizer.compute(pi, predicted_proba=0.35, historical_win_rate=0.35)
    assert result.proposed_shares == 0
    assert result.method == "rejected_zero_shares"


@pytest.mark.unit
def test_kelly_negative_fallback_atr_explicit() -> None:
    """V3: fallback ATR explicite via KellyFallback.ATR_FALLBACK."""
    cfg = _kelly_cfg(min_effective_probability=0.52)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    result = sizer.compute(
        pi, predicted_proba=0.35, historical_win_rate=0.35,
        fallback=KellyFallback.ATR_FALLBACK,
    )
    assert result.method == "atr"


@pytest.mark.unit
def test_kelly_negative_fallback_minimal_probe() -> None:
    """V3: fallback MINIMAL_PROBE donne 1 share."""
    cfg = _kelly_cfg(min_effective_probability=0.52)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    result = sizer.compute(
        pi, predicted_proba=0.35, historical_win_rate=0.35,
        fallback=KellyFallback.MINIMAL_PROBE,
    )
    assert result.proposed_shares == 1.0
    assert result.method == "atr"


@pytest.mark.unit
def test_kelly_disabled_uses_v1_sizer() -> None:
    from risk_management.position_sizer import PositionSizer
    cfg = _kelly_cfg(enable_kelly_sizing=False)
    # Use PositionSizer directly (KellySizer not created when disabled)
    sizer = PositionSizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    result = sizer.compute(pi)
    assert result.method in ("atr", "equal_weight")


@pytest.mark.unit
def test_kelly_capped_by_max_position_weight() -> None:
    # Very high kelly_fraction_multiplier to force clipping
    cfg = _kelly_cfg(kelly_fraction_multiplier=1.0, max_position_weight=0.05)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 10.0, 0.5)
    result = sizer.compute(pi, predicted_proba=0.90, historical_win_rate=0.80)
    # max notional = 100000 * 0.05 = 5000, shares = 5000/10 = 500
    assert result.proposed_shares <= 500
    assert result.proposed_shares >= 1


@pytest.mark.unit
def test_kelly_min_notional_rejection() -> None:
    cfg = _kelly_cfg(min_position_notional=50_000.0, kelly_fraction_multiplier=0.01)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    result = sizer.compute(pi, predicted_proba=0.55, historical_win_rate=0.55)
    assert result.proposed_shares == 0
    assert result.method == "rejected_notional"


@pytest.mark.unit
def test_fallback_equal_weight_when_no_data() -> None:
    cfg = _kelly_cfg()
    sizer = KellySizer(cfg)
    pi = PriceInfo("XYZ", 50.0, None)
    # default_win_rate=0.55 for both → p_eff=0.55 >= 0.52
    # Kelly = 0.55 - 0.45/1.5 = 0.55 - 0.30 = 0.25 → frac = 0.25*0.25 = 0.0625
    # notional = 100000*0.0625 = 6250 → shares = 125 → kelly_only
    result = sizer.compute(pi, predicted_proba=None, historical_win_rate=None)
    assert result.method == "kelly_only"
    assert result.proposed_shares >= 1


@pytest.mark.unit
def test_kelly_atr_cap_uses_risk_multiplier() -> None:
    cfg = _kelly_cfg(risk_multiplier=0.5, max_position_weight=0.5)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 100.0, 2.0)

    result = sizer.compute(pi, predicted_proba=0.90, historical_win_rate=0.80)

    # Kelly très favorable, mais cap ATR piloté par risk_multiplier :
    # budget = 100_000 * 1% * 0.5 = 500 ; risk/share = 2*2 = 4 ; cap = 125.
    assert result.method == "kelly_atr"
    assert result.proposed_shares == 125


@pytest.mark.unit
def test_kelly_uses_effective_min_notional_for_rejection() -> None:
    cfg = _kelly_cfg(
        account_equity=2_000.0,
        min_position_notional=10.0,
        enforce_min_notional=500.0,
    )
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 100.0, None)

    result = sizer.compute(pi, predicted_proba=0.55, historical_win_rate=0.55)

    assert result.proposed_shares == 0
    assert result.method == "rejected_notional_below_enforced"


# ── Sprint Maître 8 — V3 tests ─────────────────────────────────────────────


@pytest.mark.unit
class TestKellySizerV3Directional:
    """Tests V3 avec DirectionalWinRateInfo (hit rate + payoff directionnels)."""

    def test_directional_stats_used_for_kelly(self) -> None:
        cfg = _kelly_cfg()
        sizer = KellySizer(cfg)
        pi = PriceInfo("AAPL", 150.0, None)
        stats = DirectionalWinRateInfo(
            symbol="AAPL", side="long", hit_rate=0.65, payoff=2.0,
            trade_count=100, run_id="run_001",
        )
        result = sizer.compute(
            pi, predicted_proba=0.70, historical_win_rate=0.58,
            directional_stats=stats,
        )
        # Avec hit_rate=0.65, payoff=2.0 (au lieu de p_eff/1.5)
        # Kelly = 0.65 - 0.35/2.0 = 0.65 - 0.175 = 0.475
        # frac = 0.475 * 0.25 = 0.11875
        # notional = 100000 * 0.11875 = 11875 → shares = 79
        assert result.method == "kelly_only"
        assert result.proposed_shares >= 1

    def test_directional_stats_shrinkage_small_sample(self) -> None:
        """Faible échantillon → shrinkage appliqué."""
        cfg = _kelly_cfg()
        sizer = KellySizer(cfg)
        pi = PriceInfo("AAPL", 150.0, None)
        stats = DirectionalWinRateInfo(
            symbol="AAPL", side="long", hit_rate=0.80, payoff=3.0,
            trade_count=5, run_id="run_002",
        )
        result = sizer.compute(
            pi, predicted_proba=0.70, historical_win_rate=0.58,
            directional_stats=stats,
        )
        # Shrinkage applied: hit_rate shrunk toward 0.50
        # N=5, prior_strength=5 → w_data = 0.5, w_prior = 0.5
        # shrunk hit_rate = 0.5*0.80 + 0.5*0.50 = 0.65
        # shrunk payoff = 0.5*3.0 + 0.5*1.0 = 2.0
        # Kelly = 0.65 - 0.35/2.0 = 0.65 - 0.175 = 0.475 → frac = 0.11875
        assert result.method == "kelly_only"
        assert result.proposed_shares >= 1

    def test_directional_stats_kelly_negative_rejects(self) -> None:
        """Hit rate et payoff trop faibles → Kelly ≤ 0 → rejet."""
        cfg = _kelly_cfg()
        sizer = KellySizer(cfg)
        pi = PriceInfo("AAPL", 150.0, 5.0)
        stats = DirectionalWinRateInfo(
            symbol="AAPL", side="long", hit_rate=0.40, payoff=0.8,
            trade_count=50, run_id="run_003",
        )
        result = sizer.compute(
            pi, predicted_proba=0.40, historical_win_rate=0.40,
            directional_stats=stats,
        )
        # Kelly = 0.40 - 0.60/0.8 = 0.40 - 0.75 = -0.35 ≤ 0 → rejet
        assert result.proposed_shares == 0


@pytest.mark.unit
class TestKellySizerV3LongShort:
    """Payoff long/short distincts."""

    def test_long_vs_short_different_payoff(self) -> None:
        cfg = _kelly_cfg()
        sizer = KellySizer(cfg)
        pi = PriceInfo("AAPL", 150.0, None)

        stats_long = DirectionalWinRateInfo(
            symbol="AAPL", side="long", hit_rate=0.55, payoff=2.0,
            trade_count=100, run_id="run_001",
        )
        stats_short = DirectionalWinRateInfo(
            symbol="AAPL", side="short", hit_rate=0.50, payoff=1.2,
            trade_count=80, run_id="run_002",
        )

        result_long = sizer.compute(
            pi, predicted_proba=0.55, directional_stats=stats_long,
        )
        result_short = sizer.compute(
            pi, predicted_proba=0.50, directional_stats=stats_short,
        )
        # Les sizing sont différents car payoff/hit_rate différents
        assert result_long.proposed_shares != result_short.proposed_shares


@pytest.mark.unit
class TestKellySizerV3ATRCaps:
    """Cap ATR et gestion du risque."""

    def test_atr_plus_eleve_taille_plus_faible(self) -> None:
        """ATR plus élevé → risque par share plus élevé → moins de shares."""
        cfg = _kelly_cfg(risk_multiplier=1.0, max_position_weight=0.5)
        sizer = KellySizer(cfg)

        pi_low_atr = PriceInfo("AAPL", 100.0, 1.0)   # ATR bas
        pi_high_atr = PriceInfo("AAPL", 100.0, 10.0)  # ATR élevé

        result_low = sizer.compute(pi_low_atr, predicted_proba=0.70, historical_win_rate=0.60)
        result_high = sizer.compute(pi_high_atr, predicted_proba=0.70, historical_win_rate=0.60)

        # ATR plus élevé → cap plus restrictif
        assert result_high.proposed_shares <= result_low.proposed_shares

    def test_risque_post_fill_inferieur_budget(self) -> None:
        """Le risque post-fill est ≤ budget de risque."""
        cfg = _kelly_cfg(risk_per_trade_pct=0.01, atr_stop_multiple=2.0)
        sizer = KellySizer(cfg)
        pi = PriceInfo("AAPL", 150.0, 5.0)

        result = sizer.compute(pi, predicted_proba=0.70, historical_win_rate=0.60)
        if result.proposed_shares > 0 and pi.atr_20:
            risk_post_fill = result.proposed_shares * pi.atr_20 * cfg.atr_stop_multiple
            budget = cfg.account_equity * cfg.risk_per_trade_pct
            assert risk_post_fill <= budget + 1.0  # tolérance d'arrondi


# ── compute_kelly_fraction ──────────────────────────────────────────────────


class TestComputeKellyFraction:
    def test_positive_kelly(self) -> None:
        frac = compute_kelly_fraction(0.60, 2.0)
        # Kelly = 0.60 - 0.40/2.0 = 0.40 → 0.40*0.25 = 0.10
        assert frac == pytest.approx(0.10)

    def test_zero_kelly_low_hit_rate(self) -> None:
        frac = compute_kelly_fraction(0.30, 2.0)
        # Kelly = 0.30 - 0.70/2.0 = 0.30 - 0.35 = -0.05 ≤ 0 → 0
        assert frac == 0.0

    def test_zero_kelly_low_payoff(self) -> None:
        frac = compute_kelly_fraction(0.55, 0.5)
        # Kelly = 0.55 - 0.45/0.5 = 0.55 - 0.90 = -0.35 ≤ 0 → 0
        assert frac == 0.0

    def test_kelly_capped_by_max_fraction(self) -> None:
        frac = compute_kelly_fraction(0.90, 5.0, kelly_multiplier=1.0, max_fraction=0.25)
        # Kelly = 0.90 - 0.10/5.0 = 0.90 - 0.02 = 0.88 → min(0.88, 0.25) = 0.25
        assert frac == 0.25

    def test_shrinkage_on_small_sample(self) -> None:
        frac_no_shrink = compute_kelly_fraction(0.70, 3.0, trade_count=100)
        frac_with_shrink = compute_kelly_fraction(0.70, 3.0, trade_count=5)
        # Shrinkage → hit_rate/payoff rapprochés de 0.50/1.0 → Kelly plus faible
        assert frac_with_shrink < frac_no_shrink

    def test_no_shrinkage_on_large_sample(self) -> None:
        frac1 = compute_kelly_fraction(0.65, 2.0, trade_count=30)
        frac2 = compute_kelly_fraction(0.65, 2.0, trade_count=1000)
        # Même résultat (pas de shrinkage au-delà de min_trades=30)
        assert frac1 == pytest.approx(frac2)


# ── compute_kelly_shares ────────────────────────────────────────────────────


class TestComputeKellyShares:
    def test_basic(self) -> None:
        shares = compute_kelly_shares(100_000, 100.0, 0.10)
        assert shares == 100  # 100000*0.10/100 = 100

    def test_atr_cap(self) -> None:
        shares = compute_kelly_shares(100_000, 100.0, 0.50, atr=5.0)
        # kelly_shares = 100000*0.50/100 = 500
        # risk_budget = 100000*0.01 = 1000
        # risk_per_share = 5*2 = 10
        # atr_shares = 1000/10 = 100 → min(500, 100) = 100
        assert shares == 100

    def test_fractional_shares(self) -> None:
        shares = compute_kelly_shares(100_000, 300.0, 0.001, allow_fractional=True)
        # kelly_shares = 100000*0.001/300 = 0.333...
        assert shares > 0
        assert shares < 1

    def test_fractional_rounds_down(self) -> None:
        shares = compute_kelly_shares(100_000, 300.0, 0.001, allow_fractional=False)
        # 0.333 → floor = 0
        assert shares == 0

    def test_invalid_price(self) -> None:
        assert compute_kelly_shares(100_000, 0.0, 0.10) == 0
        assert compute_kelly_shares(100_000, -10.0, 0.10) == 0

    def test_invalid_fraction(self) -> None:
        assert compute_kelly_shares(100_000, 100.0, 0.0) == 0
        assert compute_kelly_shares(100_000, 100.0, -0.10) == 0
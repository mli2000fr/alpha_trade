"""Parité breaker B4 — backtest vs prod, jour par jour (pytest).

Vérifie que ``DrawdownCircuitBreaker(policy="b4")`` (backtesting) et
``risk_management.circuit_breaker.CircuitBreaker(policy="b4")`` (prod porté)
sont bit-à-bit identiques jour par jour sur une séquence synthétique qui
couvre : phase normale, trip DD 15%, just_tripped, REBOUND (rearm 25%),
BULL confirmé (streak -> 50%), RR >= 25% (-> 75%), RR >= 50% (-> 100%),
RELAPSE (nouveau trough -> 10%), 2e récupération, nouveau peak.

Même machine d'état, mêmes seuils, même régime SPY, mêmes règles PIT que le
backtest (les deux délèguent à ``backtesting.adaptive_breaker``).
"""
from __future__ import annotations
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtesting.risk_overlay import DrawdownCircuitBreaker
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig

MAX_DD = 0.15
RECOVERY = 0.92
DEGRADED = 0.06
RAMP_DAY = 0.025
RAMP_MAX = 0.25
RAMP_WIN = 5


def _build_sequence():
    """[(date, equity, peak, regime, entry_mode)] couvrant trip/recovery/relapse."""
    seq = []
    peak = 4000.0
    cur = date(2025, 1, 1)

    def day(e, regime, mode):
        nonlocal peak, cur
        peak = max(peak, e)
        seq.append((cur, e, peak, regime, mode))
        cur += timedelta(days=1)

    for i in range(20):
        day(4000 + i * 5, "BULL", "normal")       # montée -> 4095
    day(4100, "BULL", "normal")
    for e in (4060, 4000, 3920, 3840, 3760, 3680, 3600, 3520, 3460, 3400, 3340, 3280):
        day(e, "SLIDE", None)                      # déclin -> trip (peak 4100, seuil 3485)
    for e in (3320, 3360, 3400, 3440, 3480):
        day(e, "REBOUND", "normal")                # récupération REBOUND (rearm 25%)
    for e in (3520, 3560, 3600, 3640, 3660):
        day(e, "BULL", "normal")                   # BULL confirmé : RR 25-50% -> 0.75 (épisode OUVERT)
    for e in (3580, 3460, 3340, 3220):
        day(e, "REBOUND", None)                   # déclin PENDANT un réarmement en cours
                                                  # (régime encore favorable) -> nouveau trough
                                                  # < 3280 -> RELAPSE -> 10%
    for e in (3300, 3440, 3580, 3720, 3860, 4000, 4120, 4240, 4300, 4360):
        day(e, "BULL", "normal")                   # 2e récupération -> 1.00 -> close + nouveau peak
    return seq


def _make_backtest(regime_map):
    return DrawdownCircuitBreaker(
        enabled=True, policy="b4",
        max_dd_pct=MAX_DD, recovery_pct=RECOVERY,
        rolling_peak_window_days=0,
        degraded_entry_allocation_pct=DEGRADED,
        regime_ramp_up_enabled=True,
        regime_ramp_up_pct_per_day=RAMP_DAY,
        regime_ramp_up_max_pct=RAMP_MAX,
        regime_ramp_up_peak_window_days=RAMP_WIN,
        spy_regime_map=regime_map,
    )


def _make_prod(regime_map):
    cfg = RiskConfig(
        max_portfolio_drawdown_pct=MAX_DD,
        max_daily_loss_pct=0.05,
        recovery_pct=RECOVERY,
        rolling_peak_window_days=0,
        degraded_entry_allocation_pct=DEGRADED,
        regime_ramp_up_enabled=True,
        regime_ramp_up_pct_per_day=RAMP_DAY,
        regime_ramp_up_max_pct=RAMP_MAX,
        regime_ramp_up_peak_window_days=RAMP_WIN,
        account_equity=4000.0,
        policy="b4",
        spy_regime_map=regime_map,
    )
    return CircuitBreaker(cfg, PnLSnapshot(daily_pnl=None))


def test_b4_breaker_prod_parity_daily():
    seq = _build_sequence()
    regime_map = {d: r for d, _, _, r, _ in seq}
    bt = _make_backtest(regime_map)
    prod = _make_prod(regime_map)
    trips = 0
    relapses = 0
    max_alloc = 0.0
    prev_alloc = 1.0
    for i, (d, equity, peak, _r, mode) in enumerate(seq):
        em = mode or None
        # BACKTEST — ordre simulateur
        bt.set_spy_regime(d)
        bt.update(equity, peak)
        bt_just = bt.just_tripped()
        bt.update_regime_streak(em, equity)
        bt_alloc = bt.allocation_scale(em)
        # PROD — mêmes inputs, mêmes ordre
        prod.set_spy_regime(d)
        prod.update_adaptive(equity, peak)
        prod_just = prod.just_tripped()
        prod.update_regime_streak(em, equity)
        prod_alloc = prod.allocation_scale(em)

        # État trippé / allocation / just_tripped / streak
        assert bt._tripped == prod._tripped, f"jour {i}: tripped bt={bt._tripped} prod={prod._tripped}"
        assert abs(bt_alloc - prod_alloc) < 1e-9, f"jour {i}: alloc bt={bt_alloc:.6f} prod={prod_alloc:.6f}"
        assert bt_just == prod_just, f"jour {i}: just bt={bt_just} prod={prod_just}"
        # Régime utilisé identique
        assert bt._regime_today == prod._regime_today, f"jour {i}: régime bt={bt._regime_today} prod={prod._regime_today}"
        # Machine d'état (épisode) identique : peak / trough / allocation / streak / rearm_start_dd
        if bt._episode is not None and prod._episode is not None:
            assert abs(bt._episode.peak - prod._episode.peak) < 1e-9, f"jour {i}: episode.peak"
            assert abs(bt._episode.trough - prod._episode.trough) < 1e-9, f"jour {i}: episode.trough"
            assert abs(bt._episode.allocation - prod._episode.allocation) < 1e-9, f"jour {i}: episode.allocation"
            assert bt._episode.favorable_streak == prod._episode.favorable_streak, f"jour {i}: streak"
            assert bt._episode.rearm_start_dd == prod._episode.rearm_start_dd, f"jour {i}: rearm_start_dd"
        if bt_just:
            trips += 1
        max_alloc = max(max_alloc, bt_alloc)
        # RELAPSE observable : l'allocation revient au plancher (0.10) alors
        # qu'elle avait été réarmée (> 0.11), pendant que l'épisode est trippé.
        # (relapse_day est un latch consommé dans update() -> on le détecte ici.)
        if prev_alloc > 0.11 and bt_alloc <= 0.11 and bt._tripped:
            relapses += 1
        prev_alloc = bt_alloc

    # La séquence doit avoir exercé : au moins 1 trip, une RELAPSE B4,
    # et le réarmement complet à 100% (la ladder B4 est bien couverte).
    assert trips >= 1, f"aucun just_tripped, vu {trips}"
    assert relapses >= 1, f"aucune relapse B4, vu {relapses}"
    assert max_alloc >= 0.999, f"le réarmement à 100% n'a pas été atteint (max={max_alloc:.3f})"

"""Tests CP-V2 — politique side-aware + fenêtre de release (spec gelée 2026-08-22).

Vérifie sur la vraie `build_snapshot` :
  1. Pendant capital_preservation : max_long_exposure=0.40, max_short_exposure=0.25,
     max_gross_exposure=0.65 sur le snapshot.
  2. Fenêtre de release : après le dernier jour de signal CP, le mode reste capital_preservation
     5 séances puis revient à normal à J+6.
  3. Hors CP : les budgets par side sont absents (None) — pas de fuite.
"""
from __future__ import annotations

from datetime import date

from service.market.config import parse_market_regimes
from service.market.regime_manager import build_snapshot


class _FakeMacro:
    def __init__(self, vix: float | None = None) -> None:
        self._vix = vix

    def get_vix_close(self, _d):
        return self._vix

    def get_vix_short_term_close(self, _d):
        return None

    def get_vxn_close(self, _d):
        return None

    def get_vix3m_close(self, _d):
        return None

    def get_move_close(self, _d):
        return None

    def get_rvx_close(self, _d):
        return None

    def get_us10y_history(self, _d, lookback_days):
        return None


def _cp_v2_config(release_sessions: int = 5) -> object:
    return parse_market_regimes({
        "enabled": True,
        "vix": {"enabled": True, "high_threshold": 30.0, "symbol": "VIX.INDX"},
        "vxn": {"enabled": False},
        "vix3m": {"enabled": False},
        "move": {"enabled": False},
        "rvx": {"enabled": False},
        "yields": {"enabled": False},
        "sentiment_circuit_breaker": {"enabled": False},
        "capital_preservation_policy": "cp_v2",
        "hysteresis": {
            "enabled": True,
            "enter_soft_signals_required": 1,
            "enter_confirm_days": 2,
            "exit_soft_signals_max": 0,
            "exit_confirm_days": 1,
            "min_hold_days_defensive": 1,
            "hard_trigger_immediate": True,
            "hard_exit_confirm_days": 1,
        },
        "capital_preservation_max_gross_exposure": 0.65,
        "capital_preservation_max_long_exposure": 0.40,
        "capital_preservation_reserved_short_exposure": 0.25,
        "capital_preservation_release_sessions": release_sessions,
    })


def _run_schedule(cfg, vix_by_day):
    prev = None
    rows = []
    for d, vix in vix_by_day:
        snap = build_snapshot(d, config=cfg, macro_provider=_FakeMacro(vix=vix),
                              previous_state=prev, use_cache=False)
        prev = snap.next_state
        rows.append((d, snap.mode, snap.max_long_exposure, snap.max_short_exposure,
                     snap.max_gross_exposure))
    return rows


def test_cp_v2_per_side_budgets_during_cp():
    cfg = _cp_v2_config()
    # 3 jours vix=31 (soft source, entre en CP au j2), puis 1 jour normal
    rows = _run_schedule(cfg, [(date(2026, 1, 5 + i), 31.0 if i < 3 else 20.0) for i in range(4)])
    cp_row = rows[1]  # j2 : capital_preservation
    assert cp_row[1] == "capital_preservation"
    assert cp_row[2] == 0.40  # max_long_exposure
    assert cp_row[3] == 0.25  # max_short_exposure (réserve)
    assert cp_row[4] == 0.65  # gross total conservé


def test_cp_v2_release_window_five_sessions_then_normal():
    cfg = _cp_v2_config(release_sessions=5)
    # 3 jours CP (signal), puis 10 jours normal : dernier signal = index 2
    rows = _run_schedule(cfg, [(date(2026, 1, 5 + i), 31.0 if i < 3 else 20.0) for i in range(13)])
    # J+1..J+5 après le dernier signal (index 3..7) : encore capital_preservation
    for i in range(3, 8):
        assert rows[i][1] == "capital_preservation", f"jour {i} devrait être CP"
        assert rows[i][2] == 0.40 and rows[i][3] == 0.25  # restrictions maintenues
    # J+6 (index 8) : retour normal
    assert rows[8][1] == "normal"
    assert rows[8][2] is None and rows[8][3] is None  # budgets nettoyés


def test_cp_v2_no_release_no_behavior_change():
    # release_sessions=0 → pas de maintien post-CP : on sort dès que l'hystérésis le permet
    cfg = _cp_v2_config(release_sessions=0)
    rows = _run_schedule(cfg, [(date(2026, 1, 5 + i), 31.0 if i < 3 else 20.0) for i in range(6)])
    # avec exit_confirm_days=1 / min_hold=1 : j4 (1er jour normal) → retour normal direct
    assert rows[3][1] == "normal"


def test_apply_account_cp_policy_long_only_clears_per_side_budgets():
    # Variante B (E42) : compte long-only → budgets par side CP-V2 retirés,
    # gross 0.65 conservé (release J+6 + hystérésis restent via le snapshot).
    from risk_management.config import RiskConfig
    from risk_management.regime_apply import apply_account_cp_policy

    cfg = RiskConfig(max_long_exposure=0.40, max_short_exposure=0.25, max_gross_exposure=0.65)
    out = apply_account_cp_policy(cfg, account_long_only=True)
    assert out.max_long_exposure is None
    assert out.max_short_exposure is None
    assert out.max_gross_exposure == 0.65  # gross conservé
    assert out is not cfg  # nouveau RiskConfig, pas de mutation


def test_apply_account_cp_policy_short_capable_keeps_budgets():
    # Compte short-capable (6L/2S) : CP-V2 complet inchangé.
    from risk_management.config import RiskConfig
    from risk_management.regime_apply import apply_account_cp_policy

    cfg = RiskConfig(max_long_exposure=0.40, max_short_exposure=0.25)
    out = apply_account_cp_policy(cfg, account_long_only=False)
    assert out.max_long_exposure == 0.40
    assert out.max_short_exposure == 0.25
    assert out is cfg  # aucun changement

"""Tests pour les contraintes directionnelles et la configuration — Sprint Maître 6."""

from __future__ import annotations

import pytest

from risk_management.config import RiskConfig
from risk_management.constraints import ConstraintChecker, PortfolioState
from core.ml_selection_contract import SelectionCapacity
from core.direction import compute_initial_stop_price


# ── PortfolioState directionnel ─────────────────────────────────────────────

def test_portfolio_state_defaults() -> None:
    state = PortfolioState()
    assert state.position_count == 0
    assert state.long_count == 0
    assert state.short_count == 0
    assert state.gross_notional == 0.0
    assert state.net_notional == 0.0


def test_portfolio_state_add_long() -> None:
    state = PortfolioState()
    state.add_position(notional=5000.0, sector="Tech", side="long", symbol="AAPL")
    assert state.position_count == 1
    assert state.long_count == 1
    assert state.short_count == 0
    assert state.long_notional == 5000.0
    assert state.short_notional == 0.0
    assert state.gross_notional == 5000.0
    assert state.net_notional == 5000.0
    assert state.sector_notional["Tech"] == 5000.0


def test_portfolio_state_add_short() -> None:
    state = PortfolioState()
    state.add_position(notional=3000.0, sector="Finance", side="short", symbol="JPM")
    assert state.short_count == 1
    assert state.short_notional == 3000.0
    assert state.long_count == 0
    assert state.net_notional == -3000.0


def test_portfolio_state_mixed() -> None:
    state = PortfolioState()
    state.add_position(notional=10000.0, sector="Tech", side="long", symbol="AAPL")
    state.add_position(notional=4000.0, sector="Tech", side="short", symbol="NVDA")
    assert state.position_count == 2
    assert state.long_count == 1
    assert state.short_count == 1
    assert state.long_notional == 10000.0
    assert state.short_notional == 4000.0
    assert state.gross_notional == 14000.0
    assert state.net_notional == 6000.0
    assert state.sector_notional["Tech"] == 14000.0


# ── Contraintes directionnelles ─────────────────────────────────────────────

@pytest.fixture
def risk_cfg() -> RiskConfig:
    return RiskConfig(
        account_equity=100_000.0,
        max_positions=10,
        max_long_positions=8,
        max_short_positions=3,
        max_position_weight=0.10,
        max_sector_weight=0.30,
        max_gross_exposure=1.0,
    )


def test_constraint_max_long_positions(risk_cfg) -> None:
    checker = ConstraintChecker(risk_cfg)
    state = PortfolioState()
    # Remplir à 8 longs
    for i in range(8):
        state.add_position(notional=1000.0, sector="X", side="long", symbol=f"S{i}")
    shares, reason = checker.check("S9", "X", 10.0, 100.0, state, side="long")
    assert shares == 0.0
    assert "max_long_positions" in reason


def test_constraint_max_short_positions(risk_cfg) -> None:
    checker = ConstraintChecker(risk_cfg)
    state = PortfolioState()
    for i in range(3):
        state.add_position(notional=1000.0, sector="X", side="short", symbol=f"S{i}")
    shares, reason = checker.check("S4", "X", 10.0, 100.0, state, side="short")
    assert shares == 0.0
    assert "max_short_positions" in reason


def test_constraint_long_not_limited_by_short_cap(risk_cfg) -> None:
    """Le cap short ne limite pas les longs."""
    checker = ConstraintChecker(risk_cfg)
    state = PortfolioState()
    # Remplir 3 shorts (max atteint)
    for i in range(3):
        state.add_position(notional=1000.0, sector="X", side="short", symbol=f"S{i}")
    # Un long doit passer
    shares, reason = checker.check("L1", "X", 10.0, 100.0, state, side="long")
    assert shares > 0
    assert reason == "OK"


# ── ADV fail-closed ─────────────────────────────────────────────────────────

def test_adv_fail_closed_rejects_missing_adv() -> None:
    cfg = RiskConfig(account_equity=100_000.0, max_position_pct_of_adv=0.01)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    shares, reason = checker.check("AAPL", "Tech", 100.0, 150.0, state, adv_usd=None)
    assert shares == 0.0
    assert reason == "adv_unavailable"


def test_adv_fail_closed_rejects_zero_adv() -> None:
    cfg = RiskConfig(account_equity=100_000.0, max_position_pct_of_adv=0.01)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    shares, reason = checker.check("AAPL", "Tech", 100.0, 150.0, state, adv_usd=0.0)
    assert shares == 0.0
    assert reason == "adv_unavailable"


def test_adv_ok_when_not_configured() -> None:
    """Si max_position_pct_of_adv est None, ADV absent ne bloque pas."""
    cfg = RiskConfig(account_equity=100_000.0, max_position_pct_of_adv=None)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    shares, reason = checker.check("AAPL", "Tech", 10.0, 100.0, state, adv_usd=None)
    assert shares > 0
    assert reason == "OK"


# ── Stop directionnel ───────────────────────────────────────────────────────

def test_stop_long_below_entry() -> None:
    stop = compute_initial_stop_price("buy", 100.0, risk_per_share=5.0)
    assert stop is not None
    assert stop < 100.0  # long: stop sous l'entrée


def test_stop_short_above_entry() -> None:
    stop = compute_initial_stop_price("sell", 100.0, risk_per_share=5.0)
    assert stop is not None
    assert stop > 100.0  # short: stop au-dessus de l'entrée


# ── Gross/net ───────────────────────────────────────────────────────────────

def test_gross_notional_sum_of_long_and_short() -> None:
    state = PortfolioState()
    state.add_position(notional=7000.0, sector="A", side="long")
    state.add_position(notional=3000.0, sector="A", side="short")
    assert state.gross_notional == 10000.0


def test_net_notional_long_minus_short() -> None:
    state = PortfolioState()
    state.add_position(notional=7000.0, sector="A", side="long")
    state.add_position(notional=3000.0, sector="A", side="short")
    assert state.net_notional == 4000.0


# ── RiskConfig fingerprint ──────────────────────────────────────────────────

def test_risk_config_fingerprint_is_stable() -> None:
    cfg1 = RiskConfig(account_equity=100_000.0, max_positions=10)
    cfg2 = RiskConfig(account_equity=100_000.0, max_positions=10)
    assert cfg1.fingerprint == cfg2.fingerprint


def test_risk_config_fingerprint_changes_with_param() -> None:
    cfg1 = RiskConfig(account_equity=100_000.0)
    cfg2 = RiskConfig(account_equity=200_000.0)
    assert cfg1.fingerprint != cfg2.fingerprint


def test_risk_config_to_dict_roundtrip() -> None:
    cfg = RiskConfig(
        account_equity=150_000.0,
        max_positions=15,
        max_short_positions=5,
        correlation_threshold=0.75,
    )
    d = cfg.to_dict(exclude_defaults=False)
    restored = RiskConfig.from_dict(d)
    assert restored.account_equity == 150_000.0
    assert restored.max_short_positions == 5
    assert restored.fingerprint == cfg.fingerprint


def test_risk_config_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="Clés inconnues"):
        RiskConfig.from_dict({"account_equity": 100000, "fantasy_key": 123})


def test_risk_config_with_overrides() -> None:
    cfg = RiskConfig(account_equity=100_000.0)
    overridden = cfg.with_overrides(max_positions=5, correlation_threshold=0.70)
    assert overridden.max_positions == 5
    assert overridden.correlation_threshold == 0.70
    assert overridden.account_equity == 100_000.0
    assert overridden.fingerprint != cfg.fingerprint


def test_risk_config_with_overrides_rejects_unknown() -> None:
    cfg = RiskConfig()
    with pytest.raises(ValueError, match="Overrides inconnus"):
        cfg.with_overrides(fake_param=42)  # type: ignore[call-arg]


# ── Section 17 Point 6.1 : from_preset ──────────────────────────────────────

def test_from_preset_resolves_preset_by_equity() -> None:
    """from_preset avec equity=50000 résout le preset approprié."""
    cfg = RiskConfig.from_preset(equity=50000.0)
    assert isinstance(cfg.fingerprint, str)
    assert len(cfg.fingerprint) == 16
    # Le preset définit des paramètres de risque, pas l'equity elle-même
    assert cfg.risk_per_trade_pct > 0


def test_from_preset_rejects_unknown_overrides() -> None:
    """from_preset rejette les clés inconnues dans les overrides."""
    with pytest.raises(ValueError, match="Clés inconnues"):
        RiskConfig.from_preset(equity=50000.0, fantasy_key=999)


def test_from_preset_applies_overrides() -> None:
    """from_preset applique les overrides après le preset."""
    cfg = RiskConfig.from_preset(equity=50000.0, max_positions=42, dry_run=True)
    assert cfg.max_positions == 42
    assert cfg.dry_run is True


def test_from_preset_requires_equity_or_key() -> None:
    """from_preset sans equity ni preset_key lève une erreur."""
    with pytest.raises(ValueError, match="preset_key ou equity"):
        RiskConfig.from_preset()


# ── Section 17 Point 6.1 : from_yaml_section ────────────────────────────────

def test_from_yaml_section_merges_yaml_and_preset() -> None:
    """from_yaml_section fusionne YAML + preset, preset prioritaire."""
    yaml_data = {
        "max_positions": 30,
        "max_short_positions": 5,
        "short_selling_enabled": True,
    }
    cfg = RiskConfig.from_yaml_section(yaml_data=yaml_data, equity=100000.0)
    assert isinstance(cfg.fingerprint, str)
    assert cfg.max_short_positions == 5


def test_from_yaml_section_ignores_non_risk_keys() -> None:
    """Les clés YAML non-RiskConfig sont ignorées silencieusement."""
    yaml_data = {
        "max_positions": 10,
        "dashboard_refresh_seconds": 5,
        "email_alerts": True,
    }
    cfg = RiskConfig.from_yaml_section(yaml_data=yaml_data)
    assert cfg.max_positions == 10
    assert isinstance(cfg.fingerprint, str)


def test_from_yaml_section_overrides_win() -> None:
    """Les overrides explicites écrasent tout (YAML + preset)."""
    cfg = RiskConfig.from_yaml_section(
        yaml_data={"max_positions": 10},
        equity=100000.0,
        max_positions=99,
    )
    assert cfg.max_positions == 99


# ── Section 17 Point 6.1 : load_risk_config ─────────────────────────────────

def test_load_risk_config_returns_valid_config() -> None:
    """load_risk_config produit une RiskConfig valide avec fingerprint."""
    from risk_management.config import load_risk_config

    cfg = load_risk_config(equity=100000.0)
    assert isinstance(cfg, RiskConfig)
    assert isinstance(cfg.fingerprint, str)
    assert cfg.account_equity == 100000.0


def test_load_risk_config_cli_overrides_win() -> None:
    """Les CLI overrides écrasent tout le reste."""
    from risk_management.config import load_risk_config

    cfg = load_risk_config(
        equity=100000.0,
        cli_overrides={"max_positions": 7, "dry_run": True},
    )
    assert cfg.max_positions == 7
    assert cfg.dry_run is True


# ── Section 17 Point 6.5 : revalidate_portfolio ─────────────────────────────

def test_revalidate_portfolio_empty_state_passes() -> None:
    """Un portefeuille vide ne génère aucune violation."""
    checker = ConstraintChecker(RiskConfig())
    state = PortfolioState()
    violations = checker.revalidate_portfolio(state)
    assert len(violations) == 0


def test_revalidate_portfolio_detects_long_count_exceeded() -> None:
    """revalidate_portfolio détecte le dépassement de max_long_positions."""
    cfg = RiskConfig(max_positions=3, max_long_positions=2, max_short_positions=1)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    for _ in range(3):
        state.add_position(notional=1000.0, sector="Tech", side="long")
    violations = checker.revalidate_portfolio(state)
    assert any("long_count_exceeded" in v for v in violations)


def test_revalidate_portfolio_detects_gross_exposure_exceeded() -> None:
    """revalidate_portfolio détecte le dépassement d'exposition brute."""
    cfg = RiskConfig(account_equity=10000.0, max_gross_exposure=0.5)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    state.add_position(notional=6000.0, sector="Tech", side="long")
    violations = checker.revalidate_portfolio(state)
    assert any("gross_exposure_exceeded" in v for v in violations)


def test_revalidate_portfolio_detects_net_exposure_violation() -> None:
    """revalidate_portfolio détecte la violation de neutralité nette."""
    cfg = RiskConfig(
        account_equity=10000.0,
        enforce_net_exposure=True,
        net_exposure_target=0.0,
        net_exposure_tolerance=0.05,
    )
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    state.add_position(notional=2000.0, sector="Tech", side="long")
    violations = checker.revalidate_portfolio(state)
    assert any("net_exposure_violation" in v for v in violations)


def test_revalidate_portfolio_detects_sector_weight_exceeded() -> None:
    """revalidate_portfolio détecte le dépassement de poids sectoriel."""
    cfg = RiskConfig(account_equity=10000.0, max_sector_weight=0.10)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    state.add_position(notional=1500.0, sector="Tech", side="long")
    violations = checker.revalidate_portfolio(state)
    assert any("sector_weight_exceeded" in v for v in violations)


def test_revalidate_portfolio_detects_min_notional_violation() -> None:
    """revalidate_portfolio détecte les positions sous le notional minimum."""
    cfg = RiskConfig(account_equity=100000.0, min_position_notional=500.0)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    state.add_position(notional=100.0, sector="Tech", side="long")
    violations = checker.revalidate_portfolio(
        state,
        positions=[{"symbol": "TINY", "sector": "Tech", "notional": 100.0}],
    )
    assert any("min_notional_violation" in v for v in violations)


def test_revalidate_portfolio_conformant_portfolio_no_violations() -> None:
    """Un portefeuille qui respecte toutes les contraintes n'a pas de violation."""
    cfg = RiskConfig(
        account_equity=100000.0,
        max_positions=10,
        max_position_weight=0.10,
        max_sector_weight=0.30,
        max_gross_exposure=1.0,
        min_position_notional=500.0,
    )
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    state.add_position(notional=5000.0, sector="Tech", side="long")
    state.add_position(notional=3000.0, sector="Health", side="short")
    violations = checker.revalidate_portfolio(
        state,
        positions=[
            {"symbol": "AAPL", "sector": "Tech", "notional": 5000.0},
            {"symbol": "PFE", "sector": "Health", "notional": 3000.0},
        ],
    )
    assert len(violations) == 0


def test_revalidate_portfolio_sector_ticker_count_exceeded() -> None:
    """revalidate_portfolio détecte le dépassement de tickers par secteur."""
    cfg = RiskConfig(max_tickers_per_sector=2)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    for _ in range(3):
        state.add_position(notional=1000.0, sector="Tech", side="long")
    violations = checker.revalidate_portfolio(state)
    assert any("sector_ticker_count_exceeded" in v for v in violations)


# ── Section 17 Point 6.3 : factor constraints on sized weights ──────────────

def test_factor_constraints_on_sized_weights_empty_weights() -> None:
    """Des poids vides ne génèrent pas de violation."""
    import numpy as np
    from datetime import date

    from risk_management.factor_model import (
        FactorCovariance,
        check_factor_constraints_on_sized_weights,
    )

    cov = FactorCovariance(
        factor_cov=np.eye(4),
        factor_names=["market", "size", "momentum", "value"],
        specific_variances={},
        estimation_date=date(2026, 1, 1),
    )
    violations = check_factor_constraints_on_sized_weights({}, {}, cov)
    assert len(violations) == 0


def test_factor_constraints_on_sized_weights_no_exposures() -> None:
    """Si aucun symbole n'a d'exposition, pas de violation."""
    import numpy as np
    from datetime import date

    from risk_management.factor_model import (
        FactorCovariance,
        check_factor_constraints_on_sized_weights,
    )

    cov = FactorCovariance(
        factor_cov=np.eye(1),
        factor_names=["market"],
        specific_variances={},
        estimation_date=date(2026, 1, 1),
    )
    violations = check_factor_constraints_on_sized_weights(
        {"AAPL": 0.05}, {}, cov
    )
    assert len(violations) == 0


def test_freshness_gate_blocks_critical_stale() -> None:
    """Section 17 Point 6.4 : FreshnessGate bloque quand price_data est stale (>300s)."""
    from datetime import datetime, timedelta, timezone

    from risk_management.freshness_gate import FreshnessConfig, FreshnessGate

    now = datetime.now(timezone.utc)
    old = now - timedelta(minutes=10)  # 600s > max_age_price_data=300s → stale

    gate = FreshnessGate(FreshnessConfig())
    result = gate.evaluate(
        price_data_at=old,
        reference_time=now,
    )
    assert result.must_block, "Des prix vieux de 10min doivent bloquer (CRITICAL, max 300s)"
    assert "price_data" in result.blocked_dimensions


def test_freshness_gate_allows_fresh_data() -> None:
    """Des données fraîches ne bloquent pas (max_age_price_data=300s)."""
    from datetime import datetime, timedelta, timezone

    from risk_management.freshness_gate import FreshnessConfig, FreshnessGate

    now = datetime.now(timezone.utc)
    # Dans la limite de 300s pour price_data
    very_recent = now - timedelta(seconds=60)

    gate = FreshnessGate(FreshnessConfig())
    result = gate.evaluate(
        price_data_at=very_recent,
        ml_model_at=very_recent,
        market_regime_at=very_recent,
        volume_adv_at=very_recent,
        calibration_at=very_recent,
        reference_time=now,
    )
    assert not result.must_block


def test_freshness_gate_degraded_missing_noncricital() -> None:
    """Une dimension REQUIRED stale dégrade mais ne bloque pas."""
    from datetime import datetime, timedelta, timezone

    from risk_management.freshness_gate import FreshnessConfig, FreshnessGate

    now = datetime.now(timezone.utc)
    very_recent = now - timedelta(seconds=60)  # < 300s pour price_data
    old = now - timedelta(days=5)  # ADV vieux de 5 jours → REQUIRED stale

    gate = FreshnessGate(FreshnessConfig())
    result = gate.evaluate(
        price_data_at=very_recent,  # CRITICAL: frais
        ml_model_at=very_recent,  # CRITICAL: frais
        volume_adv_at=old,  # REQUIRED: stale
        reference_time=now,
    )
    assert not result.must_block, "ADV stale ne doit pas bloquer (REQUIRED, pas CRITICAL)"
    assert result.is_degraded

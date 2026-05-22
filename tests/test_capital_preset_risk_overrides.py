"""Sprint S3 / A-011 — overrides risk_max_drawdown_pct / risk_max_daily_loss_pct par préset.
Sprint S1 / A-001 — cohérence risk_max_positions / risk_min_position_notional.
Sprint S2 / A-006 — PDT rule 'auto' sur presets margin ≥ 25k$.
Sprint S2 / A-007 — selector_min_close ≥ 10.0 sur tous les presets.

Vérifie que :
- Chaque préset capital définit ``risk_max_drawdown_pct`` et
  ``risk_max_daily_loss_pct``.
- Les valeurs sont décroissantes en strictness (compte plus gros =>
  tolérance plus large) — cohérence métier.
- Les valeurs sont dans des plages réalistes (drawdown ∈ [0.05, 0.25],
  daily_loss ∈ [0.02, 0.07]).
- Le CLI ``risk_management`` accepte les flags ``--max-portfolio-drawdown-pct``
  et ``--max-daily-loss-pct``.
- [A-001] ``risk_max_positions × risk_min_position_notional ≤ 0.95 × max_equity``
  (solvabilité notionnelle).
- [A-001] Le preset micro-compte ``capital_0_2000_eur`` a au plus 5 positions.
- [A-006] Les presets margin ont ``execution_pdt_rule='auto'``.
- [A-007] Tous les presets ont ``selector_min_close ≥ 10.0``.
- [A-016] Les presets cash ont ``execution_pdt_rule='off'`` (PDT N/A).
"""
from __future__ import annotations

import pytest

from common.capital_presets import load_capital_presets
from risk_management.cli import build_arg_parser
from risk_management.config import RiskConfig

REQUIRED_KEYS = ("risk_max_drawdown_pct", "risk_max_daily_loss_pct")


@pytest.fixture(scope="module")
def presets():
    return list(load_capital_presets())


def test_all_presets_define_risk_overrides(presets):
    for preset in presets:
        for key in REQUIRED_KEYS:
            assert key in preset.values, (
                f"Le preset '{preset.key}' ne définit pas '{key}'."
            )


def test_drawdown_values_in_realistic_range(presets):
    for preset in presets:
        dd = float(preset.values["risk_max_drawdown_pct"])
        assert 0.05 <= dd <= 0.25, f"{preset.key}: drawdown {dd} hors plage [0.05, 0.25]"


def test_daily_loss_values_in_realistic_range(presets):
    for preset in presets:
        dl = float(preset.values["risk_max_daily_loss_pct"])
        assert 0.02 <= dl <= 0.07, f"{preset.key}: daily_loss {dl} hors plage [0.02, 0.07]"


def test_thresholds_increase_with_account_size(presets):
    """Convention métier : tranche supérieure ⇒ tolérance ≥ tranche inférieure."""
    dds = [float(p.values["risk_max_drawdown_pct"]) for p in presets]
    dls = [float(p.values["risk_max_daily_loss_pct"]) for p in presets]
    assert dds == sorted(dds), f"drawdown_pct doit être croissant entre presets: {dds}"
    assert dls == sorted(dls), f"daily_loss_pct doit être croissant entre presets: {dls}"


def test_small_account_has_strictest_thresholds(presets):
    smallest = next(p for p in presets if p.key == "capital_0_5000")
    biggest = next(p for p in presets if p.key == "capital_100001_plus")
    assert float(smallest.values["risk_max_drawdown_pct"]) < float(
        biggest.values["risk_max_drawdown_pct"]
    )
    assert float(smallest.values["risk_max_daily_loss_pct"]) <= float(
        biggest.values["risk_max_daily_loss_pct"]
    )


def test_cli_exposes_threshold_flags():
    parser = build_arg_parser()
    args = parser.parse_args([
        "--max-portfolio-drawdown-pct", "0.08",
        "--max-daily-loss-pct", "0.03",
    ])
    assert args.max_portfolio_drawdown_pct == pytest.approx(0.08)
    assert args.max_daily_loss_pct == pytest.approx(0.03)


def test_risk_config_accepts_overrides():
    cfg = RiskConfig(
        account_equity=5000.0,
        max_portfolio_drawdown_pct=0.08,
        max_daily_loss_pct=0.03,
    )
    assert cfg.max_portfolio_drawdown_pct == pytest.approx(0.08)
    assert cfg.max_daily_loss_pct == pytest.approx(0.03)


def test_preset_values_match_risk_config_defaults_can_construct(presets):
    """Sanity : chaque triplet preset peut alimenter un RiskConfig valide."""
    for preset in presets:
        cfg = RiskConfig(
            account_equity=max(preset.min_equity + 1.0, 1000.0),
            max_portfolio_drawdown_pct=float(preset.values["risk_max_drawdown_pct"]),
            max_daily_loss_pct=float(preset.values["risk_max_daily_loss_pct"]),
        )
        assert cfg.max_portfolio_drawdown_pct > 0
        assert cfg.max_daily_loss_pct > 0


# ---------------------------------------------------------------------------
# Sprint S1 / A-001 — cohérence max_positions × min_notional vs equity
# ---------------------------------------------------------------------------

def test_positions_notional_solvency(presets):
    """[A-001] max_positions × min_position_notional ≤ 0.95 × max_equity.

    Garantit qu'un portefeuille entièrement chargé au minimum de notionnel
    reste en dessous de 95 % du capital de la tranche.
    Note : ``capital_0_2000_eur`` a max_equity=2000 EUR ≈ 2000 USD (approx).
    """
    for preset in presets:
        max_equity = preset.max_equity
        if max_equity is None:
            # Grand compte sans plafond : on utilise min_equity + 1 comme proxy
            continue
        max_pos = int(preset.values.get("risk_max_positions", 1))
        min_notional = float(preset.values.get("risk_min_position_notional", 0))
        total_min_notional = max_pos * min_notional
        limit = 0.95 * max_equity
        assert total_min_notional <= limit, (
            f"{preset.key}: {max_pos} positions × {min_notional}$ = {total_min_notional}$ "
            f"> 0.95 × {max_equity} = {limit}$ — portefeuille insolvable au minimum notionnel"
        )


def test_capital_preset_risk_per_trade_micro(presets):
    micro = next((p for p in presets if p.key == "capital_0_2000_eur"), None)
    assert micro is not None, "Preset capital_0_2000_eur non trouvé"
    assert float(micro.values["risk_per_trade_pct"]) == pytest.approx(0.01)


def test_micro_account_max_positions_coherent(presets):
    """[A-001] Le preset capital_0_2000_eur doit avoir au plus 5 positions.

    Un compte de ~2 000 € avec >5 positions implique des tickets si petits
    que les frais de transaction deviennent supérieurs à l'alpha attendu.
    """
    micro = next((p for p in presets if p.key == "capital_0_2000_eur"), None)
    if micro is None:
        pytest.skip("Preset capital_0_2000_eur non trouvé")
    max_pos = int(micro.values["risk_max_positions"])
    assert max_pos <= 5, (
        f"capital_0_2000_eur.risk_max_positions={max_pos} > 5 — "
        f"tickets trop petits pour être rentables après frais"
    )


def test_micro_account_min_notional_viable(presets):
    """[A-001] Le preset capital_0_2000_eur doit avoir un ticket min ≥ 400 USD.

    Sous 400 USD, la commission relative (≥ 1 USD/trade Alpaca) dépasse 0.25 %
    par aller-retour, détruisant l'alpha sur un swing trade standard de 5-8 %.
    """
    micro = next((p for p in presets if p.key == "capital_0_2000_eur"), None)
    if micro is None:
        pytest.skip("Preset capital_0_2000_eur non trouvé")
    min_notional = float(micro.values["risk_min_position_notional"])
    assert min_notional >= 400.0, (
        f"capital_0_2000_eur.risk_min_position_notional={min_notional} < 400$ — "
        f"frais relatifs trop élevés pour le swing trade"
    )


# ---------------------------------------------------------------------------
# Sprint S1 / A-016 — PDT rule cohérente avec account_type
# ---------------------------------------------------------------------------

def test_cash_presets_have_pdt_off(presets):
    """[A-016] Tout preset cash doit avoir pdt_rule='off' (PDT N/A sur cash)."""
    for preset in presets:
        account_type = preset.values.get("execution_account_type", "cash")
        pdt_rule = preset.values.get("execution_pdt_rule", "off")
        if account_type == "cash":
            assert pdt_rule == "off", (
                f"{preset.key}: account_type=cash mais pdt_rule='{pdt_rule}' "
                f"(devrait être 'off' — PDT ne s'applique qu'aux comptes margin)"
            )


def test_positions_increase_with_account_size(presets):
    """Convention métier : tranche supérieure peut gérer plus de positions."""
    max_positions = [int(p.values["risk_max_positions"]) for p in presets]
    assert max_positions == sorted(max_positions), (
        f"risk_max_positions doit être croissant entre presets: {max_positions}"
    )


# ---------------------------------------------------------------------------
# Sprint S2 / A-006 — PDT rule 'auto' sur presets margin
# ---------------------------------------------------------------------------

def test_margin_presets_have_pdt_auto(presets):
    """[A-006] Tout preset margin doit avoir pdt_rule='auto'.

    Sur un compte margin, si l'equity chute temporairement sous 25 000 $,
    la règle PDT doit être appliquée automatiquement (4e day-trade bloqué)
    pour éviter les restrictions broker (min-equity call, 90 jours de restriction).
    cf. execution_engine/config.py:applies_pdt_limit()
    """
    margin_presets = [
        p for p in presets
        if p.values.get("execution_account_type") == "margin"
    ]
    assert margin_presets, "Aucun preset margin trouvé dans capital_presets.yaml"
    for preset in margin_presets:
        pdt_rule = preset.values.get("execution_pdt_rule", "off")
        assert pdt_rule == "auto", (
            f"{preset.key}: account_type=margin mais pdt_rule='{pdt_rule}' "
            f"(devrait être 'auto' — protection en cas de drawdown sous 25k$)"
        )


# ---------------------------------------------------------------------------
# Sprint S2 / A-007 — selector_min_close ≥ 10.0 sur tous les presets
# ---------------------------------------------------------------------------

def test_all_presets_selector_min_close_gte_10(presets):
    """[A-007] Tous les presets doivent avoir selector_min_close ≥ 10.0.

    Les actions < 10 USD ont des frais relatifs disproportionnés et des spreads
    IEX plus larges. STRICT_SWING_CASH_FILTERS.min_close = 10.0 fixe le plancher.
    """
    for preset in presets:
        min_close = float(preset.values.get("selector_min_close", 0.0))
        assert min_close >= 10.0, (
            f"{preset.key}: selector_min_close={min_close} < 10.0 — "
            f"non aligné avec STRICT_SWING_CASH_FILTERS.min_close=10.0"
        )


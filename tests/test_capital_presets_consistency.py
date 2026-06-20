"""A-005 — cohérence documentée entre presets de capital et profil strict.

Le chargeur doit désormais refuser :
- tout écart selector vs ``STRICT_SWING_CASH_FILTERS`` sans justification dédiée ;
- toute justification devenue obsolète ;
- tout désalignement entre les deux alias RS.
"""
from __future__ import annotations

import textwrap

import pytest

from common.capital_presets import collect_strict_profile_deviations, load_capital_presets


@pytest.fixture(scope="module")
def presets():
    return list(load_capital_presets())


def test_all_default_presets_document_current_strict_profile_deviations(presets):
    assert presets, "Aucun preset chargé"
    assert any(preset.strict_profile_justifications for preset in presets)

    for preset in presets:
        deviations = collect_strict_profile_deviations(preset)
        documented_keys = set(preset.strict_profile_justifications.keys())
        assert documented_keys == set(deviations.keys()), (
            f"{preset.key}: divergences={sorted(deviations.keys())}, "
            f"justifications={sorted(documented_keys)}"
        )
        for selector_key, reason in preset.strict_profile_justifications.items():
            assert reason.strip(), f"{preset.key}: justification vide pour {selector_key}"


def test_loading_yaml_with_undocumented_strict_profile_divergence_fails(tmp_path):
    config_path = tmp_path / "capital_presets_invalid.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            presets:
              - key: invalid_micro
                label: "Invalid"
                min_equity: 0
                max_equity: 1000
                description: "Preset volontairement invalide"
                values:
                  selector_min_beta_126: 0.7
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sans justification"):
        load_capital_presets(config_path)


def test_loading_yaml_with_stale_justification_fails(tmp_path):
    config_path = tmp_path / "capital_presets_stale.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            presets:
              - key: stale_doc
                label: "Stale"
                min_equity: 0
                max_equity: 1000
                description: "Justification devenue inutile"
                strict_profile_justifications:
                  selector_min_close: "Commentaire obsolète"
                values:
                  selector_min_close: 10.0
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="justifications devenues inutiles"):
        load_capital_presets(config_path)


def test_loading_yaml_with_rs_alias_mismatch_fails(tmp_path):
    config_path = tmp_path / "capital_presets_alias_mismatch.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            presets:
              - key: alias_mismatch
                label: "Alias mismatch"
                min_equity: 0
                max_equity: 1000
                description: "Alias RS incohérents"
                strict_profile_justifications:
                  selector_min_ibd_rs_rank: "Divergence voulue pour le test"
                values:
                  selector_min_ibd_rs_rank: 95.0
                  selector_min_relative_strength_index: 96.0
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="doivent rester identiques"):
        load_capital_presets(config_path)


# ── Sprint S8 : Tests de cohérence drawdown breaker et min_notional ──


def test_drawdown_breaker_params_are_non_decreasing_with_equity(presets):
    """T-CAP-002 : Les paramètres de drawdown breaker sont croissants avec le capital."""
    # Trier les presets par max_equity (ou min_equity si max_equity est None)
    sorted_presets = sorted(
        presets,
        key=lambda p: p.max_equity if p.max_equity is not None else float("inf"),
    )

    prev_degraded = -1.0
    prev_ramp_up_max = -1.0
    prev_ramp_up_per_day = -1.0

    for preset in sorted_presets:
        degraded = float(preset.values.get("risk_degraded_entry_allocation_pct", 0))
        ramp_up_max = float(preset.values.get("risk_regime_ramp_up_max_pct", 0))
        ramp_up_per_day = float(preset.values.get("risk_regime_ramp_up_pct_per_day", 0))

        assert degraded >= prev_degraded, (
            f"{preset.key}: risk_degraded_entry_allocation_pct={degraded} < prev={prev_degraded} — "
            f"les paramètres de drawdown breaker doivent être non-décroissants avec le capital"
        )
        assert ramp_up_max >= prev_ramp_up_max, (
            f"{preset.key}: risk_regime_ramp_up_max_pct={ramp_up_max} < prev={prev_ramp_up_max}"
        )
        assert ramp_up_per_day >= prev_ramp_up_per_day, (
            f"{preset.key}: risk_regime_ramp_up_pct_per_day={ramp_up_per_day} < prev={prev_ramp_up_per_day}"
        )

        prev_degraded = degraded
        prev_ramp_up_max = ramp_up_max
        prev_ramp_up_per_day = ramp_up_per_day


def test_backtesting_drawdown_breaker_params_match_risk(presets):
    """Les paramètres backtesting_dd_* doivent être cohérents avec leurs équivalents risk_*."""
    for preset in presets:
        risk_degraded = float(preset.values.get("risk_degraded_entry_allocation_pct", 0))
        risk_ramp_up_max = float(preset.values.get("risk_regime_ramp_up_max_pct", 0))
        risk_ramp_up_per_day = float(preset.values.get("risk_regime_ramp_up_pct_per_day", 0))

        bt_degraded = float(preset.values.get("backtesting_dd_degraded_allocation_pct", 0))
        bt_ramp_up_max = float(preset.values.get("backtesting_dd_regime_ramp_up_max_pct", 0))
        bt_ramp_up_per_day = float(preset.values.get("backtesting_dd_regime_ramp_up_pct_per_day", 0))

        assert bt_degraded == risk_degraded, (
            f"{preset.key}: backtesting_dd_degraded_allocation_pct={bt_degraded} != risk={risk_degraded}"
        )
        assert bt_ramp_up_max == risk_ramp_up_max, (
            f"{preset.key}: backtesting_dd_regime_ramp_up_max_pct={bt_ramp_up_max} != risk={risk_ramp_up_max}"
        )
        assert bt_ramp_up_per_day == risk_ramp_up_per_day, (
            f"{preset.key}: backtesting_dd_regime_ramp_up_pct_per_day={bt_ramp_up_per_day} != risk={risk_ramp_up_per_day}"
        )


def test_min_position_notional_ge_enforce_min_notional(presets):
    """T-CAP-003 : Tous les risk_min_position_notional >= enforce_min_notional (155$)."""
    ENFORCE_MIN_NOTIONAL = 155.0  # Alpaca minimum notional

    for preset in presets:
        min_notional = float(preset.values.get("risk_min_position_notional", 0))
        assert min_notional >= ENFORCE_MIN_NOTIONAL, (
            f"{preset.key}: risk_min_position_notional={min_notional} < enforce_min_notional={ENFORCE_MIN_NOTIONAL} — "
            f"les ordres seraient rejetés par Alpaca"
        )


def test_swing_only_is_false_on_all_presets(presets):
    """Post-PDT FINRA 2026-06-04 : execution_swing_only=false est correct sur tous les presets."""
    for preset in presets:
        swing_only = preset.values.get("execution_swing_only", None)
        assert swing_only is False, (
            f"{preset.key}: execution_swing_only={swing_only} — "
            f"devrait être false depuis la suppression de la règle PDT par la FINRA (2026-06-04)"
        )


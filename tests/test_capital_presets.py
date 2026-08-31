from __future__ import annotations

import ihm.services.capital_presets as capital_presets


def test_load_capital_presets_reads_versioned_yaml_file() -> None:
    presets = capital_presets.load_capital_presets()

    assert len(presets) >= 6
    # Sprint S26 — preset micro-compte (~2 000 €) prepended.
    assert presets[0].key == "capital_0_2000"
    assert presets[-1].key == "capital_100001_plus"


def test_resolve_capital_preset_for_equity_selects_expected_bucket() -> None:
    # Sprint S26 — 2 000 USD relève désormais du preset micro-compte EUR.
    assert capital_presets.resolve_capital_preset_for_equity(2_000.0).key == "capital_0_2000"
    assert capital_presets.resolve_capital_preset_for_equity(3_500.0).key == "capital_2001_5000"
    assert capital_presets.resolve_capital_preset_for_equity(7_500.0).key == "capital_5001_10000"
    assert capital_presets.resolve_capital_preset_for_equity(75_000.0).key == "capital_50001_100000"
    assert capital_presets.resolve_capital_preset_for_equity(150_000.0).key == "capital_100001_plus"


def test_capital_preset_maps_detected_equity_placeholder_to_pipeline_session_key() -> None:
    preset = capital_presets.get_capital_preset_by_key("capital_2001_5000")

    assert preset is not None
    session_values = preset.to_session_state_values(detected_equity=2_345.67)

    assert session_values["pipeline_risk_account_equity"] == 2_345.67
    assert session_values["pipeline_risk_per_trade_pct"] == 0.0125
    assert session_values["pipeline_screener_liquidity_threshold_usd"] == 5_000_000.0
    assert session_values["pipeline_selector_require_above_ma200"] == "auto"


def test_capital_preset_max_anomaly_count_monotonic() -> None:
    presets = capital_presets.load_capital_presets()
    anomaly_counts = [int(preset.values["selector_max_anomaly_count"]) for preset in presets]

    assert anomaly_counts == sorted(anomaly_counts)
    assert anomaly_counts[0] == 15


def test_capital_preset_uses_canonical_ibd_rs_key() -> None:
    preset = capital_presets.get_capital_preset_by_key("capital_0_2000")

    assert preset is not None
    assert preset.values["selector_min_ibd_rs_rank"] == 90.0
    assert "selector_min_relative_strength_index" not in preset.values

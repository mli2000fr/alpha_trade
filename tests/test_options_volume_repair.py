from modelFactory.directional_data_research.options_volume_repair import aggregate_four_leg_volumes


def test_aggregate_four_leg_volumes_requires_all_legs() -> None:
    result = aggregate_four_leg_volumes({
        "atm_call": 10.0, "otm_call": 5.0, "atm_put": 4.0, "otm_put": None,
    })
    assert result["volume_legs_available"] == 3
    assert result["call_put_volume_log_ratio"] is None


def test_aggregate_four_leg_volumes_preserves_real_zeros() -> None:
    result = aggregate_four_leg_volumes({
        "atm_call": 10.0, "otm_call": 0.0, "atm_put": 4.0, "otm_put": 1.0,
    })
    assert result["volume_legs_available"] == 4
    assert result["call_volume"] == 10.0
    assert result["put_volume"] == 5.0
    assert result["call_put_volume_log_ratio"] > 0

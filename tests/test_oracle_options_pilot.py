from __future__ import annotations

from datetime import date

import pandas as pd

from modelFactory import oracle_options_pilot as pilot
from modelFactory.oracle_amplitude_audit import GROUP_COL, TOP20


def test_choose_pair_requires_same_expiry_and_strike() -> None:
    contracts = [
        {"ticker": "C100", "contract_type": "call", "expiration_date": "2024-08-16", "strike_price": 100},
        {"ticker": "P100", "contract_type": "put", "expiration_date": "2024-08-16", "strike_price": 100},
        {"ticker": "C105", "contract_type": "call", "expiration_date": "2024-08-16", "strike_price": 105},
    ]
    pair = pilot.choose_contract_pair(
        contracts, spot=101, entry_date=date(2024, 7, 2), config=pilot.OptionsPilotConfig()
    )
    assert pair is not None
    assert pair["strike"] == 100
    assert pair["call_ticker"] == "C100"
    assert pair["put_ticker"] == "P100"


def test_choose_pair_rejects_single_leg() -> None:
    contracts = [
        {"ticker": "C100", "contract_type": "call", "expiration_date": "2024-08-16", "strike_price": 100}
    ]
    assert pilot.choose_contract_pair(
        contracts, spot=100, entry_date=date(2024, 7, 2), config=pilot.OptionsPilotConfig()
    ) is None


def test_config_rejects_negative_expiry_buffer() -> None:
    try:
        pilot.OptionsPilotConfig(minimum_exit_buffer_days=-1)
    except ValueError as error:
        assert "buffer" in str(error)
    else:
        raise AssertionError("Un buffer négatif doit être rejeté.")


def test_horizon_specific_dte_contracts_are_valid() -> None:
    expected = {
        3: (10, 14, 21), 5: (14, 21, 28),
        10: (21, 28, 35), 20: (35, 45, 55),
    }
    for horizon, (minimum, target, maximum) in expected.items():
        config = pilot.OptionsPilotConfig(
            horizons=(horizon,), min_dte=minimum,
            target_dte=target, max_dte=maximum,
        )
        assert config.min_dte <= config.target_dte <= config.max_dte


def test_schedule_counts_entry_session_as_h1() -> None:
    dates = pd.date_range("2024-01-02", periods=30, freq="B")
    bars = pd.DataFrame({"date": dates, "symbol": "AAA", "open": 100.0})
    events = pd.DataFrame({"date": [dates[2]], "symbol": ["AAA"]})
    result = pilot.build_event_schedule(events, bars, (3, 5, 20)).iloc[0]
    assert result["entry_date"] == dates[3]
    assert result["h3_exit_date"] == dates[5]
    assert result["h20_exit_date"] == dates[22]


def test_event_sampling_is_temporal_and_oracle_only() -> None:
    rows = []
    for current in pd.date_range("2022-01-03", "2023-12-29", freq="B"):
        for index in range(3):
            rows.append({
                "date": current, "symbol": f"S{index}",
                GROUP_COL: TOP20 if index < 2 else "REST80",
                "directional_oracle_extreme_pct": 1-index/10,
                "amplitude_entry_eligible": index != 1,
                "h20_max_abs_excursion_capped_100pct": 0.1,
            })
    selected = pilot.select_pilot_events(
        pd.DataFrame(rows), dates_per_semester=1, max_symbols_per_date=1,
        start_date="2022-03-07", end_date="2023-12-29",
    )
    assert selected[GROUP_COL].eq(TOP20).all()
    assert selected.groupby("semester")["date"].nunique().eq(1).all()
    assert selected.groupby("date").size().eq(1).all()
    assert selected["symbol"].eq("S0").all()


def test_summary_reports_ask_bid_net_returns() -> None:
    frame = pd.DataFrame({
        "status": ["complete", "partial_exit_nbbo"],
        "call_ticker": ["C", "C2"], "entry_premium": [10.0, 8.0],
        "h3_net_return": [0.2, -0.1],
    })
    result = pilot.summarize(frame, pilot.OptionsPilotConfig(horizons=(3,)))
    assert result["h3"]["observations"] == 2
    assert result["h3"]["mean_net_return"] == 0.05
    assert result["h3"]["positive_rate"] == 0.5

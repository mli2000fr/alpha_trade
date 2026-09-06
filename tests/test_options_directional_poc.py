from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from modelFactory import options_directional_poc as options
from modelFactory.oracle_amplitude_audit import GROUP_COL, TOP20


def test_select_events_is_temporal_and_does_not_filter_on_future_gap() -> None:
    rows = []
    for current in pd.date_range("2022-03-07", "2023-12-29", freq="B"):
        rows.extend([
            {"date": current, "symbol": "AAA", GROUP_COL: TOP20,
             "directional_oracle_extreme_pct": 0.99, "amplitude_entry_eligible": False},
            {"date": current, "symbol": "BBB", GROUP_COL: TOP20,
             "directional_oracle_extreme_pct": 0.98, "amplitude_entry_eligible": True},
            {"date": current, "symbol": "CCC", GROUP_COL: "REST80",
             "directional_oracle_extreme_pct": 0.20, "amplitude_entry_eligible": True},
        ])
    selected = options.select_events(
        pd.DataFrame(rows), start_date="2022-03-07", end_date="2023-12-29",
        dates_per_semester=1,
    )
    assert selected.groupby("semester")["date"].nunique().eq(1).all()
    assert set(selected["symbol"]) == {"AAA", "BBB"}


def test_choose_surface_uses_one_expiry_and_symmetric_wings() -> None:
    contracts = []
    for strike in (90, 95, 100, 105, 110):
        for side in ("call", "put"):
            contracts.append({
                "ticker": f"{side[0].upper()}{strike}", "contract_type": side,
                "expiration_date": "2024-08-16", "strike_price": strike,
            })
    selected = options.choose_surface_contracts(
        contracts, spot=100, signal_date=date(2024, 7, 2),
        config=options.OptionsDirectionalConfig(),
    )
    assert selected is not None
    assert selected["atm_strike"] == 100
    assert selected["otm_call_strike"] == 105
    assert selected["otm_put_strike"] == 95


def test_fetch_surface_builds_expiry_dates_from_plain_date() -> None:
    class Response:
        ok = True

        @staticmethod
        def json() -> dict[str, list[dict[str, object]]]:
            return {"results": []}

    class Client:
        params: dict[str, object] = {}

        def get(self, _path: str, *, params: dict[str, object]) -> Response:
            self.params = params
            return Response()

    client = Client()
    assert options.fetch_surface_contracts(
        client, "AAA", date(2024, 7, 2), 100.0,
        options.OptionsDirectionalConfig(),
    ) is None
    assert client.params["expiration_date.gte"] == "2024-08-06"
    assert client.params["expiration_date.lte"] == "2024-08-26"


def test_implied_volatility_recovers_black_price() -> None:
    expected = 0.42
    price = options._black_price(101.0, 105.0, 45/365, expected, "call")
    actual = options.implied_volatility(
        price, forward=101.0, strike=105.0, years=45/365, side="call"
    )
    assert actual == pytest.approx(expected, rel=1e-6)


def test_compute_features_are_oriented_toward_call_strength() -> None:
    def quote(mid: float, depth: float) -> dict[str, float]:
        return {"mid": mid, "bid_size": depth/2, "ask_size": depth/2,
                "relative_spread": 0.05, "timestamp": 1}
    surface = {"atm_strike": 100, "otm_call_strike": 105,
               "otm_put_strike": 95, "dte": 45}
    result = options.compute_features(
        spot=100, surface=surface,
        quotes={"atm_call": quote(6, 30), "atm_put": quote(5, 20),
                "otm_call": quote(3, 40), "otm_put": quote(2, 10)},
        volumes={"atm_call": 100, "otm_call": 50, "atm_put": 40, "otm_put": 10},
    )
    assert result["otm_price_risk_reversal"] > 0
    assert result["atm_call_put_mid_log_ratio"] > 0
    assert result["otm_quote_depth_imbalance"] > 0
    assert result["call_put_volume_log_ratio"] > 0


def test_compute_features_does_not_impute_missing_volume_as_zero() -> None:
    def quote(mid: float) -> dict[str, float]:
        return {"mid": mid, "bid_size": 10, "ask_size": 10,
                "relative_spread": 0.05, "timestamp": 1}

    result = options.compute_features(
        spot=100,
        surface={"atm_strike": 100, "otm_call_strike": 105,
                 "otm_put_strike": 95, "dte": 45},
        quotes={"atm_call": quote(6), "atm_put": quote(5),
                "otm_call": quote(3), "otm_put": quote(2)},
        volumes={"atm_call": None, "otm_call": None,
                 "atm_put": None, "otm_put": None},
    )

    assert result["call_volume"] is None
    assert result["put_volume"] is None
    assert result["call_put_volume_log_ratio"] is None


def test_evaluation_masks_incomplete_four_leg_volume() -> None:
    frame = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-02")],
        "h3_terminal_return": [0.01],
        "call_put_volume_log_ratio": [0.0],
        "volume_legs_available": [0],
    })

    result = options.evaluate_features(frame, options.OptionsDirectionalConfig())

    assert result["horizons"]["h3"]["call_put_volume_log_ratio"]["coverage"] == 0
    assert result["horizons"]["h3"]["call_put_volume_log_ratio"]["observations"] == 0


def test_perfect_feature_passes_prefixed_directional_gates() -> None:
    rows = []
    for year in range(2022, 2026):
        for day in range(3):
            current = pd.Timestamp(year=year, month=2+day, day=1)
            for index in range(50):
                value = index/49
                rows.append({"date": current, "signal": value,
                             "h20_terminal_return": (value-0.5)*0.20})
    result = options.evaluate_feature(
        pd.DataFrame(rows), "signal", "h20_terminal_return", 0.20
    )
    assert result["mean_daily_ic"] > 0.99
    assert result["auc_d10_vs_d1"] == pytest.approx(1.0)
    assert result["all_gates_passed"] is True

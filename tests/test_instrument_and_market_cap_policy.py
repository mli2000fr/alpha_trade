from datetime import date

import pandas as pd

from common.instrument_policy import excluded_collective_instrument_reason
from common.publish_tradable_universe import _select_market_cap_rows


def test_collective_instrument_policy_excludes_target_products() -> None:
    assert excluded_collective_instrument_reason("iShares Core S&P 500 ETF") == "excluded_etf_or_etn"
    assert excluded_collective_instrument_reason("MicroSectors FANG+ ETNs due 2038") == "excluded_etf_or_etn"
    assert excluded_collective_instrument_reason("Vanguard Total Bond Market") is not None
    assert excluded_collective_instrument_reason("ProShares UltraShort QQQ") is not None


def test_collective_instrument_policy_keeps_companies_reits_and_adrs() -> None:
    assert excluded_collective_instrument_reason("Digital Realty Trust, Inc.") is None
    assert excluded_collective_instrument_reason("Fundamental Global Inc.") is None
    assert excluded_collective_instrument_reason("Taiwan Semiconductor Manufacturing ADR") is None
    assert excluded_collective_instrument_reason("Ultra Clean Holdings, Inc.") is None
    assert excluded_collective_instrument_reason("Invesco Ltd.") is None
    assert excluded_collective_instrument_reason("Invesco QQQ Trust") is not None


def test_yahoo_is_preferred_when_both_sources_are_fresh() -> None:
    rows = pd.DataFrame(
        [
            {
                "symbol": "ABC",
                "market_value": 3_000_000_000.0,
                "market_cap_reference_date": "2025-01-01",
                "market_cap_source": "FINNHUB",
            },
            {
                "symbol": "ABC",
                "market_value": 2_500_000_000.0,
                "market_cap_reference_date": "2024-12-31",
                "market_cap_source": "YAHOO FINANCE",
            },
        ]
    )

    selected = _select_market_cap_rows(
        rows,
        snapshot_date=date(2025, 1, 2),
        max_age_days=365,
        provider="yahoo_then_finnhub",
    )

    assert len(selected) == 1
    assert selected.iloc[0]["market_cap_source"] == "YAHOO FINANCE"
    assert selected.iloc[0]["market_value"] == 2_500_000_000.0


def test_fresh_finnhub_replaces_stale_yahoo() -> None:
    rows = pd.DataFrame(
        [
            {
                "symbol": "ABC",
                "market_value": 2_500_000_000.0,
                "market_cap_reference_date": "2022-01-01",
                "market_cap_source": "YAHOO FINANCE",
            },
            {
                "symbol": "ABC",
                "market_value": 3_000_000_000.0,
                "market_cap_reference_date": "2024-12-31",
                "market_cap_source": "FINNHUB",
            },
        ]
    )

    selected = _select_market_cap_rows(
        rows,
        snapshot_date=date(2025, 1, 2),
        max_age_days=365,
        provider="yahoo_then_finnhub",
    )

    assert selected.iloc[0]["market_cap_source"] == "FINNHUB"
    assert selected.iloc[0]["market_value"] == 3_000_000_000.0

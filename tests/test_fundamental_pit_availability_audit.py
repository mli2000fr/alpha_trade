from __future__ import annotations

import pandas as pd

from modelFactory.fundamental_pit_availability_audit import (
    ACCOUNTING_COLUMNS,
    E19AConfig,
    loader_contract_audit,
    next_market_session,
    reconstruct_daily_availability,
)


def _fundamental_row(*, filed: str, roe: float = 0.2) -> dict:
    row = {
        "symbol": "AAA", "trade_date": pd.Timestamp(filed),
        "fetched_at": pd.Timestamp("2026-09-01"), "source": "SEC_EDGAR",
    }
    for column in ACCOUNTING_COLUMNS:
        row[column] = None
    row["roe"] = roe
    for column in (
        "pe_ratio", "pb_ratio", "ps_ratio", "ev_to_ebitda", "market_cap",
        "beta", "dividend_yield", "forward_pe", "peg_ratio",
        "eps_estimate_current", "eps_estimate_next",
    ):
        row[column] = None
    return row


def test_sec_filing_becomes_available_on_strictly_next_market_session() -> None:
    calendar = pd.DatetimeIndex(pd.to_datetime([
        "2024-01-05", "2024-01-08", "2024-01-09",
    ]))
    result = next_market_session(pd.Series(pd.to_datetime([
        "2024-01-05", "2024-01-06", "2024-01-08",
    ])), calendar)
    assert result.tolist() == [
        pd.Timestamp("2024-01-08"), pd.Timestamp("2024-01-08"),
        pd.Timestamp("2024-01-09"),
    ]


def test_same_day_filing_is_not_visible_but_next_session_is() -> None:
    eligible = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-05", "2024-01-08"]),
        "symbol": ["AAA", "AAA"],
    })
    fundamentals = pd.DataFrame([_fundamental_row(filed="2024-01-05")])
    calendar = pd.DatetimeIndex(eligible["date"])
    result = reconstruct_daily_availability(
        eligible, fundamentals, calendar, E19AConfig()
    ).sort_values("date")
    assert pd.isna(result.iloc[0]["roe"])
    assert result.iloc[1]["roe"] == 0.2
    assert result.iloc[1]["available_date"] == pd.Timestamp("2024-01-08")


def test_stale_filing_is_present_but_not_fresh() -> None:
    eligible = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-08", "2024-08-01"]),
        "symbol": ["AAA", "AAA"],
    })
    fundamentals = pd.DataFrame([_fundamental_row(filed="2024-01-05")])
    calendar = pd.DatetimeIndex(eligible["date"])
    result = reconstruct_daily_availability(
        eligible, fundamentals, calendar, E19AConfig(primary_max_age_days=180)
    ).sort_values("date")
    assert bool(result.iloc[0]["fresh_primary"])
    assert not bool(result.iloc[1]["fresh_primary"])
    assert bool(result.iloc[1]["has_any_accounting"])


def test_non_sec_snapshot_is_never_used_for_historical_reconstruction() -> None:
    eligible = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-08"]), "symbol": ["AAA"],
    })
    row = _fundamental_row(filed="2024-01-05")
    row["source"] = "Yahoo Finance"
    result = reconstruct_daily_availability(
        eligible, pd.DataFrame([row]), pd.DatetimeIndex(eligible["date"]), E19AConfig()
    )
    assert pd.isna(result.loc[0, "roe"])
    assert not bool(result.loc[0, "fresh_primary"])


def test_loader_contract_exposes_only_missing_schema_blocker() -> None:
    table_columns = {
        "symbol", "trade_date", "fetched_at", "source", "roe", "roa",
    }
    audit = loader_contract_audit(table_columns)
    assert audit["loader_selects_source"]
    assert audit["loader_has_deterministic_provider_priority"]
    assert audit["loader_fetches_pre_start_predecessor"]
    assert audit["loader_uses_conservative_next_session_availability"]
    assert audit["loader_preserves_missing_as_nan"]
    assert not audit["table_has_required_lineage"]


def test_loader_contract_is_ready_after_migration_0074() -> None:
    table_columns = {
        "symbol", "trade_date", "available_date", "fetched_at", "source",
        "fiscal_period_end", "form", "accession_number", "roe", "roa",
    }
    audit = loader_contract_audit(table_columns)
    assert audit["table_has_required_lineage"]
    assert all(
        audit[key]
        for key in (
            "loader_selects_source", "loader_selects_fetched_at",
            "loader_has_deterministic_provider_priority",
            "loader_fetches_pre_start_predecessor",
            "loader_preserves_missing_as_nan",
            "loader_uses_conservative_next_session_availability",
        )
    )

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from modelFactory.fundamental_features import (
    _apply_availability_contract,
    derive_features,
    load_fundamentals_from_db,
)


def test_non_sec_snapshot_cannot_be_backdated_before_fetch() -> None:
    frame = pd.DataFrame([{
        "symbol": "AAA", "trade_date": "2020-01-01",
        "available_date": None, "fetched_at": "2026-09-10 12:00:00",
        "source": "EODHD", "roe": 0.2,
    }])
    result = _apply_availability_contract(frame)
    assert result.iloc[0]["available_date"] == pd.Timestamp("2026-09-11")


def test_same_day_provider_collision_uses_deterministic_priority() -> None:
    frame = pd.DataFrame([
        {"symbol": "AAA", "trade_date": "2024-01-05", "available_date": "2024-01-06",
         "fetched_at": "2024-01-05", "source": "Finnhub", "roe": 0.1},
        {"symbol": "AAA", "trade_date": "2024-01-05", "available_date": "2024-01-06",
         "fetched_at": "2026-09-01", "source": "SEC_EDGAR", "roe": 0.3},
    ])
    result = _apply_availability_contract(frame)
    assert len(result) == 1
    assert result.iloc[0]["source"] == "SEC_EDGAR"
    assert result.iloc[0]["roe"] == 0.3


def test_missingness_is_explicit_and_zero_is_not_missing() -> None:
    result = derive_features(pd.DataFrame({"roe": [np.nan, 0.0, 0.25]}))
    assert result["fund_roe"].tolist() == [0.0, 0.0, 0.25]
    assert result["fund_roe_missing"].tolist() == [1.0, 0.0, 0.0]
    assert result["fund_beta_missing"].tolist() == [1.0, 1.0, 1.0]


def test_loader_keeps_last_pre_start_observation() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE stock_fundamentals_daily (
                symbol TEXT, trade_date DATE, available_date DATE,
                fetched_at DATETIME, source TEXT, roe FLOAT
            )
        """))
        connection.execute(text("""
            INSERT INTO stock_fundamentals_daily VALUES
            ('AAA','2023-12-20','2023-12-21','2026-09-01','SEC_EDGAR',0.1),
            ('AAA','2024-01-10','2024-01-11','2026-09-01','SEC_EDGAR',0.2),
            ('AAA','2024-02-10','2024-02-11','2026-09-01','SEC_EDGAR',0.3)
        """))
    result = load_fundamentals_from_db(
        ["AAA"], "2024-01-01", "2024-01-31", engine=engine
    )
    assert result["source_trade_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2023-12-20", "2024-01-10",
    ]
    assert result["trade_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2023-12-21", "2024-01-11",
    ]

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
import requests

import modelFactory.nyse_auction_history_poc as nyse_poc
from modelFactory.nyse_auction_history_poc import (
    NyseRateLimitError,
    _candidate_dates,
    _parse_symbols,
    _request_json,
    _resolve_input_symbols,
    _rotate_symbols,
    summarize_auction_rows,
)


def test_poc_hard_limits_symbols_and_keeps_deterministic_order() -> None:
    assert _parse_symbols("IBM,JPM,IBM") == ["IBM", "JPM"]
    with pytest.raises(ValueError, match="limited to 20"):
        _parse_symbols(",".join(f"S{index}" for index in range(21)))



def test_universe_source_accepts_full_daily_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        nyse_poc,
        "load_universe_file_symbols",
        lambda source: ["JPM", "IBM", "IBM", "BAC"] if source else [],
    )
    assert _resolve_input_symbols(
        None, "universe-file:univers_filtred_tradable.txt",
    ) == ["BAC", "IBM", "JPM"]


def test_direct_symbols_and_universe_source_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="either --symbols or --symbol-source"):
        _resolve_input_symbols("IBM", "universe-file:univers_filtred_tradable.txt")

def test_daily_rotation_is_deterministic_and_keeps_all_symbols() -> None:
    symbols = ["A", "B", "C", "D"]
    rotated, offset = _rotate_symbols(symbols, key="opening:2026-09-11")
    repeated, repeated_offset = _rotate_symbols(symbols, key="opening:2026-09-11")
    assert (rotated, offset) == (repeated, repeated_offset)
    assert sorted(rotated) == symbols
    assert 0 <= offset < len(symbols)

def test_candidate_dates_exclude_weekends_and_keep_last_limit() -> None:
    assert _candidate_dates(date(2026, 9, 7), date(2026, 9, 13), 3) == [
        date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11),
    ]


def test_rate_limit_is_explicit_and_does_not_retry_forever() -> None:
    class Response:
        status_code = 429
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            raise requests.HTTPError("429")

        def json(self) -> dict[str, str]:
            return {}

    class Session:
        def get(self, *args: object, **kwargs: object) -> Response:
            return Response()

    with pytest.raises(NyseRateLimitError, match="HTTP 429"):
        _request_json(
            Session(),  # type: ignore[arg-type]
            "/api/auction-charts",
            {"symbol": "IBM"},
            attempts=1,
        )


def test_summary_is_explicitly_post_auction_and_preserves_direction() -> None:
    observed = datetime(2026, 9, 11, 14, 0, tzinfo=UTC)
    rows = [
        {
            "tradeDate": "2026-09-11 09:25:00", "symbol": "IBM", "mic": "XNYS",
            "price": 235.0, "avgPairedQty": 20000,
            "avgImbalanceQty": -1000, "avgBookClearingPrice": 234.5,
        },
        {
            "tradeDate": "2026-09-11 09:30:00", "symbol": "IBM", "mic": "XNYS",
            "price": 235.0, "avgPairedQty": 25000,
            "avgImbalanceQty": -5000, "avgBookClearingPrice": 234.0,
        },
    ]
    result = summarize_auction_rows(rows, observed_at=observed)
    assert result is not None
    assert result["imbalance_side"] == "SELL"
    assert result["imbalance_acceleration"] == -4000
    assert result["imbalance_to_paired"] == -0.2
    assert result["side_persistence"] == 1.0
    assert result["available_before_auction"] is False
    assert result["source_contract"] == "NYSE_WEB_POST_AUCTION_UNDOCUMENTED_ROUTE"


def test_empty_auction_response_is_not_a_valid_observation() -> None:
    assert summarize_auction_rows([], observed_at=datetime.now(UTC)) is None


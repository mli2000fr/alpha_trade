from pathlib import Path

import pandas as pd
import pytest

from modelFactory.oracle_universe_audit import _concentration, parse_symbols, source_path


def test_parse_symbols_normalizes_deduplicates_and_sorts() -> None:
    assert parse_symbols(" msft,AAPL,MSFT,, ") == ["AAPL", "MSFT"]


def test_source_path_only_resolves_universe_file_source() -> None:
    assert source_path("universe-file:ticket_recherche.txt") == Path(
        "config/univers/ticket_recherche.txt"
    )
    assert source_path("tradable-universe") is None


def test_concentration_reports_top_twenty_percent_share() -> None:
    result = _concentration(pd.Series([40, 30, 20, 10, 0]))
    assert result["events"] == 100
    assert result["top_20pct_symbols"] == 1
    assert result["top_20pct_event_share"] == pytest.approx(0.40)
    assert result["hhi"] == pytest.approx(0.30)


def test_concentration_handles_empty_input() -> None:
    result = _concentration(pd.Series(dtype=float))
    assert result["events"] == 0
    assert result["top_20pct_event_share"] == 0.0
    assert result["hhi"] == 0.0

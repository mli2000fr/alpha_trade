from pathlib import Path

import pandas as pd

from scripts.build_equity_universe import filter_equity_symbols, read_symbols


def test_read_symbols_accepts_commas_comments_and_duplicates(tmp_path: Path) -> None:
    source = tmp_path / "universe.txt"
    source.write_text("AAPL,SPY\n# commentaire\nAAPL,MSFT\n", encoding="utf-8")
    assert read_symbols(source) == ["AAPL", "MSFT", "SPY"]


def test_filter_equity_symbols_keeps_companies_and_excludes_products() -> None:
    metadata = pd.DataFrame(
        [
            {"symbol": "AAPL", "company_name": "Apple Inc."},
            {"symbol": "DLR", "company_name": "Digital Realty Trust, Inc."},
            {"symbol": "SPY", "company_name": "SPDR S&P 500 ETF Trust"},
            {"symbol": "TQQQ", "company_name": "ProShares UltraPro QQQ"},
        ]
    )

    retained, excluded = filter_equity_symbols(
        ["AAPL", "DLR", "SPY", "TQQQ"], metadata
    )

    assert retained == ["AAPL", "DLR"]
    assert {row["symbol"] for row in excluded} == {"SPY", "TQQQ"}
